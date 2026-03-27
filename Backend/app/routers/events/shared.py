"""Shared helpers for the event router package."""

from datetime import datetime, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db
from app.core.event_defaults import resolve_governance_event_default_values
from app.core.security import get_current_user, get_school_id_or_403, has_any_role
from app.models.attendance import Attendance as AttendanceModel
from app.models.department import Department as DepartmentModel
from app.models.event import Event as EventModel, EventStatus as ModelEventStatus
from app.models.governance_hierarchy import GovernanceUnit, GovernanceUnitType, PermissionCode
from app.models.program import Program as ProgramModel
from app.models.school import SchoolSetting as SchoolSettingModel
from app.models.user import StudentProfile as StudentProfileModel, User as UserModel
from app.schemas.event import (
    Event as EventSchema,
    EventCreate,
    EventLocationVerificationRequest,
    EventLocationVerificationResponse,
    EventStatus,
    EventTimeStatusInfo,
    EventUpdate,
    EventWithRelations,
    SignOutOpenEarlyRequest,
)
from app.services import governance_hierarchy_service
from app.services.event_attendance_service import finalize_completed_event_attendance
from app.services.event_geolocation import (
    build_event_time_status_info,
    validate_event_geolocation_fields,
    verify_event_geolocation,
)
from app.services.event_time_status import (
    DEFAULT_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES,
    get_event_timezone,
)
from app.services.event_workflow_status import (
    get_expected_workflow_status,
    sync_event_workflow_status,
    sync_scope_event_workflow_statuses,
)

logger = logging.getLogger(__name__)
NEAR_START_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES = (
    DEFAULT_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES
)


def _get_payload_fields_set(payload) -> set[str]:
    model_fields_set = getattr(payload, "model_fields_set", None)
    if model_fields_set is not None:
        return set(model_fields_set)
    return set(payload.__fields_set__)


def _ensure_event_manager(db: Session, current_user: UserModel) -> None:
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return

    if governance_hierarchy_service.get_user_governance_unit_types(
        db,
        current_user=current_user,
    ):
        governance_hierarchy_service.ensure_governance_permission(
            db,
            current_user=current_user,
            permission_code=PermissionCode.MANAGE_EVENTS,
            detail=(
                "This governance account has no event features yet. "
                "Campus Admin must assign manage_events to the governance member."
            ),
        )
        return

    raise HTTPException(status_code=403, detail="Not authorized to manage events")


def _ensure_event_attendance_manager(db: Session, current_user: UserModel) -> None:
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return

    if governance_hierarchy_service.get_user_governance_unit_types(
        db,
        current_user=current_user,
    ):
        governance_hierarchy_service.ensure_governance_permission(
            db,
            current_user=current_user,
            permission_code=PermissionCode.MANAGE_ATTENDANCE,
            detail=(
                "This governance account has no attendance features yet. "
                "Campus Admin must assign manage_attendance to the governance member."
            ),
        )
        return

    raise HTTPException(status_code=403, detail="Not authorized to manage event attendance")


def _actor_school_scope_id(current_user: UserModel) -> Optional[int]:
    if has_any_role(current_user, ["admin"]) and getattr(current_user, "school_id", None) is None:
        return None
    return get_school_id_or_403(current_user)


def _require_school_scope(current_user: UserModel) -> int:
    school_id = _actor_school_scope_id(current_user)
    if school_id is None:
        raise HTTPException(
            status_code=403,
            detail="Platform admin cannot perform school-scoped event writes without school context.",
        )
    return school_id


def _school_scoped_event_query(db: Session, school_id: Optional[int]):
    query = db.query(EventModel)
    if school_id is not None:
        query = query.filter(EventModel.school_id == school_id)
    return query


def _get_school_settings(db: Session, *, school_id: int) -> SchoolSettingModel | None:
    return (
        db.query(SchoolSettingModel)
        .filter(SchoolSettingModel.school_id == school_id)
        .first()
    )


def _persist_scope_status_sync(db: Session, school_id: Optional[int]) -> None:
    results = sync_scope_event_workflow_statuses(db, school_id=school_id)
    if any(result.changed for result in results):
        db.commit()


def _persist_event_status_sync(db: Session, event: EventModel) -> None:
    result = sync_event_workflow_status(db, event)
    if result.changed:
        db.commit()
        db.refresh(event)


