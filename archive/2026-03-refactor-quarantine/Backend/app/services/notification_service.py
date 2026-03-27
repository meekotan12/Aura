from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    user_id: int,
    school_id: int,
    title: str,
    message: str,
    type_value: str = "event",
    related_id: int | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        school_id=school_id,
        title=title,
        message=message,
        type=type_value,
        related_id=related_id,
        is_read=False,
    )
    db.add(row)
    return row
