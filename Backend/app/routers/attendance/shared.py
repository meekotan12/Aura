"""Shared helpers for the attendance router package."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import String, and_, case, func, or_, text
from sqlalchemy.orm import Session, joinedload

from app.core.dependencies import get_db
from app.core.security import get_current_user, get_school_id_or_403, has_any_role
from app.models.attendance import Attendance as AttendanceModel
from app.models.event import Event, EventStatus
from app.models.governance_hierarchy import GovernanceUnitType, PermissionCode
from app.models.program import Program
from app.models.user import StudentProfile, User, User as UserModel
from app.schemas.attendance import (
    Attendance,
    AttendanceReportResponse,
    AttendanceStatus,
    AttendanceWithStudent,
    StudentAttendanceDetail,
    StudentAttendanceRecord,
    StudentAttendanceReport,
    StudentAttendanceResponse,
    StudentAttendanceSummary,
    StudentListItem,
)
from app.schemas.attendance_requests import BulkAttendanceRequest, ManualAttendanceRequest
from app.services import governance_hierarchy_service
from app.services.attendance_status import (
    ATTENDED_STATUS_VALUES,
    empty_attendance_display_status_counts,
    empty_attendance_status_counts,
    finalize_completed_attendance_status,
    is_attendance_completed,
    is_completed_attended_status,
    is_attended_status,
    normalize_attendance_status,
    resolve_attendance_display_status,
)
from app.services.event_time_status import get_attendance_decision, get_sign_out_decision
from app.services.event_workflow_status import sync_event_workflow_status

logger = logging.getLogger(__name__)


def _get_attendance_governance_units(
    db: Session,
    *,
    current_user: UserModel,
    governance_context: GovernanceUnitType | None,
):
    if has_any_role(current_user, ["admin", "campus_admin"]):
        return []

    return governance_hierarchy_service.get_governance_units_with_permission(
        db,
        current_user=current_user,
        permission_code=PermissionCode.MANAGE_ATTENDANCE,
        unit_type=governance_context,
    )


def _apply_student_scope_filters(query, governance_units):
    if not governance_units:
        return query
    if any(unit.department_id is None and unit.program_id is None for unit in governance_units):
        return query

    filters = []
    for governance_unit in governance_units:
        condition_parts = []
        if governance_unit.department_id is not None:
            condition_parts.append(StudentProfile.department_id == governance_unit.department_id)
        if governance_unit.program_id is not None:
            condition_parts.append(StudentProfile.program_id == governance_unit.program_id)
        if condition_parts:
            filters.append(and_(*condition_parts))

    if not filters:
        return query.filter(text("1=0"))
    return query.filter(or_(*filters))


def _event_matches_governance_units(event: Event, governance_units) -> bool:
    if not governance_units:
        return True

    department_ids = {department.id for department in event.departments}
    program_ids = {program.id for program in event.programs}
    return any(
        governance_hierarchy_service.governance_unit_matches_event_scope(
            governance_unit,
            department_ids=department_ids,
            program_ids=program_ids,
        )
        for governance_unit in governance_units
    )


def _ensure_event_in_attendance_scope(event: Event, governance_units) -> None:
    if governance_units and not _event_matches_governance_units(event, governance_units):
        raise HTTPException(404, "Event not found")


def _ensure_student_in_attendance_scope(student: StudentProfile, governance_units) -> None:
    if governance_units and not governance_hierarchy_service.governance_units_match_student_scope(
        governance_units,
        department_id=student.department_id,
        program_id=student.program_id,
    ):
        raise HTTPException(404, "Student not found")


def _ensure_student_is_event_participant(student: StudentProfile, event: Event) -> None:
    event_program_ids = {program.id for program in event.programs}
    event_department_ids = {department.id for department in event.departments}
    if event_program_ids and student.program_id not in event_program_ids:
        raise HTTPException(400, "Student is outside the event program scope")
    if event_department_ids and student.department_id not in event_department_ids:
        raise HTTPException(400, "Student is outside the event department scope")


def _get_event_ids_in_attendance_scope(db: Session, *, school_id: int, governance_units) -> list[int]:
    if not governance_units:
        return [
            event_id
            for (event_id,) in db.query(Event.id).filter(Event.school_id == school_id).all()
        ]

    events = (
        db.query(Event)
        .options(
            joinedload(Event.departments),
            joinedload(Event.programs),
        )
        .filter(Event.school_id == school_id)
        .all()
    )
    return [event.id for event in events if _event_matches_governance_units(event, governance_units)]


def _get_event_in_school_or_404(db: Session, event_id: int, school_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id, Event.school_id == school_id).first()
    if not event:
        raise HTTPException(404, "Event not found")
    result = sync_event_workflow_status(db, event)
    if result.changed:
        db.commit()
        db.refresh(event)
    return event


def _get_event_attendance_decision(event: Event) -> dict[str, Any]:
    decision = get_attendance_decision(
        start_time=event.start_datetime,
        end_time=event.end_datetime,
        early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
        late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
        sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
        sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
        sign_out_override_until=getattr(event, "sign_out_override_until", None),
        present_until_override_at=getattr(event, "present_until_override_at", None),
        late_until_override_at=getattr(event, "late_until_override_at", None),
    )
    return _serialize_attendance_decision(decision)


def _get_event_sign_out_decision(event: Event) -> dict[str, Any]:
    decision = get_sign_out_decision(
        start_time=event.start_datetime,
        end_time=event.end_datetime,
        early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
        late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
        sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
        sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
        sign_out_override_until=getattr(event, "sign_out_override_until", None),
        present_until_override_at=getattr(event, "present_until_override_at", None),
        late_until_override_at=getattr(event, "late_until_override_at", None),
    )
    return _serialize_attendance_decision(decision)


def _serialize_attendance_decision(decision) -> dict[str, Any]:
    payload = decision.to_dict()
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


def _attendance_display_status_value(attendance: AttendanceModel) -> str:
    return resolve_attendance_display_status(
        stored_status=attendance.status,
        time_out=attendance.time_out,
    )


def _attendance_completion_state_value(attendance: AttendanceModel) -> str:
    return "completed" if is_attendance_completed(time_out=attendance.time_out) else "incomplete"


def _attendance_is_valid_value(attendance: AttendanceModel) -> bool:
    return is_completed_attended_status(
        stored_status=attendance.status,
        time_out=attendance.time_out,
    )


def _attendance_matches_status_filter(
    attendance: AttendanceModel,
    status: AttendanceStatus | None,
) -> bool:
    if status is None:
        return True

    return _attendance_display_status_value(attendance) == normalize_attendance_status(status)


def _serialize_attendance_model(attendance: AttendanceModel) -> Attendance:
    payload = Attendance.model_validate(attendance, from_attributes=True)
    return payload.model_copy(
        update={
            "display_status": _attendance_display_status_value(attendance),
            "completion_state": _attendance_completion_state_value(attendance),
            "is_valid_attendance": _attendance_is_valid_value(attendance),
        }
    )


def _serialize_attendance_with_student(
    attendance: AttendanceModel,
    *,
    student_id: str,
    student_name: str,
) -> AttendanceWithStudent:
    return AttendanceWithStudent(
        attendance=_serialize_attendance_model(attendance),
        student_id=student_id,
        student_name=student_name,
    )


def _build_student_attendance_record(
    attendance: AttendanceModel,
    *,
    event_name: str,
) -> StudentAttendanceRecord:
    duration = None
    if attendance.time_in and attendance.time_out:
        duration = int((attendance.time_out - attendance.time_in).total_seconds() / 60)

    return StudentAttendanceRecord(
        id=attendance.id,
        event_id=attendance.event_id,
        event_name=event_name,
        time_in=attendance.time_in,
        time_out=attendance.time_out,
        check_in_status=attendance.check_in_status,
        check_out_status=attendance.check_out_status,
        status=attendance.status,
        display_status=_attendance_display_status_value(attendance),
        completion_state=_attendance_completion_state_value(attendance),
        is_valid_attendance=_attendance_is_valid_value(attendance),
        method=attendance.method,
        notes=attendance.notes,
        duration_minutes=duration,
    )


def _build_student_attendance_detail(attendance: AttendanceModel) -> StudentAttendanceDetail:
    duration = None
    if attendance.time_in and attendance.time_out:
        duration = int((attendance.time_out - attendance.time_in).total_seconds() / 60)

    return StudentAttendanceDetail(
        id=attendance.id,
        event_id=attendance.event_id,
        event_name=attendance.event.name,
        event_location=attendance.event.location,
        event_date=attendance.event.start_datetime,
        time_in=attendance.time_in,
        time_out=attendance.time_out,
        check_in_status=attendance.check_in_status,
        check_out_status=attendance.check_out_status,
        status=attendance.status,
        display_status=_attendance_display_status_value(attendance),
        completion_state=_attendance_completion_state_value(attendance),
        is_valid_attendance=_attendance_is_valid_value(attendance),
        method=attendance.method,
        notes=attendance.notes,
        duration_minutes=duration,
    )


def _active_attendance_for_student_event(
    db: Session,
    *,
    student_profile_id: int,
    event_id: int,
) -> AttendanceModel | None:
    return (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student_profile_id,
            AttendanceModel.event_id == event_id,
            AttendanceModel.time_out.is_(None),
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )


def _complete_attendance_sign_out(
    attendance: AttendanceModel,
    *,
    recorded_at: datetime,
) -> int:
    attendance.time_out = recorded_at
    attendance.check_out_status = "present"
    attendance.status, final_note = finalize_completed_attendance_status(
        check_in_status=attendance.check_in_status or attendance.status,
        check_out_status=attendance.check_out_status,
    )
    attendance.notes = final_note
    duration_seconds = (attendance.time_out - attendance.time_in).total_seconds()
    return int(max(0, duration_seconds / 60))


def _ensure_attendance_management_access(db: Session, current_user: UserModel) -> None:
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

    raise HTTPException(403, "Insufficient permissions")


def _ensure_event_report_access(db: Session, current_user: UserModel) -> None:
    _ensure_attendance_management_access(db, current_user)


def _ensure_attendance_report_access(db: Session, current_user: UserModel) -> None:
    _ensure_attendance_management_access(db, current_user)


def _ensure_attendance_operator_access(db: Session, current_user: UserModel) -> None:
    _ensure_attendance_management_access(db, current_user)


__all__ = [name for name in globals() if not name.startswith("__")]