def _resolve_near_start_attendance_override_window(
    *,
    start_datetime: datetime,
    end_datetime: datetime,
    early_check_in_minutes: int,
    late_threshold_minutes: int,
    current_time: datetime,
) -> tuple[datetime | None, datetime | None]:
    normalized_early_check_in_minutes = max(0, int(early_check_in_minutes or 0))
    normalized_late_threshold_minutes = max(0, int(late_threshold_minutes or 0))
    if normalized_early_check_in_minutes <= 0:
        return None, None

    time_until_start = start_datetime - current_time
    if time_until_start >= timedelta(minutes=normalized_early_check_in_minutes):
        return None, None

    if start_datetime <= current_time:
        raise HTTPException(
            status_code=400,
            detail=(
                "This event start time is already in the past, so the near-start attendance "
                "override cannot preserve the full present window. Move the start time later "
                "or reduce the early check-in minutes."
            ),
        )

    required_duration_minutes = (
        normalized_early_check_in_minutes
        + normalized_late_threshold_minutes
        + NEAR_START_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES
    )
    remaining_duration_seconds = (end_datetime - current_time).total_seconds()
    if remaining_duration_seconds < required_duration_minutes * 60:
        raise HTTPException(
            status_code=400,
            detail=(
                "This event is too short for the near-start attendance override. "
                f"It needs at least {required_duration_minutes} minutes from now until the event "
                f"end to keep {normalized_early_check_in_minutes} minutes present, "
                f"{normalized_late_threshold_minutes} minutes late, and "
                f"{NEAR_START_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES} minutes absent."
            ),
        )

    present_until_override_at = current_time + timedelta(
        minutes=normalized_early_check_in_minutes
    )
    late_until_override_at = present_until_override_at + timedelta(
        minutes=normalized_late_threshold_minutes
    )
    return present_until_override_at, late_until_override_at


def _build_status_conflict_detail(
    *,
    requested_status: EventStatus,
    computed_time_status: str,
    event: EventModel,
) -> str | None:
    if requested_status == EventStatus.ongoing:
        if computed_time_status in {"before_check_in", "early_check_in"}:
            scheduled_start = event.start_datetime.isoformat(sep=" ", timespec="minutes")
            return (
                "You cannot start this event yet. "
                f"Its scheduled start time is {scheduled_start}."
            )
        if computed_time_status == "closed":
            scheduled_end = event.end_datetime.isoformat(sep=" ", timespec="minutes")
            return (
                "You cannot start this event because the event schedule is already closed. "
                f"Its scheduled end time was {scheduled_end}."
            )

    if requested_status == EventStatus.upcoming:
        if event.status == ModelEventStatus.COMPLETED:
            return "You cannot reopen this event because it is already completed."
        if computed_time_status in {"late_check_in", "absent_check_in"}:
            return "You cannot reopen this event to upcoming because it is already in progress."

    return None


def _get_event_scope_ids(event: EventModel) -> tuple[set[int], set[int]]:
    return (
        {department.id for department in event.departments},
        {program.id for program in event.programs},
    )


def _get_actor_student_profile(db: Session, current_user: UserModel) -> Optional[StudentProfileModel]:
    school_id = _actor_school_scope_id(current_user)
    if school_id is None:
        return None
    return (
        db.query(StudentProfileModel)
        .filter(
            StudentProfileModel.user_id == current_user.id,
            StudentProfileModel.school_id == school_id,
        )
        .first()
    )


def _event_is_visible_to_student_profile(
    event: EventModel,
    student_profile: Optional[StudentProfileModel],
) -> bool:
    if student_profile is None:
        return False

    event_department_ids, event_program_ids = _get_event_scope_ids(event)
    if not event_department_ids and not event_program_ids:
        return True
    if event_department_ids and student_profile.department_id not in event_department_ids:
        return False
    if event_program_ids and student_profile.program_id not in event_program_ids:
        return False
    return True


def _filter_events_to_student_scope(
    events: list[EventModel],
    *,
    student_profile: Optional[StudentProfileModel],
) -> list[EventModel]:
    if student_profile is None:
        return []
    return [
        event
        for event in events
        if event.status == ModelEventStatus.UPCOMING
        or _event_is_visible_to_student_profile(event, student_profile)
    ]


def _filter_events_for_actor(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
    events: list[EventModel],
) -> list[EventModel]:
    filtered_events = _filter_events_to_governance_scope(
        events,
        _get_governance_event_units(
            db,
            current_user=current_user,
            governance_context=governance_context,
        ),
    )

    if governance_context is not None or has_any_role(current_user, ["admin", "campus_admin"]):
        return filtered_events

    return _filter_events_to_student_scope(
        filtered_events,
        student_profile=_get_actor_student_profile(db, current_user),
    )


def _get_governance_event_units(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
) -> list:
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return []

    if governance_context is None:
        return []

    governance_units = governance_hierarchy_service.get_governance_units_with_permission(
        db,
        current_user=current_user,
        permission_code=PermissionCode.MANAGE_EVENTS,
        unit_type=governance_context,
    )
    if governance_units:
        return governance_units

    governance_unit_types = governance_hierarchy_service.get_user_governance_unit_types(
        db,
        current_user=current_user,
    )
    if governance_context in governance_unit_types:
        raise HTTPException(
            status_code=403,
            detail=(
                "This governance account has no event features yet. "
                "The parent governance manager must assign manage_events first."
            ),
        )
    raise HTTPException(
        status_code=403,
        detail="You do not have access to this governance event scope.",
    )


def _get_governance_event_write_units(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
) -> list:
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return []

    if governance_context is not None:
        return _get_governance_event_units(
            db,
            current_user=current_user,
            governance_context=governance_context,
        )

    return governance_hierarchy_service.get_governance_units_with_permission(
        db,
        current_user=current_user,
        permission_code=PermissionCode.MANAGE_EVENTS,
    )


