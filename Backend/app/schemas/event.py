"""Use: Defines request and response data shapes for event API data.
Where to use: Use this in routers and services when validating or returning event API data.
Role: Schema layer. It keeps API payloads clear and typed.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator
from datetime import datetime
from enum import Enum

from app.core.event_defaults import (
    DEFAULT_EVENT_EARLY_CHECK_IN_MINUTES,
    DEFAULT_EVENT_LATE_THRESHOLD_MINUTES,
    DEFAULT_EVENT_SIGN_OUT_GRACE_MINUTES,
)
from app.schemas.attendance import Attendance, AttendanceStatus
from app.schemas.department import Department
from app.schemas.program import Program

class EventStatus(str, Enum):
    upcoming = "upcoming"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"


class EventTimeStatus(str, Enum):
    before_check_in = "before_check_in"
    early_check_in = "early_check_in"
    late_check_in = "late_check_in"
    absent_check_in = "absent_check_in"
    sign_out_pending = "sign_out_pending"
    sign_out_open = "sign_out_open"
    closed = "closed"


class EventTimeStatusInfo(BaseModel):
    event_status: EventTimeStatus
    current_time: datetime
    check_in_opens_at: datetime
    start_time: datetime
    end_time: datetime
    late_threshold_time: datetime
    attendance_override_active: bool
    effective_present_until_at: datetime
    effective_late_until_at: datetime
    sign_out_opens_at: datetime
    normal_sign_out_closes_at: datetime
    effective_sign_out_closes_at: datetime
    timezone_name: str


class EventAttendanceDecisionInfo(BaseModel):
    action: str = "check_in"
    event_status: EventTimeStatus
    attendance_allowed: bool
    attendance_status: Optional[AttendanceStatus] = None
    reason_code: Optional[str] = None
    message: str
    current_time: datetime
    check_in_opens_at: datetime
    start_time: datetime
    end_time: datetime
    late_threshold_time: datetime
    attendance_override_active: bool
    effective_present_until_at: datetime
    effective_late_until_at: datetime
    sign_out_opens_at: datetime
    normal_sign_out_closes_at: datetime
    effective_sign_out_closes_at: datetime
    timezone_name: str


class EventLocationVerificationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, gt=0, le=5000)


class SignOutOpenEarlyRequest(BaseModel):
    use_sign_out_grace_minutes: bool = Field(
        default=True,
        description="If true, close early sign-out using the event's current sign_out_grace_minutes value.",
    )
    close_after_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=1440,
        description="Custom number of minutes to keep sign-out open after ending the event early.",
    )

    @model_validator(mode="after")
    def validate_close_after_minutes(self) -> "SignOutOpenEarlyRequest":
        if self.use_sign_out_grace_minutes:
            return self
        if self.close_after_minutes is None:
            raise ValueError(
                "close_after_minutes is required when use_sign_out_grace_minutes is false."
            )
        return self


class EventLocationVerificationResponse(BaseModel):
    ok: bool
    reason: Optional[str] = None
    distance_m: float
    effective_distance_m: Optional[float] = None
    radius_m: float
    accuracy_m: Optional[float] = None
    time_status: Optional[EventTimeStatusInfo] = None
    attendance_decision: Optional[EventAttendanceDecisionInfo] = None

class EventBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    geo_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    geo_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    geo_radius_m: Optional[float] = Field(default=None, gt=0, le=5000)
    geo_required: bool = False
    geo_max_accuracy_m: Optional[float] = Field(default=None, gt=0, le=1000)
    early_check_in_minutes: int = Field(
        default=DEFAULT_EVENT_EARLY_CHECK_IN_MINUTES,
        ge=0,
        le=1440,
    )
    late_threshold_minutes: int = Field(
        default=DEFAULT_EVENT_LATE_THRESHOLD_MINUTES,
        ge=0,
        le=1440,
    )
    sign_out_grace_minutes: int = Field(
        default=DEFAULT_EVENT_SIGN_OUT_GRACE_MINUTES,
        ge=0,
        le=1440,
    )
    sign_out_open_delay_minutes: int = Field(
        default=0,
        ge=0,
        le=1440,
    )
    start_datetime: datetime
    end_datetime: datetime
    status: EventStatus = EventStatus.upcoming

    @model_validator(mode="after")
    def validate_sign_out_window(self) -> "EventBase":
        if self.sign_out_open_delay_minutes > self.sign_out_grace_minutes:
            raise ValueError(
                "sign_out_open_delay_minutes cannot be greater than sign_out_grace_minutes."
            )
        return self

class EventCreate(EventBase):
    department_ids: List[int] = Field(default_factory=list)
    program_ids: List[int] = Field(default_factory=list)

class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, min_length=1, max_length=200)
    geo_latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    geo_longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    geo_radius_m: Optional[float] = Field(default=None, gt=0, le=5000)
    geo_required: Optional[bool] = None
    geo_max_accuracy_m: Optional[float] = Field(default=None, gt=0, le=1000)
    early_check_in_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    late_threshold_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    sign_out_grace_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    sign_out_open_delay_minutes: Optional[int] = Field(default=None, ge=0, le=1440)
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    status: Optional[EventStatus] = None
    department_ids: Optional[List[int]] = None
    program_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def validate_sign_out_window(self) -> "EventUpdate":
        if (
            self.sign_out_open_delay_minutes is not None
            and self.sign_out_grace_minutes is not None
            and self.sign_out_open_delay_minutes > self.sign_out_grace_minutes
        ):
            raise ValueError(
                "sign_out_open_delay_minutes cannot be greater than sign_out_grace_minutes."
            )
        return self

class Event(EventBase):
    id: int
    school_id: int
    present_until_override_at: Optional[datetime] = None
    late_until_override_at: Optional[datetime] = None
    sign_out_override_until: Optional[datetime] = None
    departments: List[Department] = Field(default_factory=list)
    programs: List[Program] = Field(default_factory=list)
    
    # Computed fields for IDs
    @computed_field
    def department_ids(self) -> List[int]:
        return [dept.id for dept in self.departments]
    
    @computed_field
    def program_ids(self) -> List[int]:
        return [program.id for program in self.programs]
    
    model_config = ConfigDict(from_attributes=True)

class EventWithRelations(Event):
    departments: List[Department] = Field(default_factory=list)
    programs: List[Program] = Field(default_factory=list)
    attendances: List[Attendance] = Field(
        default_factory=list,
        description="Attendance records for this event"
    )
    attendance_summary: dict = Field(
        default_factory=dict,
        description="Counts by attendance status"
    )
    
    model_config = ConfigDict(from_attributes=True)

class EventPaginated(BaseModel):
    total: int
    items: List[Event]
    skip: int
    limit: int
