"""Use: Defines database models for events and event scope settings.
Where to use: Use this when the backend needs to store or load events and event scope settings data.
Role: Model layer. It maps Python objects to database tables and relationships.
"""

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from app.core.event_defaults import (
    DEFAULT_EVENT_EARLY_CHECK_IN_MINUTES,
    DEFAULT_EVENT_LATE_THRESHOLD_MINUTES,
    DEFAULT_EVENT_SIGN_OUT_GRACE_MINUTES,
)
from app.models.base import Base
from app.models.associations import event_department_association, event_program_association

class EventStatus(PyEnum):
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    geo_latitude = Column(Float, nullable=True)
    geo_longitude = Column(Float, nullable=True)
    geo_radius_m = Column(Float, nullable=True)
    geo_required = Column(Boolean, nullable=False, default=False)
    geo_max_accuracy_m = Column(Float, nullable=True)
    early_check_in_minutes = Column(
        Integer,
        nullable=False,
        default=DEFAULT_EVENT_EARLY_CHECK_IN_MINUTES,
    )
    late_threshold_minutes = Column(
        Integer,
        nullable=False,
        default=DEFAULT_EVENT_LATE_THRESHOLD_MINUTES,
    )
    sign_out_grace_minutes = Column(
        Integer,
        nullable=False,
        default=DEFAULT_EVENT_SIGN_OUT_GRACE_MINUTES,
    )
    sign_out_open_delay_minutes = Column(
        Integer,
        nullable=False,
        default=0,
    )
    sign_out_override_until = Column(DateTime, nullable=True)
    present_until_override_at = Column(DateTime, nullable=True)
    late_until_override_at = Column(DateTime, nullable=True)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status = Column(Enum(EventStatus), nullable=False, default=EventStatus.UPCOMING)
    
    
    # Many-to-many relationships
    departments = relationship(
        "Department", 
        secondary=event_department_association, 
        back_populates="events",
       
    )
    programs = relationship(
        "Program", 
        secondary=event_program_association, 
        back_populates="events",
       
    )
    attendances = relationship(
       "Attendance",
       back_populates="event",
       cascade="all, delete-orphan"
    )
    school = relationship("School", back_populates="events")
