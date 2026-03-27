"""Background tasks for event attendance."""

from __future__ import annotations

from datetime import datetime

from app.database import SessionLocal
from app.services.event_attendance_service import mark_absent_attendance
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.mark_event_absentees")
def mark_event_absentees_task() -> int:
    with SessionLocal() as db:
        count = mark_absent_attendance(db, now=datetime.utcnow())
        db.commit()
        return count
