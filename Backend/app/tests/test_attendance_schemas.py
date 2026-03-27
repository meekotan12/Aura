from datetime import datetime

from app.schemas.attendance import (
    AttendanceMethod,
    AttendanceStatus,
    StudentAttendanceRecord,
    StudentAttendanceResponse,
    StudentAttendanceSummary,
    StudentListItem,
)


def _sample_attendance_record() -> StudentAttendanceRecord:
    return StudentAttendanceRecord(
        id=1,
        event_id=10,
        event_name="Sample Event",
        time_in=datetime(2026, 3, 27, 9, 0, 0),
        status=AttendanceStatus.INCOMPLETE,
        display_status=AttendanceStatus.INCOMPLETE,
        method=AttendanceMethod.FACE_SCAN,
    )


def test_student_attendance_response_allows_missing_student_id() -> None:
    response = StudentAttendanceResponse(
        student_id=None,
        student_name="Sample Student",
        total_records=1,
        attendances=[_sample_attendance_record()],
    )

    assert response.student_id is None


def test_student_attendance_summary_allows_missing_student_id() -> None:
    summary = StudentAttendanceSummary(
        student_id=None,
        student_name="Sample Student",
        total_events=1,
        attended_events=0,
        absent_events=0,
        excused_events=0,
        attendance_rate=0.0,
    )

    assert summary.student_id is None


def test_student_list_item_allows_missing_student_id() -> None:
    item = StudentListItem(
        id=1,
        student_id=None,
        full_name="Sample Student",
        total_events=0,
        attendance_rate=0.0,
    )

    assert item.student_id is None
