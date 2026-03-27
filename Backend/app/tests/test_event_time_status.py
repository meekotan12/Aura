"""Use: Tests computed event time status rules.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.event_time_status import (
    get_attendance_decision,
    get_effective_sign_out_close_time,
    get_event_status,
    get_sign_out_decision,
)


def test_get_event_status_transitions_across_all_windows() -> None:
    manila = ZoneInfo("Asia/Manila")
    start_time = datetime(2026, 3, 11, 9, 0, 0)
    end_time = datetime(2026, 3, 11, 11, 0, 0)

    before_check_in = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 8, 49, 59, tzinfo=manila),
    )
    early_check_in = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 8, 50, 0, tzinfo=manila),
    )
    late_check_in = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 9, 10, 0, tzinfo=manila),
    )
    absent_check_in = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 9, 10, 1, tzinfo=manila),
    )
    sign_out_open = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 5, 0, tzinfo=manila),
    )
    closed = get_event_status(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 10, 1, tzinfo=manila),
    )

    assert before_check_in.event_status == "before_check_in"
    assert early_check_in.event_status == "early_check_in"
    assert late_check_in.event_status == "late_check_in"
    assert absent_check_in.event_status == "absent_check_in"
    assert sign_out_open.event_status == "sign_out_open"
    assert closed.event_status == "closed"
    assert early_check_in.check_in_opens_at == datetime(
        2026, 3, 11, 8, 50, 0, tzinfo=manila
    )
    assert sign_out_open.effective_sign_out_closes_at == datetime(
        2026, 3, 11, 11, 10, 0, tzinfo=manila
    )


def test_get_event_status_supports_naive_event_datetimes_and_returns_manila_zone() -> None:
    result = get_event_status(
        start_time=datetime(2026, 3, 11, 9, 0, 0),
        end_time=datetime(2026, 3, 11, 11, 0, 0),
        early_check_in_minutes=15,
        late_threshold_minutes=15,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 9, 5, 0),
    )

    assert result.event_status == "late_check_in"
    assert result.timezone_name == "Asia/Manila"
    assert str(result.current_time.tzinfo) == "Asia/Manila"
    assert result.sign_out_opens_at.isoformat() == "2026-03-11T11:00:00+08:00"


def test_get_event_status_supports_pending_sign_out_window_before_delay_opens() -> None:
    manila = ZoneInfo("Asia/Manila")
    result = get_event_status(
        start_time=datetime(2026, 3, 11, 9, 0, 0),
        end_time=datetime(2026, 3, 11, 11, 0, 0),
        early_check_in_minutes=15,
        late_threshold_minutes=15,
        sign_out_grace_minutes=30,
        sign_out_open_delay_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 5, 0, tzinfo=manila),
    )

    assert result.event_status == "sign_out_pending"
    assert result.sign_out_opens_at.isoformat() == "2026-03-11T11:10:00+08:00"

    attendance_decision = get_attendance_decision(
        start_time=datetime(2026, 3, 11, 9, 0, 0),
        end_time=datetime(2026, 3, 11, 11, 0, 0),
        early_check_in_minutes=15,
        late_threshold_minutes=15,
        sign_out_grace_minutes=30,
        sign_out_open_delay_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 5, 0, tzinfo=manila),
    )
    sign_out_decision = get_sign_out_decision(
        start_time=datetime(2026, 3, 11, 9, 0, 0),
        end_time=datetime(2026, 3, 11, 11, 0, 0),
        early_check_in_minutes=15,
        late_threshold_minutes=15,
        sign_out_grace_minutes=30,
        sign_out_open_delay_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 5, 0, tzinfo=manila),
    )

    assert attendance_decision.attendance_allowed is False
    assert attendance_decision.reason_code == "sign_out_not_open_yet"
    assert sign_out_decision.attendance_allowed is False
    assert sign_out_decision.reason_code == "sign_out_not_open_yet"


def test_get_attendance_decision_maps_check_in_windows_to_statuses() -> None:
    manila = ZoneInfo("Asia/Manila")
    start_time = datetime(2026, 3, 11, 9, 0, 0)
    end_time = datetime(2026, 3, 11, 11, 0, 0)

    before_check_in = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 8, 45, 0, tzinfo=manila),
    )
    early_check_in = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 8, 55, 0, tzinfo=manila),
    )
    late_check_in = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 9, 0, 0, tzinfo=manila),
    )
    absent_check_in = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 9, 20, 0, tzinfo=manila),
    )
    sign_out_open = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 0, 0, tzinfo=manila),
    )
    closed = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=10,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 10, 1, tzinfo=manila),
    )

    assert before_check_in.attendance_allowed is False
    assert before_check_in.reason_code == "event_not_open_yet"

    assert early_check_in.attendance_allowed is True
    assert early_check_in.attendance_status == "present"

    assert late_check_in.attendance_allowed is True
    assert late_check_in.attendance_status == "late"

    assert absent_check_in.attendance_allowed is True
    assert absent_check_in.attendance_status == "absent"

    assert sign_out_open.attendance_allowed is False
    assert sign_out_open.reason_code == "sign_out_window_open"

    assert closed.attendance_allowed is False
    assert closed.reason_code == "event_closed"


def test_get_sign_out_decision_respects_early_end_and_grace_windows() -> None:
    manila = ZoneInfo("Asia/Manila")
    start_time = datetime(2026, 3, 11, 9, 0, 0)
    end_time = datetime(2026, 3, 11, 11, 0, 0)
    early_end_time = datetime(2026, 3, 11, 10, 50, 0)

    before_sign_out = get_sign_out_decision(
        start_time=start_time,
        end_time=end_time,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 10, 59, 59, tzinfo=manila),
    )
    normal_sign_out = get_sign_out_decision(
        start_time=start_time,
        end_time=end_time,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 5, 0, tzinfo=manila),
    )
    early_end_sign_out = get_sign_out_decision(
        start_time=start_time,
        end_time=early_end_time,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 10, 55, 0, tzinfo=manila),
    )
    early_end_closed = get_sign_out_decision(
        start_time=start_time,
        end_time=early_end_time,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 0, 1, tzinfo=manila),
    )
    closed = get_sign_out_decision(
        start_time=start_time,
        end_time=end_time,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        current_time=datetime(2026, 3, 11, 11, 15, 1, tzinfo=manila),
    )

    assert before_sign_out.attendance_allowed is False
    assert before_sign_out.reason_code == "sign_out_not_open_yet"

    assert normal_sign_out.attendance_allowed is True
    assert normal_sign_out.attendance_status == "present"

    assert early_end_sign_out.attendance_allowed is True
    assert early_end_sign_out.event_status == "sign_out_open"

    assert early_end_closed.attendance_allowed is False
    assert early_end_closed.reason_code == "sign_out_closed"
    assert early_end_closed.event_status == "closed"

    assert get_effective_sign_out_close_time(
        early_end_time,
        sign_out_grace_minutes=10,
        sign_out_override_until=datetime(2026, 3, 11, 11, 15, 0),
    ) == datetime(2026, 3, 11, 11, 0, 0, tzinfo=manila)

    assert closed.attendance_allowed is False
    assert closed.reason_code == "sign_out_closed"


def test_get_event_status_rejects_invalid_schedule() -> None:
    with pytest.raises(ValueError, match="end_time must be after start_time"):
        get_event_status(
            start_time=datetime(2026, 3, 11, 11, 0, 0),
            end_time=datetime(2026, 3, 11, 11, 0, 0),
            late_threshold_minutes=10,
        )


def test_get_attendance_decision_uses_override_cutoffs_for_present_late_and_absent() -> None:
    manila = ZoneInfo("Asia/Manila")
    start_time = datetime(2026, 3, 11, 9, 0, 0)
    end_time = datetime(2026, 3, 11, 10, 30, 0)
    present_until_override_at = datetime(2026, 3, 11, 9, 29, 0)
    late_until_override_at = datetime(2026, 3, 11, 9, 39, 0)

    present_result = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=datetime(2026, 3, 11, 9, 10, 0, tzinfo=manila),
    )
    late_result = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=datetime(2026, 3, 11, 9, 35, 0, tzinfo=manila),
    )
    absent_result = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=datetime(2026, 3, 11, 9, 50, 0, tzinfo=manila),
    )
    sign_out_result = get_attendance_decision(
        start_time=start_time,
        end_time=end_time,
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        present_until_override_at=present_until_override_at,
        late_until_override_at=late_until_override_at,
        current_time=datetime(2026, 3, 11, 10, 35, 0, tzinfo=manila),
    )

    assert present_result.attendance_allowed is True
    assert present_result.attendance_status == "present"
    assert present_result.attendance_override_active is True
    assert present_result.effective_present_until_at == datetime(
        2026, 3, 11, 9, 29, 0, tzinfo=manila
    )
    assert present_result.effective_late_until_at == datetime(
        2026, 3, 11, 9, 39, 0, tzinfo=manila
    )

    assert late_result.attendance_allowed is True
    assert late_result.attendance_status == "late"
    assert late_result.attendance_override_active is True

    assert absent_result.attendance_allowed is True
    assert absent_result.attendance_status == "absent"
    assert absent_result.attendance_override_active is True

    assert sign_out_result.attendance_allowed is False
    assert sign_out_result.reason_code == "sign_out_window_open"


def test_get_event_status_keeps_workflow_window_schedule_based_while_reporting_override_cutoffs() -> None:
    manila = ZoneInfo("Asia/Manila")

    result = get_event_status(
        start_time=datetime(2026, 3, 11, 9, 0, 0),
        end_time=datetime(2026, 3, 11, 10, 30, 0),
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=10,
        present_until_override_at=datetime(2026, 3, 11, 9, 29, 0),
        late_until_override_at=datetime(2026, 3, 11, 9, 39, 0),
        current_time=datetime(2026, 3, 11, 9, 10, 0, tzinfo=manila),
    )

    assert result.event_status == "late_check_in"
    assert result.attendance_override_active is True
    assert result.effective_present_until_at == datetime(
        2026, 3, 11, 9, 29, 0, tzinfo=manila
    )
    assert result.effective_late_until_at == datetime(
        2026, 3, 11, 9, 39, 0, tzinfo=manila
    )
