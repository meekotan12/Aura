"""Use: Contains the main backend rules for automatic event workflow status syncing.
Where to use: Use this from routers, workers, or other services when automatic event workflow status syncing logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.models.event import Event as EventModel
from app.models.event import EventStatus as ModelEventStatus
from app.services.event_attendance_service import finalize_completed_event_attendance
from app.services.event_time_status import get_event_status


EventCompletionFinalizer = Callable[[Session, EventModel], dict[str, int]]


@dataclass(frozen=True)
class EventWorkflowStatusSyncResult:
    changed: bool
    previous_status: ModelEventStatus
    current_status: ModelEventStatus
    computed_time_status: str
    attendance_finalized: bool
    finalization_summary: dict[str, int] | None = None


@dataclass(frozen=True)
class EventWorkflowStatusSyncSummary:
    scanned_events: int
    changed_events: int
    moved_to_upcoming: int
    moved_to_ongoing: int
    moved_to_completed: int
    attendance_finalized_events: int
    absent_records_created: int
    absent_no_timeout_marked: int


def map_time_status_to_workflow_status(time_status: str) -> ModelEventStatus:
    if time_status in {"before_check_in", "early_check_in"}:
        return ModelEventStatus.UPCOMING
    if time_status in {"late_check_in", "absent_check_in", "sign_out_pending", "sign_out_open"}:
        return ModelEventStatus.ONGOING
    return ModelEventStatus.COMPLETED


def get_expected_workflow_status(
    event: EventModel,
    *,
    current_time: datetime | None = None,
) -> tuple[ModelEventStatus, str]:
    time_status = get_event_status(
        start_time=event.start_datetime,
        end_time=event.end_datetime,
        early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
        late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
        sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
        sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
        sign_out_override_until=getattr(event, "sign_out_override_until", None),
        present_until_override_at=getattr(event, "present_until_override_at", None),
        late_until_override_at=getattr(event, "late_until_override_at", None),
        current_time=current_time,
    )
    return map_time_status_to_workflow_status(time_status.event_status), time_status.event_status


def sync_event_workflow_status(
    db: Session,
    event: EventModel,
    *,
    current_time: datetime | None = None,
    completion_finalizer: EventCompletionFinalizer = finalize_completed_event_attendance,
) -> EventWorkflowStatusSyncResult:
    previous_status = event.status
    expected_status, computed_time_status = get_expected_workflow_status(
        event,
        current_time=current_time,
    )

    # Preserve manual terminal states. Cancelled events stay cancelled.
    if previous_status == ModelEventStatus.CANCELLED:
        return EventWorkflowStatusSyncResult(
            changed=False,
            previous_status=previous_status,
            current_status=previous_status,
            computed_time_status=computed_time_status,
            attendance_finalized=False,
        )

    # Completed is treated as sticky so an early manual completion is not reopened.
    if previous_status == ModelEventStatus.COMPLETED and expected_status != ModelEventStatus.COMPLETED:
        return EventWorkflowStatusSyncResult(
            changed=False,
            previous_status=previous_status,
            current_status=previous_status,
            computed_time_status=computed_time_status,
            attendance_finalized=False,
        )

    if previous_status == expected_status:
        return EventWorkflowStatusSyncResult(
            changed=False,
            previous_status=previous_status,
            current_status=previous_status,
            computed_time_status=computed_time_status,
            attendance_finalized=False,
        )

    event.status = expected_status
    finalization_summary: dict[str, int] | None = None
    attendance_finalized = False

    if expected_status == ModelEventStatus.COMPLETED:
        finalization_summary = completion_finalizer(db, event)
        attendance_finalized = True

    return EventWorkflowStatusSyncResult(
        changed=True,
        previous_status=previous_status,
        current_status=expected_status,
        computed_time_status=computed_time_status,
        attendance_finalized=attendance_finalized,
        finalization_summary=finalization_summary,
    )


def sync_scope_event_workflow_statuses(
    db: Session,
    *,
    school_id: int | None = None,
    current_time: datetime | None = None,
) -> list[EventWorkflowStatusSyncResult]:
    query = db.query(EventModel).filter(
        EventModel.status.in_(
            [
                ModelEventStatus.UPCOMING,
                ModelEventStatus.ONGOING,
            ]
        )
    )
    if school_id is not None:
        query = query.filter(EventModel.school_id == school_id)

    results: list[EventWorkflowStatusSyncResult] = []
    for event in query.all():
        results.append(
            sync_event_workflow_status(
                db,
                event,
                current_time=current_time,
            )
        )
    return results


def summarize_event_workflow_status_sync(
    results: list[EventWorkflowStatusSyncResult],
) -> EventWorkflowStatusSyncSummary:
    moved_to_upcoming = 0
    moved_to_ongoing = 0
    moved_to_completed = 0
    attendance_finalized_events = 0
    absent_records_created = 0
    absent_no_timeout_marked = 0

    for result in results:
        if not result.changed:
            continue

        if result.current_status == ModelEventStatus.UPCOMING:
            moved_to_upcoming += 1
        elif result.current_status == ModelEventStatus.ONGOING:
            moved_to_ongoing += 1
        elif result.current_status == ModelEventStatus.COMPLETED:
            moved_to_completed += 1

        if result.attendance_finalized:
            attendance_finalized_events += 1

        if result.finalization_summary:
            absent_records_created += int(result.finalization_summary.get("created_absent", 0))
            absent_no_timeout_marked += int(
                result.finalization_summary.get("marked_absent_no_timeout", 0)
            )

    return EventWorkflowStatusSyncSummary(
        scanned_events=len(results),
        changed_events=sum(1 for result in results if result.changed),
        moved_to_upcoming=moved_to_upcoming,
        moved_to_ongoing=moved_to_ongoing,
        moved_to_completed=moved_to_completed,
        attendance_finalized_events=attendance_finalized_events,
        absent_records_created=absent_records_created,
        absent_no_timeout_marked=absent_no_timeout_marked,
    )
