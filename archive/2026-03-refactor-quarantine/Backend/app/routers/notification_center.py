from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_current_user_with_roles
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification_center import (
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationOut,
)

router = APIRouter(prefix="/api/notifications-center", tags=["notifications-center"])


@router.get("/me", response_model=NotificationListResponse)
def list_my_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db),
):
    if current_user.school_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a school")

    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .scalar()
        or 0
    )
    items = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
    return NotificationListResponse(
        unread_count=int(unread_count),
        items=[NotificationOut.model_validate(item) for item in items],
    )


@router.post("/me/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_read(
    payload: NotificationMarkReadRequest,
    current_user: User = Depends(get_current_user_with_roles),
    db: Session = Depends(get_db),
):
    if current_user.school_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a school")

    ids = list(dict.fromkeys(payload.ids))
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.id.in_(ids))
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return None
