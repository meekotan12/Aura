# Backend Event Auto Status Guide

## Purpose

This guide explains how the backend now keeps the stored event workflow status aligned with the computed attendance windows.

## Route Prefix Note

- canonical private event routes in this guide now live under `/api/events/*`
- the deprecated unprefixed `/events/*` aliases were removed

The system still stores organizer-facing workflow status on `events.status`, but that stored value is now synced from the computed time window instead of only from the raw event end time.

## Status Layers

### Computed attendance-window status

From `Backend/app/services/event_time_status.py`:

- `before_check_in`
- `early_check_in`
- `late_check_in`
- `absent_check_in`
- `sign_out_open`
- `closed`

### Stored workflow status

On `events.status`:

- `upcoming`
- `ongoing`
- `completed`
- `cancelled`

## Mapping Rules

The workflow sync service maps computed time status like this:

- `before_check_in` -> `upcoming`
- `early_check_in` -> `upcoming`
- `late_check_in` -> `ongoing`
- `absent_check_in` -> `ongoing`
- `sign_out_open` -> `ongoing`
- `closed` -> `completed`

This means:

- early check-in does not move the event to `ongoing`
- sign-out availability still counts as `ongoing`
- the event becomes `completed` only after the effective sign-out close

## Effective Sign-Out Close

Auto-completion now uses the effective sign-out close, not just `end_datetime`.

The effective close is:

- `end_datetime + sign_out_grace_minutes`

If an event is ended early through `POST /events/{event_id}/sign-out/open-early`, the backend moves `end_datetime` to the current time first. After that, the event still stays `ongoing` until the new `end_datetime + sign_out_grace_minutes` close time passes.

## Safety Rules

Two terminal-state protections remain in place:

- `cancelled` stays manual and is never auto-overridden
- manually completed events stay sticky and are not reopened automatically
- manually setting `ongoing` is rejected if the current Manila time is still before the event `start_datetime`
- manually setting `upcoming` is rejected once the event timing has already moved into:
  - in-progress attendance windows
  - the sign-out window
  - the fully closed window

For `PATCH /events/{event_id}/status`:

- `status=ongoing` is allowed only once the scheduled start time has been reached
- if the event has not started yet, the route returns `409 Conflict`
- `status=upcoming` is allowed only while the computed event timing is still `before_check_in` or `early_check_in`
- if the event is already in progress, the route returns `409 Conflict`
- if a cancelled event is reopened during sign-out, the request succeeds but auto-sync returns the event to `ongoing`
- if a cancelled event is reopened after the full event window is already closed, the request succeeds but auto-sync returns the event to `completed`
- if the event is already stored as `completed`, the route returns `409 Conflict` with a message that it cannot be reopened because it is already completed
- this keeps the manual status action aligned with the same event-time rules used by auto-sync

## Attendance Finalization On Completion

When sync moves an event to `completed`, the backend runs:

- `finalize_completed_event_attendance()`

That finalizer:

- creates absent rows for in-scope students who never signed in
- marks open attendances with no sign-out as absent
- uses the effective sign-out close timestamp when writing the auto-finalized `time_out`

## Where Sync Runs

### Request-time fallback

Relevant routes refresh stale workflow status before continuing:

- `GET /events/`
- `GET /events/{event_id}`
- `GET /events/{event_id}/time-status`
- `POST /events/{event_id}/verify-location`
- event attendance helpers in `attendance.py`
- student face attendance helpers in `face_recognition.py`

### Background scheduler

Celery Beat still publishes:

- `app.workers.tasks.sync_event_workflow_statuses`

That task scans `upcoming` and `ongoing` events and applies the same service logic.

## Main Files

- `Backend/app/services/event_workflow_status.py`
- `Backend/app/services/event_time_status.py`
- `Backend/app/services/event_attendance_service.py`
- `Backend/app/routers/events/`
- `Backend/app/routers/attendance/`
- `Backend/app/routers/face_recognition.py`
- `Backend/app/workers/celery_app.py`
- `Backend/app/workers/tasks.py`
- `Backend/app/tests/test_event_workflow_status.py`

## Example Flow

If an event has:

- `start_datetime = 1:00 PM`
- `end_datetime = 2:00 PM`
- `sign_out_grace_minutes = 10`

then:

- before `1:00 PM`, including early check-in -> stored status stays `upcoming`
- from `1:00 PM` through attendance and sign-out availability -> stored status is `ongoing`
- after `2:10 PM` -> stored status becomes `completed`

If an early sign-out override opens until `2:15 PM`, the event stays `ongoing` until `2:15 PM`.

## Testing

Recommended checks:

1. Run `Backend\.venv\Scripts\python.exe -m pytest -q Backend/app/tests/test_event_workflow_status.py`.
2. Create an event with a sign-out grace period and confirm it stays `ongoing` after `end_datetime` while sign-out is still open.
3. Open a sign-out override near the end of the event and confirm the event remains `ongoing` until the later override close.
4. Confirm the next sync after the effective close moves the event to `completed`.
5. Confirm absent finalization happens only after that completion point.
