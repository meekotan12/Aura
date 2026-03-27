"""Use: Handles user notifications API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs user notifications features.
Role: Router layer. It receives HTTP requests, checks access rules, and returns API responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import (
    get_current_admin_or_campus_admin,
    get_current_application_user,
    has_any_role,
)
from app.core.dependencies import get_db
from app.models.platform_features import NotificationLog
from app.models.user import User
from app.schemas.notification import (
    NotificationDispatchSummary,
    NotificationLogItem,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationTestRequest,
    SecurityNotificationRequest,
)
from app.services.notification_center_service import (
    dispatch_low_attendance_notifications,
    dispatch_event_reminder_notifications,
    dispatch_missed_event_notifications,
    get_notification_inbox_for_user,
    get_or_create_notification_preference,
    send_account_security_notification,
    send_notification_to_user,
)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _resolve_school_scope(current_user: User, requested_school_id: int | None = None) -> int:
    actor_school_id = getattr(current_user, "school_id", None)
    is_platform_admin = has_any_role(current_user, ["admin"]) and actor_school_id is None
    if is_platform_admin:
        if requested_school_id is None:
            raise HTTPException(status_code=400, detail="school_id is required for platform admin actions")
        return requested_school_id
    if actor_school_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a school")
    return actor_school_id


@router.get("/preferences/me", response_model=NotificationPreferenceResponse)
def get_my_notification_preferences(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    pref = get_or_create_notification_preference(db, user_id=current_user.id)
    db.commit()
    db.refresh(pref)
    return pref


@router.put("/preferences/me", response_model=NotificationPreferenceResponse)
def update_my_notification_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    pref = get_or_create_notification_preference(db, user_id=current_user.id)

    for field in [
        "email_enabled",
        "sms_enabled",
        "sms_number",
        "notify_missed_events",
        "notify_low_attendance",
        "notify_account_security",
        "notify_subscription",
    ]:
        value = getattr(payload, field)
        if value is not None:
            setattr(pref, field, value)

    db.commit()
    db.refresh(pref)
    return pref


@router.get("/logs", response_model=list[NotificationLogItem])
def list_notification_logs(
    school_id: int | None = Query(default=None),
    category: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    user_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    actor_school_id = getattr(current_user, "school_id", None)
    is_platform_admin = has_any_role(current_user, ["admin"]) and actor_school_id is None

    query = db.query(NotificationLog)
    if not is_platform_admin:
        if actor_school_id is None:
            raise HTTPException(status_code=403, detail="User is not assigned to a school")
        query = query.filter(NotificationLog.school_id == actor_school_id)
    elif school_id is not None:
        query = query.filter(NotificationLog.school_id == school_id)

    if category:
        query = query.filter(NotificationLog.category == category)
    if status_value:
        query = query.filter(NotificationLog.status == status_value)
    if user_id is not None:
        query = query.filter(NotificationLog.user_id == user_id)

    return (
        query.order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/inbox/me", response_model=list[NotificationLogItem])
def list_my_notification_inbox(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    return get_notification_inbox_for_user(
        db,
        user_id=current_user.id,
        limit=limit,
    )


@router.post("/test", response_model=NotificationDispatchSummary)
def send_test_notification(
    payload: NotificationTestRequest,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    message = payload.message or "This is a test notification from VALID8."
    status_value = send_notification_to_user(
        db,
        user=current_user,
        school_id=getattr(current_user, "school_id", None),
        category="test_notification",
        subject="VALID8 Test Notification",
        message=message,
        metadata_json={"triggered_by": current_user.id, "channel_hint": payload.channel},
    )
    db.commit()
    return NotificationDispatchSummary(
        processed_users=1,
        sent=1 if status_value == "sent" else 0,
        failed=1 if status_value == "failed" else 0,
        skipped=1 if status_value == "skipped" else 0,
        category="test_notification",
    )


@router.post("/dispatch/missed-events", response_model=NotificationDispatchSummary)
def dispatch_missed_events_notifications(
    school_id: int | None = Query(default=None),
    lookback_days: int = Query(default=14, ge=1, le=90),
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    scoped_school_id = _resolve_school_scope(current_user, school_id)

    result = dispatch_missed_event_notifications(
        db,
        school_id=scoped_school_id,
        lookback_days=lookback_days,
    )
    db.commit()
    return NotificationDispatchSummary(category="missed_events", **result)


@router.post("/dispatch/low-attendance", response_model=NotificationDispatchSummary)
def dispatch_low_attendance_alerts(
    school_id: int | None = Query(default=None),
    threshold_percent: float = Query(default=75.0, ge=1, le=100),
    min_records: int = Query(default=3, ge=1, le=100),
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    scoped_school_id = _resolve_school_scope(current_user, school_id)

    result = dispatch_low_attendance_notifications(
        db,
        school_id=scoped_school_id,
        threshold_percent=threshold_percent,
        min_records=min_records,
    )
    db.commit()
    return NotificationDispatchSummary(category="low_attendance", **result)


@router.post("/dispatch/event-reminders", response_model=NotificationDispatchSummary)
def dispatch_event_reminders(
    school_id: int | None = Query(default=None),
    lead_hours: int = Query(default=24, ge=1, le=168),
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    scoped_school_id = _resolve_school_scope(current_user, school_id)
    result = dispatch_event_reminder_notifications(
        db,
        school_id=scoped_school_id,
        lead_hours=lead_hours,
    )
    db.commit()
    return NotificationDispatchSummary(category="event_reminder", **result)


@router.post("/dispatch/security", response_model=NotificationDispatchSummary)
def dispatch_security_notification(
    payload: SecurityNotificationRequest,
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    actor_school_id = getattr(current_user, "school_id", None)
    is_platform_admin = has_any_role(current_user, ["admin"]) and actor_school_id is None
    if not is_platform_admin:
        if actor_school_id is None or target_user.school_id != actor_school_id:
            raise HTTPException(status_code=404, detail="Target user not found")

    status_value = send_account_security_notification(
        db,
        user=target_user,
        subject=payload.subject,
        message=payload.message,
        metadata_json={"triggered_by": current_user.id},
    )
    db.commit()
    return NotificationDispatchSummary(
        processed_users=1,
        sent=1 if status_value == "sent" else 0,
        failed=1 if status_value == "failed" else 0,
        skipped=1 if status_value == "skipped" else 0,
        category="account_security",
    )

