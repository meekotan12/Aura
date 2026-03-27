"""Attendance-facing event query routes for the event router package."""

from .shared import *  # noqa: F403
from app.services.attendance_status import resolve_attendance_display_status, is_completed_attended_status

router = APIRouter()


@router.get("/{event_id}/attendees")
def get_event_attendees(
    event_id: int,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    event = (
        _school_scoped_event_query(db, _actor_school_scope_id(current_user))
        .filter(EventModel.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _ensure_event_is_visible_in_governance_scope(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )

    _persist_event_status_sync(db, event)
    attendances = db.query(AttendanceModel).filter(AttendanceModel.event_id == event_id).order_by(
        AttendanceModel.status,
        AttendanceModel.time_in,
    ).all()
    if status:
        normalized_filter = str(status).strip().lower()
        attendances = [
            attendance
            for attendance in attendances
            if resolve_attendance_display_status(
                stored_status=attendance.status,
                time_out=attendance.time_out,
            ) == normalized_filter
        ]

    return attendances[skip : skip + limit]


@router.get("/{event_id}/stats")
def get_event_stats(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    event = (
        _school_scoped_event_query(db, _actor_school_scope_id(current_user))
        .filter(EventModel.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _ensure_event_is_visible_in_governance_scope(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )

    _persist_event_status_sync(db, event)
    attendances = db.query(AttendanceModel).filter(
        AttendanceModel.event_id == event_id
    ).all()
    total = len(attendances)
    counts: dict[str, int] = {}
    for attendance in attendances:
        display_status = resolve_attendance_display_status(
            stored_status=attendance.status,
            time_out=attendance.time_out,
        )
        if display_status in {"present", "late"} and not is_completed_attended_status(
            stored_status=attendance.status,
            time_out=attendance.time_out,
        ):
            display_status = "incomplete"
        counts[display_status] = counts.get(display_status, 0) + 1

    return {
        "total": total,
        "statuses": {
            status_name: {
                "count": count,
                "percentage": round((count / total) * 100, 2) if total else 0,
            }
            for status_name, count in counts.items()
        },
    }
