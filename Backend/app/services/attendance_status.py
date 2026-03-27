"""Use: Contains the main backend rules for attendance status decisions and counters.
Where to use: Use this from routers, workers, or other services when attendance status decisions and counters logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.services.event_time_status import (
    DEFAULT_EVENT_TIMEZONE,
    get_event_timezone,
    normalize_event_datetime,
    normalize_late_threshold_minutes,
)


ALL_ATTENDANCE_STATUS_VALUES: tuple[str, ...] = ("present", "late", "absent", "excused")
ATTENDED_STATUS_VALUES: tuple[str, ...] = ("present", "late")
ATTENDANCE_DISPLAY_STATUS_VALUES: tuple[str, ...] = (
    "present",
    "late",
    "absent",
    "excused",
    "incomplete",
)


def normalize_attendance_status(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip().lower()


def is_attended_status(value: Any) -> bool:
    return normalize_attendance_status(value) in ATTENDED_STATUS_VALUES


def is_attendance_completed(*, time_out: datetime | None) -> bool:
    return time_out is not None


def resolve_attendance_display_status(
    *,
    stored_status: Any,
    time_out: datetime | None,
) -> str:
    if not is_attendance_completed(time_out=time_out):
        return "incomplete"

    normalized_status = normalize_attendance_status(stored_status)
    if normalized_status in ALL_ATTENDANCE_STATUS_VALUES:
        return normalized_status
    return "absent"


def is_completed_attended_status(
    *,
    stored_status: Any,
    time_out: datetime | None,
) -> bool:
    return is_attendance_completed(time_out=time_out) and is_attended_status(stored_status)


def empty_attendance_status_counts() -> dict[str, int]:
    return {status: 0 for status in ALL_ATTENDANCE_STATUS_VALUES}


def empty_attendance_display_status_counts() -> dict[str, int]:
    return {status: 0 for status in ATTENDANCE_DISPLAY_STATUS_VALUES}


def normalize_attendance_datetime(
    value: datetime,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(get_event_timezone(timezone_name))


def late_cutoff_datetime(
    event_start: datetime,
    late_threshold_minutes: Any,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    localized_start = normalize_event_datetime(event_start, timezone_name)
    return localized_start + timedelta(minutes=normalize_late_threshold_minutes(late_threshold_minutes))


def is_late_arrival(
    *,
    event_start: datetime,
    time_in: datetime,
    late_threshold_minutes: Any,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> bool:
    localized_time_in = normalize_attendance_datetime(time_in, timezone_name)
    localized_start = normalize_event_datetime(event_start, timezone_name)
    if localized_time_in < localized_start:
        return False
    return localized_time_in <= late_cutoff_datetime(
        event_start,
        late_threshold_minutes,
        timezone_name=timezone_name,
    )


def finalize_completed_attendance_status(
    *,
    check_in_status: Any,
    check_out_status: Any,
) -> tuple[str, str | None]:
    normalized_check_in_status = normalize_attendance_status(check_in_status)
    normalized_check_out_status = normalize_attendance_status(check_out_status)

    if normalized_check_out_status != "present":
        return (
            "absent",
            "Attendance was marked absent because sign-out was missing or outside the allowed sign-out window.",
        )

    if normalized_check_in_status in {"present", "late", "absent"}:
        return normalized_check_in_status, None

    return (
        "absent",
        "Attendance was marked absent because the sign-in status could not be determined.",
    )
