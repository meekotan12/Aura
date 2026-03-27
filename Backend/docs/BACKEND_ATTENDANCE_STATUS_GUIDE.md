# Backend Attendance Status Guide

## Purpose

This guide documents how attendance status is now recorded in the backend with explicit sign-in and sign-out audit fields.

## Null Student IDs In Responses

- attendance response payloads may return `student_id = null` when the student profile is valid but the school has not assigned an external student identifier yet
- this applies to student self-service records, attendance overview rows, and student attendance reports
- frontend code should treat `student_id` as nullable display data, not as a guaranteed identifier for record integrity

## Route Prefix Note

- canonical private route families in this guide now live under `/api/events/*` and `/api/attendance/*`
- the deprecated unprefixed `/events/*` and `/attendance/*` aliases were removed

The backend now separates:

- `check_in_status`: what the sign-in window decided
- `check_out_status`: whether sign-out completed inside an allowed sign-out window
- `status`: the final attendance status used by reports and dashboards
- computed API-only fields:
  - `display_status`
  - `completion_state`
  - `is_valid_attendance`

## Valid Final Statuses

- `present`
- `late`
- `absent`
- `excused`

## New Attendance Audit Fields

Stored on `attendances`:

- `check_in_status: "present" | "late" | "absent" | null`
- `check_out_status: "present" | "absent" | null`

Exposed from:

- `Backend/app/models/attendance.py`
- `Backend/app/schemas/attendance.py`

Added by migration:

- `Backend/alembic/versions/e4b7c1d9f6a2_add_event_attendance_window_controls.py`

Historical rows may still have `null` audit fields.

## Check-In Status Rules

Check-in status is derived from the event timing window:

- before start, inside the early window -> `present`
- from exact start through the late threshold cutoff -> `late`
- after the late threshold cutoff while check-in is still open -> `absent`

Near-start override rule:

- if an event is saved too close to its scheduled start, the backend may store:
  - `present_until_override_at`
  - `late_until_override_at`
- when those fields are active:
  - students stay `present` until `present_until_override_at`
  - then they become `late` until `late_until_override_at`
  - then they become `absent` until sign-out opens at `end_datetime`
- the event workflow status still follows the scheduled start and end time, so attendance marking can temporarily differ from the workflow label

Important rule:

- exact start time is treated as `late`

The reusable helpers live in:

- `Backend/app/services/event_time_status.py`
- `Backend/app/services/attendance_status.py`

Current live-path note:

- check-in window decisions now rely on `get_attendance_decision()` from `Backend/app/services/event_time_status.py`
- final attendance matrix application still happens in `finalize_completed_attendance_status()` from `Backend/app/services/attendance_status.py`
- the older unused helper `resolve_time_in_status()` was removed after confirming it was no longer part of the current runtime flow

## Sign-Out Rules

Sign-out is allowed only when:

- the event has reached `end_datetime`, or
- an active early sign-out override is open

If the student signs out during an allowed sign-out window:

- `check_out_status = "present"`

If sign-out is missing or finalized after the effective close:

- `check_out_status = "absent"`

If an attendance row exists with no `time_out` yet:

- `display_status = "incomplete"`
- `completion_state = "incomplete"`
- `is_valid_attendance = false`

## Final Status Matrix

The backend finalizes `status` with this matrix:

| check_in_status | check_out_status | final status |
| --- | --- | --- |
| `present` | `present` | `present` |
| `late` | `present` | `late` |
| `absent` | `present` | `absent` |
| any value | not `present` | `absent` |
| unknown check-in | `present` | `absent` |

Implementation:

- `Backend/app/services/attendance_status.py`

## Route Behavior

### Manual and operator face-scan attendance

These routes now branch in this order:

1. find the student and current event
2. if there is an active attendance with no `time_out`, treat the request as sign-out
3. otherwise evaluate the check-in window and create a new attendance

That behavior is important so sign-out override works correctly.

Routes:

- `POST /attendance/manual`
- `POST /attendance/face-scan`

### Student face attendance

Student self-scan already follows the same sign-out-first behavior:

- `POST /face/face-scan-with-recognition`

## Automatic Finalization

When an event reaches the effective sign-out close, the backend finalizes remaining attendance:

- open attendances with no `time_out` become:
  - `check_out_status = "absent"`
  - final `status = "absent"`
- students in scope with no attendance row receive an auto-created absent record

Finalization now waits for the effective sign-out close, not the raw `end_datetime`.

Implementation:

- `Backend/app/services/event_attendance_service.py`
- `Backend/app/services/event_workflow_status.py`

## Reporting Behavior

For reporting and attendance-rate calculations:

- only completed `present` counts as attended
- only completed `late` counts as attended
- `incomplete` is reported separately and does not count as attended
- `absent` does not count as attended
- `excused` does not count as attended

Existing report models already expose late-aware summary fields such as:

- `ProgramBreakdownItem.late`
- `ProgramBreakdownItem.incomplete`
- `StudentAttendanceSummary.late_events`
- `StudentAttendanceSummary.incomplete_events`
- `AttendanceReportResponse.incomplete_attendees`

## Main Backend Touchpoints

- `Backend/app/models/attendance.py`
- `Backend/app/models/event.py`
- `Backend/app/schemas/attendance.py`
- `Backend/app/schemas/attendance_requests.py`
- `Backend/app/schemas/event.py`
- `Backend/app/services/attendance_status.py`
- `Backend/app/services/event_time_status.py`
- `Backend/app/services/event_attendance_service.py`
- `Backend/app/routers/attendance/`
- `Backend/app/routers/face_recognition.py`

## Testing

Recommended checks:

1. Run `Backend\.venv\Scripts\python.exe -m pytest -q Backend/app/tests/test_attendance_status_support.py Backend/app/tests/test_governance_hierarchy_api.py -k "attendance or sign_out"`.
2. Create an event with:
   - `early_check_in_minutes`
   - `late_threshold_minutes`
   - `sign_out_grace_minutes`
3. Record check-in before start and confirm `check_in_status = "present"`.
4. Record check-in at exact start or inside the threshold and confirm `check_in_status = "late"`.
5. Record check-in after the threshold and confirm `check_in_status = "absent"`.
6. Try to sign out before sign-out opens and confirm the backend rejects it.
7. Open `POST /events/{event_id}/sign-out/open-early` and confirm the same active attendance can sign out successfully.
8. Confirm final rows include `check_in_status`, `check_out_status`, and the correct final `status`.
9. Confirm unfinished rows are returned as `display_status = "incomplete"` and `is_valid_attendance = false`.
10. Create or edit an event so it starts within its configured early window and confirm the returned event now includes `present_until_override_at` and `late_until_override_at`.
11. During that override window, confirm students stay `present` until the effective present cutoff and only become `late` after that cutoff.
