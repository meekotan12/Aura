from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.models.base import Base


class EventAttendance(Base):
    __tablename__ = "event_attendance"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_attendance_event_user"),
        Index("ix_event_attendance_event_id", "event_id"),
        Index("ix_event_attendance_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    sign_in_time = Column(DateTime, nullable=True)
    sign_out_time = Column(DateTime, nullable=True)
    attendance_status = Column(String(20), nullable=False, default="absent")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event")
    user = relationship("User")
