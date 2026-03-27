"""Use: Tests attendance status support and helpers.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models.attendance import AttendanceStatus as ModelAttendanceStatus
from app.schemas.attendance import (
    AttendanceStatus as SchemaAttendanceStatus,
    ProgramBreakdownItem,
    StudentAttendanceSummary,
)
from app.services.attendance_status import (
    ATTENDED_STATUS_VALUES,
    empty_attendance_display_status_counts,
    empty_attendance_status_counts,
    finalize_completed_attendance_status,
    is_completed_attended_status,
    is_attended_status,
    is_late_arrival,
    normalize_attendance_status,
    resolve_attendance_display_status,
)


def test_model_and_schema_include_late_status() -> None:
    assert ModelAttendanceStatus.LATE.value == "late"
    assert SchemaAttendanceStatus.LATE.value == "late"


def test_late_counts_as_attended() -> None:
    assert ATTENDED_STATUS_VALUES == ("present", "late")
    assert is_attended_status("present") is True
    assert is_attended_status("late") is True
    assert is_attended_status("absent") is False
    assert is_attended_status("excused") is False


def test_empty_status_counts_include_late() -> None:
    assert empty_attendance_status_counts() == {
        "present": 0,
        "late": 0,
        "absent": 0,
        "excused": 0,
    }


def test_empty_display_status_counts_include_incomplete() -> None:
    assert empty_attendance_display_status_counts() == {
        "present": 0,
        "late": 0,
        "absent": 0,
        "excused": 0,
        "incomplete": 0,
    }


def test_normalize_attendance_status_handles_enum_values() -> None:
    assert normalize_attendance_status(SchemaAttendanceStatus.LATE) == "late"
    assert normalize_attendance_status(ModelAttendanceStatus.PRESENT) == "present"


def test_display_status_and_validity_helpers_require_sign_out_completion() -> None:
    completed_at = datetime(2026, 3, 27, 10, 0, 0, tzinfo=timezone.utc)

    assert resolve_attendance_display_status(stored_status="present", time_out=None) == "incomplete"
    assert resolve_attendance_display_status(stored_status="late", time_out=completed_at) == "late"
    assert is_completed_attended_status(stored_status="present", time_out=None) is False
    assert is_completed_attended_status(stored_status="present", time_out=completed_at) is True


def test_report_models_accept_late_fields() -> None:
    summary = StudentAttendanceSummary(
        student_id="2024-0001",
        student_name="Test Student",
        total_events=4,
        attended_events=3,
        late_events=1,
        absent_events=1,
        excused_events=0,
        attendance_rate=75.0,
    )
    breakdown = ProgramBreakdownItem(
        program="BSIT",
        total=10,
        present=5,
        late=1,
        absent=4,
    )

    assert summary.late_events == 1
    assert breakdown.late == 1


def test_late_threshold_helpers_follow_present_late_absent_windows() -> None:
    event_start = datetime(2026, 3, 11, 9, 0, 0)
    present_scan = datetime(2026, 3, 11, 0, 55, 0, tzinfo=timezone.utc)
    late_scan = datetime(2026, 3, 11, 1, 0, 0, tzinfo=timezone.utc)
    absent_scan = datetime(2026, 3, 11, 1, 11, 0, tzinfo=timezone.utc)

    assert (
        is_late_arrival(
            event_start=event_start,
            time_in=present_scan,
            late_threshold_minutes=10,
        )
        is False
    )
    assert (
        is_late_arrival(
            event_start=event_start,
            time_in=late_scan,
            late_threshold_minutes=10,
        )
        is True
    )
    assert (
        is_late_arrival(
            event_start=event_start,
            time_in=absent_scan,
            late_threshold_minutes=10,
        )
        is False
    )


def test_finalize_completed_attendance_status_uses_the_confirmed_matrix() -> None:
    assert finalize_completed_attendance_status(
        check_in_status="present",
        check_out_status="present",
    ) == ("present", None)
    assert finalize_completed_attendance_status(
        check_in_status="late",
        check_out_status="present",
    ) == ("late", None)
    assert finalize_completed_attendance_status(
        check_in_status="absent",
        check_out_status="present",
    ) == ("absent", None)


def test_finalize_completed_attendance_status_marks_missing_sign_out_absent() -> None:
    status_value, note = finalize_completed_attendance_status(
        check_in_status="present",
        check_out_status="absent",
    )

    assert status_value == "absent"
    assert note is not None
    assert "sign-out was missing" in note


def test_finalize_completed_attendance_status_marks_unknown_check_in_absent() -> None:
    status_value, note = finalize_completed_attendance_status(
        check_in_status=None,
        check_out_status="present",
    )

    assert status_value == "absent"
    assert note is not None
    assert "sign-in status could not be determined" in note


def test_late_threshold_helpers_support_aware_utc_timestamps() -> None:
    manila = ZoneInfo("Asia/Manila")
    event_start = datetime(2026, 3, 11, 9, 0, 0, tzinfo=manila)
    late_scan = datetime(2026, 3, 11, 1, 5, 0, tzinfo=timezone.utc)
    absent_scan = datetime(2026, 3, 11, 1, 20, 0, tzinfo=timezone.utc)
    assert (
        is_late_arrival(
            event_start=event_start,
            time_in=late_scan,
            late_threshold_minutes=10,
        )
        is True
    )
    assert (
        is_late_arrival(
            event_start=event_start,
            time_in=absent_scan,
            late_threshold_minutes=10,
        )
        is False
    )
