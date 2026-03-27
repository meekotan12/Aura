"""Use: Contains the main backend rules for computed event time windows.
Where to use: Use this from routers, workers, or other services when computed event time windows logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_EVENT_TIMEZONE = "Asia/Manila"
DEFAULT_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES = 20


@dataclass(frozen=True)
class AttendanceWindowCutoffResult:
    attendance_override_active: bool
    effective_present_until_at: datetime
    effective_late_until_at: datetime


@dataclass(frozen=True)
class EventTimeStatusResult:
    event_status: str
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttendanceDecisionResult:
    action: str
    event_status: str
    attendance_allowed: bool
    attendance_status: str | None
    reason_code: str | None
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_event_timezone(timezone_name: str = DEFAULT_EVENT_TIMEZONE) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unsupported timezone: {timezone_name}") from exc


def normalize_event_datetime(
    value: datetime,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    zone = get_event_timezone(timezone_name)
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def normalize_optional_event_datetime(
    value: datetime | None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime | None:
    if value is None:
        return None
    return normalize_event_datetime(value, timezone_name)


def normalize_window_minutes(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, minutes)


def normalize_late_threshold_minutes(value: Any) -> int:
    return normalize_window_minutes(value)


def normalize_early_check_in_minutes(value: Any) -> int:
    return normalize_window_minutes(value)


def normalize_sign_out_grace_minutes(value: Any) -> int:
    return normalize_window_minutes(value)


def normalize_sign_out_open_delay_minutes(value: Any) -> int:
    return normalize_window_minutes(value)


def get_check_in_opens_at(
    start_time: datetime,
    early_check_in_minutes: Any = 0,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    return normalize_event_datetime(start_time, timezone_name) - timedelta(
        minutes=normalize_early_check_in_minutes(early_check_in_minutes)
    )


def get_late_threshold_time(
    start_time: datetime,
    late_threshold_minutes: Any = 0,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    return normalize_event_datetime(start_time, timezone_name) + timedelta(
        minutes=normalize_late_threshold_minutes(late_threshold_minutes)
    )


def get_normal_sign_out_close_time(
    end_time: datetime,
    sign_out_grace_minutes: Any = 0,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    return normalize_event_datetime(end_time, timezone_name) + timedelta(
        minutes=normalize_sign_out_grace_minutes(sign_out_grace_minutes)
    )


def get_sign_out_open_time(
    end_time: datetime,
    sign_out_open_delay_minutes: Any = 0,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    return normalize_event_datetime(end_time, timezone_name) + timedelta(
        minutes=normalize_sign_out_open_delay_minutes(sign_out_open_delay_minutes)
    )


def get_effective_sign_out_close_time(
    end_time: datetime,
    sign_out_grace_minutes: Any = 0,
    sign_out_override_until: datetime | None = None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> datetime:
    normal_close_time = get_normal_sign_out_close_time(
        end_time,
        sign_out_grace_minutes,
        timezone_name=timezone_name,
    )
    localized_override = normalize_optional_event_datetime(
        sign_out_override_until,
        timezone_name,
    )
    if localized_override is None:
        return normal_close_time
    return min(normal_close_time, localized_override)


def resolve_attendance_window_cutoffs(
    *,
    start_time: datetime,
    late_threshold_minutes: Any = 0,
    present_until_override_at: datetime | None = None,
    late_until_override_at: datetime | None = None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> AttendanceWindowCutoffResult:
    localized_start = normalize_event_datetime(start_time, timezone_name)
    scheduled_late_until = get_late_threshold_time(
        localized_start,
        late_threshold_minutes,
        timezone_name=timezone_name,
    )
    localized_present_override = normalize_optional_event_datetime(
        present_until_override_at,
        timezone_name,
    )
    localized_late_override = normalize_optional_event_datetime(
        late_until_override_at,
        timezone_name,
    )

    if (
        localized_present_override is not None
        and localized_late_override is not None
        and localized_present_override > localized_start
        and localized_late_override >= localized_present_override
    ):
        return AttendanceWindowCutoffResult(
            attendance_override_active=True,
            effective_present_until_at=localized_present_override,
            effective_late_until_at=localized_late_override,
        )

    return AttendanceWindowCutoffResult(
        attendance_override_active=False,
        effective_present_until_at=localized_start,
        effective_late_until_at=scheduled_late_until,
    )


def get_event_status(
    *,
    start_time: datetime,
    end_time: datetime,
    early_check_in_minutes: Any = 0,
    late_threshold_minutes: Any = 0,
    sign_out_grace_minutes: Any = 0,
    sign_out_open_delay_minutes: Any = 0,
    sign_out_override_until: datetime | None = None,
    present_until_override_at: datetime | None = None,
    late_until_override_at: datetime | None = None,
    current_time: datetime | None = None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> EventTimeStatusResult:
    zone = get_event_timezone(timezone_name)
    localized_start = normalize_event_datetime(start_time, timezone_name)
    localized_end = normalize_event_datetime(end_time, timezone_name)
    if localized_end <= localized_start:
        raise ValueError("end_time must be after start_time")

    localized_now = (
        datetime.now(zone)
        if current_time is None
        else normalize_event_datetime(current_time, timezone_name)
    )
    check_in_opens_at = get_check_in_opens_at(
        localized_start,
        early_check_in_minutes,
        timezone_name=timezone_name,
    )
    late_threshold_time = get_late_threshold_time(
        localized_start,
        late_threshold_minutes,
        timezone_name=timezone_name,
    )
    attendance_cutoffs = resolve_attendance_window_cutoffs(
        start_time=localized_start,
        late_threshold_minutes=late_threshold_minutes,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        timezone_name=timezone_name,
    )
    sign_out_opens_at = get_sign_out_open_time(
        localized_end,
        sign_out_open_delay_minutes,
        timezone_name=timezone_name,
    )
    normal_sign_out_closes_at = get_normal_sign_out_close_time(
        localized_end,
        sign_out_grace_minutes,
        timezone_name=timezone_name,
    )
    effective_sign_out_closes_at = get_effective_sign_out_close_time(
        localized_end,
        sign_out_grace_minutes,
        sign_out_override_until,
        timezone_name=timezone_name,
    )

    if localized_now < check_in_opens_at:
        event_status = "before_check_in"
    elif localized_now < localized_start:
        event_status = "early_check_in"
    elif localized_now >= sign_out_opens_at:
        if localized_now <= effective_sign_out_closes_at:
            event_status = "sign_out_open"
        else:
            event_status = "closed"
    elif localized_now >= localized_end:
        event_status = "sign_out_pending"
    elif localized_now <= late_threshold_time:
        event_status = "late_check_in"
    else:
        event_status = "absent_check_in"

    return EventTimeStatusResult(
        event_status=event_status,
        current_time=localized_now,
        check_in_opens_at=check_in_opens_at,
        start_time=localized_start,
        end_time=localized_end,
        late_threshold_time=late_threshold_time,
        attendance_override_active=attendance_cutoffs.attendance_override_active,
        effective_present_until_at=attendance_cutoffs.effective_present_until_at,
        effective_late_until_at=attendance_cutoffs.effective_late_until_at,
        sign_out_opens_at=sign_out_opens_at,
        normal_sign_out_closes_at=normal_sign_out_closes_at,
        effective_sign_out_closes_at=effective_sign_out_closes_at,
        timezone_name=timezone_name,
    )


def _build_attendance_decision(
    *,
    action: str,
    event_status: EventTimeStatusResult,
    attendance_allowed: bool,
    attendance_status: str | None,
    reason_code: str | None,
    message: str,
) -> AttendanceDecisionResult:
    return AttendanceDecisionResult(
        action=action,
        event_status=event_status.event_status,
        attendance_allowed=attendance_allowed,
        attendance_status=attendance_status,
        reason_code=reason_code,
        message=message,
        current_time=event_status.current_time,
        check_in_opens_at=event_status.check_in_opens_at,
        start_time=event_status.start_time,
        end_time=event_status.end_time,
        late_threshold_time=event_status.late_threshold_time,
        attendance_override_active=event_status.attendance_override_active,
        effective_present_until_at=event_status.effective_present_until_at,
        effective_late_until_at=event_status.effective_late_until_at,
        sign_out_opens_at=event_status.sign_out_opens_at,
        normal_sign_out_closes_at=event_status.normal_sign_out_closes_at,
        effective_sign_out_closes_at=event_status.effective_sign_out_closes_at,
        timezone_name=event_status.timezone_name,
    )


def get_attendance_decision(
    *,
    start_time: datetime,
    end_time: datetime,
    early_check_in_minutes: Any = 0,
    late_threshold_minutes: Any = 0,
    sign_out_grace_minutes: Any = 0,
    sign_out_open_delay_minutes: Any = 0,
    sign_out_override_until: datetime | None = None,
    present_until_override_at: datetime | None = None,
    late_until_override_at: datetime | None = None,
    current_time: datetime | None = None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> AttendanceDecisionResult:
    event_status = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=early_check_in_minutes,
        late_threshold_minutes=late_threshold_minutes,
        sign_out_grace_minutes=sign_out_grace_minutes,
        sign_out_open_delay_minutes=sign_out_open_delay_minutes,
        sign_out_override_until=sign_out_override_until,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=current_time,
        timezone_name=timezone_name,
    )

    if event_status.event_status == "before_check_in":
        return _build_attendance_decision(
            action="check_in",
            event_status=event_status,
            attendance_allowed=False,
            attendance_status=None,
            reason_code="event_not_open_yet",
            message="Check-in is not open yet for this event.",
        )

    if event_status.event_status in {"sign_out_pending", "sign_out_open"}:
        return _build_attendance_decision(
            action="check_in",
            event_status=event_status,
            attendance_allowed=False,
            attendance_status=None,
            reason_code=(
                "sign_out_not_open_yet"
                if event_status.event_status == "sign_out_pending"
                else "sign_out_window_open"
            ),
            message=(
                "Check-in is closed because sign-out is not open yet for this event."
                if event_status.event_status == "sign_out_pending"
                else "Check-in is closed because sign-out is currently open for this event."
            ),
        )

    if event_status.event_status == "closed":
        return _build_attendance_decision(
            action="check_in",
            event_status=event_status,
            attendance_allowed=False,
            attendance_status=None,
            reason_code="event_closed",
            message="Check-in is already closed for this event.",
        )

    if event_status.current_time < event_status.effective_present_until_at:
        return _build_attendance_decision(
            action="check_in",
            event_status=event_status,
            attendance_allowed=True,
            attendance_status="present",
            reason_code=None,
            message=(
                "Check-in is open. A valid verification will be marked present."
                if event_status.attendance_override_active
                else "Early check-in is open. A valid verification will be marked present."
            ),
        )

    if event_status.current_time <= event_status.effective_late_until_at:
        return _build_attendance_decision(
            action="check_in",
            event_status=event_status,
            attendance_allowed=True,
            attendance_status="late",
            reason_code=None,
            message=(
                "Check-in is still open, but it is already inside the late window."
            ),
        )

    return _build_attendance_decision(
        action="check_in",
        event_status=event_status,
        attendance_allowed=True,
        attendance_status="absent",
        reason_code=None,
        message="Check-in is still being recorded, but it is already beyond the late threshold.",
    )


def get_sign_out_decision(
    *,
    start_time: datetime,
    end_time: datetime,
    early_check_in_minutes: Any = 0,
    late_threshold_minutes: Any = 0,
    sign_out_grace_minutes: Any = 0,
    sign_out_open_delay_minutes: Any = 0,
    sign_out_override_until: datetime | None = None,
    present_until_override_at: datetime | None = None,
    late_until_override_at: datetime | None = None,
    current_time: datetime | None = None,
    timezone_name: str = DEFAULT_EVENT_TIMEZONE,
) -> AttendanceDecisionResult:
    event_status = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=early_check_in_minutes,
        late_threshold_minutes=late_threshold_minutes,
        sign_out_grace_minutes=sign_out_grace_minutes,
        sign_out_open_delay_minutes=sign_out_open_delay_minutes,
        sign_out_override_until=sign_out_override_until,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=current_time,
        timezone_name=timezone_name,
    )

    if event_status.event_status == "sign_out_open":
        return _build_attendance_decision(
            action="sign_out",
            event_status=event_status,
            attendance_allowed=True,
            attendance_status="present",
            reason_code=None,
            message="Sign-out is open for this event.",
        )

    if event_status.event_status == "closed":
        return _build_attendance_decision(
            action="sign_out",
            event_status=event_status,
            attendance_allowed=False,
            attendance_status=None,
            reason_code="sign_out_closed",
            message="Sign-out is already closed for this event.",
        )

    return _build_attendance_decision(
        action="sign_out",
        event_status=event_status,
        attendance_allowed=False,
        attendance_status=None,
        reason_code="sign_out_not_open_yet",
        message="Sign-out is not open yet for this event.",
    )


__all__ = [
    "AttendanceDecisionResult",
    "AttendanceWindowCutoffResult",
    "DEFAULT_EVENT_TIMEZONE",
    "DEFAULT_ATTENDANCE_OVERRIDE_ABSENT_WINDOW_MINUTES",
    "EventTimeStatusResult",
    "get_attendance_decision",
    "get_check_in_opens_at",
    "get_effective_sign_out_close_time",
    "get_event_status",
    "get_event_timezone",
    "get_late_threshold_time",
    "get_normal_sign_out_close_time",
    "get_sign_out_open_time",
    "get_sign_out_decision",
    "normalize_early_check_in_minutes",
    "normalize_event_datetime",
    "normalize_late_threshold_minutes",
    "normalize_optional_event_datetime",
    "normalize_sign_out_open_delay_minutes",
    "normalize_sign_out_grace_minutes",
    "normalize_window_minutes",
    "resolve_attendance_window_cutoffs",
]