def _get_governance_attendance_units(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
) -> list:
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return []

    governance_units = governance_hierarchy_service.get_governance_units_with_permission(
        db,
        current_user=current_user,
        permission_code=PermissionCode.MANAGE_ATTENDANCE,
        unit_type=governance_context,
    )
    if governance_units:
        return governance_units

    if governance_context is not None:
        governance_unit_types = governance_hierarchy_service.get_user_governance_unit_types(
            db,
            current_user=current_user,
        )
        if governance_context in governance_unit_types:
            raise HTTPException(
                status_code=403,
                detail=(
                    "This governance account has no attendance features yet. "
                    "The parent governance manager must assign manage_attendance first."
                ),
            )

    if governance_context is not None:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this governance attendance scope.",
        )

    return governance_units


def _event_is_within_governance_units(event: EventModel, governance_units: list) -> bool:
    event_department_ids, event_program_ids = _get_event_scope_ids(event)
    return any(
        governance_hierarchy_service.governance_unit_matches_event_scope(
            governance_unit,
            department_ids=event_department_ids,
            program_ids=event_program_ids,
        )
        for governance_unit in governance_units
    )


def _filter_events_to_governance_scope(events: list[EventModel], governance_units: list) -> list[EventModel]:
    if not governance_units:
        return events
    return [event for event in events if _event_is_within_governance_units(event, governance_units)]


def _ensure_event_is_visible_in_governance_scope(
    db: Session,
    *,
    current_user: UserModel,
    event: EventModel,
    governance_context: GovernanceUnitType | None,
) -> None:
    governance_units = _get_governance_event_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    if governance_units and not _event_is_within_governance_units(event, governance_units):
        raise HTTPException(status_code=404, detail="Event not found")


def _ensure_event_is_writable_in_governance_scope(
    db: Session,
    *,
    current_user: UserModel,
    event: EventModel,
    governance_context: GovernanceUnitType | None,
) -> None:
    governance_units = _get_governance_event_write_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    if governance_units and not _event_is_within_governance_units(event, governance_units):
        raise HTTPException(status_code=404, detail="Event not found")


def _ensure_event_is_attendance_writable_in_governance_scope(
    db: Session,
    *,
    current_user: UserModel,
    event: EventModel,
    governance_context: GovernanceUnitType | None,
) -> None:
    governance_units = _get_governance_attendance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    if governance_units and not _event_is_within_governance_units(event, governance_units):
        raise HTTPException(status_code=404, detail="Event not found")


def _ensure_event_is_visible_for_actor(
    db: Session,
    *,
    current_user: UserModel,
    event: EventModel,
    governance_context: GovernanceUnitType | None,
) -> None:
    if governance_context is not None:
        _ensure_event_is_visible_in_governance_scope(
            db,
            current_user=current_user,
            event=event,
            governance_context=governance_context,
        )
        return

    if has_any_role(current_user, ["admin", "campus_admin"]):
        return

    if not _event_is_visible_to_student_profile(event, _get_actor_student_profile(db, current_user)):
        raise HTTPException(status_code=404, detail="Event not found")


def _resolve_governance_event_write_scope(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
) -> tuple[list[int], list[int]] | None:
    governance_unit, department_ids, program_ids = _resolve_governance_event_write_unit_and_scope(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    if governance_unit is None:
        return None
    return department_ids, program_ids


def _resolve_governance_event_write_unit_and_scope(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
) -> tuple[GovernanceUnit | None, list[int], list[int]]:
    governance_units = _get_governance_event_write_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    if not governance_units:
        return None, [], []

    if governance_context is None and len({unit.unit_type for unit in governance_units}) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "This governance account manages multiple event scopes. "
                "Provide governance_context=SSG, SG, or ORG for event writes."
            ),
        )

    school_wide_units = [unit for unit in governance_units if unit.unit_type == GovernanceUnitType.SSG]
    if school_wide_units:
        return school_wide_units[0], [], []

    department_scopes = {
        unit.department_id
        for unit in governance_units
        if unit.unit_type == GovernanceUnitType.SG and unit.department_id is not None
    }
    if department_scopes:
        if len(department_scopes) != 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple SG event scopes were found for this account. Event writes need a single SG scope.",
            )
        department_id = next(iter(department_scopes))
        matching_unit = next(
            unit
            for unit in governance_units
            if unit.unit_type == GovernanceUnitType.SG and unit.department_id == department_id
        )
        return matching_unit, [department_id], []

    org_scopes = {
        (unit.department_id, unit.program_id)
        for unit in governance_units
        if unit.unit_type == GovernanceUnitType.ORG and unit.program_id is not None
    }
    if org_scopes:
        if len(org_scopes) != 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple ORG event scopes were found for this account. Event writes need a single ORG scope.",
            )
        department_id, program_id = next(iter(org_scopes))
        department_ids = [department_id] if department_id is not None else []
        matching_unit = next(
            unit
            for unit in governance_units
            if unit.unit_type == GovernanceUnitType.ORG
            and unit.department_id == department_id
            and unit.program_id == program_id
        )
        return matching_unit, department_ids, [program_id]

    return None, [], []


__all__ = [name for name in globals() if not name.startswith("__")]
