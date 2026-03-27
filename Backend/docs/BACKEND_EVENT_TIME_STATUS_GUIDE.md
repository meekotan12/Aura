# Backend Event Time Status Guide

## Purpose

This guide documents the computed attendance-window logic that now drives event check-in, sign-out, and workflow auto-sync.

## Route Prefix Note

- canonical private route families in this guide now live under `/api/events/*` and `/api/attendance/*`
- the deprecated unprefixed `/events/*` and `/attendance/*` aliases were removed

The backend keeps two related concepts:

- stored workflow status on `events.status`: `upcoming`, `ongoing`, `completed`, `cancelled`
- computed time-window status used for attendance decisions

The computed layer is the source of truth for attendance behavior.

## Event Timing Fields

Per-event timing is now configured with:

- `start_datetime`
- `end_datetime`
- `early_check_in_minutes`
- `late_threshold_minutes`
- `sign_out_grace_minutes`
- `sign_out_open_delay_minutes`

Default values for newly created events:

- `early_check_in_minutes = 30`
- `late_threshold_minutes = 10`
- `sign_out_grace_minutes = 20`

Existing events keep whatever values are already stored.

## Near-Start Attendance Override

The backend now protects short lead-time event saves so students can still receive the full configured `present` and `late` attendance windows.

Stored on `events`:

- `present_until_override_at`
- `late_until_override_at`

How it works on create and edit:

1. the backend resolves the effective `early_check_in_minutes` and `late_threshold_minutes`
2. it compares the current Manila time to `start_datetime`
3. if the event starts soon enough that `start_datetime - now < early_check_in_minutes`, the backend tries to preserve the full attendance windows by storing:
   - `present_until_override_at = now + early_check_in_minutes`
   - `late_until_override_at = present_until_override_at + late_threshold_minutes`
4. the save is rejected if:
   - `start_datetime <= now`, or
   - `end_datetime - now` is shorter than:
     - `early_check_in_minutes`
     - plus `late_threshold_minutes`
     - plus a fixed `20-minute` absent window
5. when no override is needed, both override fields stay `null`

Important rule:

- this override only changes attendance marking
- it does not delay the event lifecycle from becoming `ongoing` at the scheduled start time

## Default Source For New Events

New event requests can now omit the three attendance-window values and let the backend fill them from settings.

Resolution order:

1. explicit per-event request values
2. `ORG` override defaults on the matching `governance_unit`
3. `SG` override defaults on the matching `governance_unit`
4. school defaults on `school_settings`
5. hard fallback `30 / 10 / 20`

Stored default-setting fields:

- school-wide:
  - `school_settings.event_default_early_check_in_minutes`
  - `school_settings.event_default_late_threshold_minutes`
  - `school_settings.event_default_sign_out_grace_minutes`
- SG/ORG override:
  - `governance_units.event_default_early_check_in_minutes`
  - `governance_units.event_default_late_threshold_minutes`
  - `governance_units.event_default_sign_out_grace_minutes`

Important rules:

- `SSG` does not store its own override layer
- `SSG` event creation uses the school default
- `SG` and `ORG` event creation can use a unit override when the route resolves that governance scope
- resetting an SG/ORG override to `null` returns future events to school-default behavior

Stored on:

- `Backend/app/models/event.py`
- `Backend/app/schemas/event.py`
- migration `Backend/alembic/versions/e4b7c1d9f6a2_add_event_attendance_window_controls.py`
- migration `Backend/alembic/versions/f5d2c8a1b4e9_add_school_and_governance_event_defaults.py`

## Computed Time Statuses

The service in `Backend/app/services/event_time_status.py` computes one of these states:

- `before_check_in`
- `early_check_in`
- `late_check_in`
- `absent_check_in`
- `sign_out_pending`
- `sign_out_open`
- `closed`

### Window rules

Given:

- `check_in_opens_at = start_datetime - early_check_in_minutes`
- `late_threshold_time = start_datetime + late_threshold_minutes`
- `effective_present_until_at = present_until_override_at` when the override is active, otherwise `start_datetime`
- `effective_late_until_at = late_until_override_at` when the override is active, otherwise `late_threshold_time`
- `normal_sign_out_closes_at = end_datetime + sign_out_grace_minutes`
- `sign_out_opens_at = end_datetime + sign_out_open_delay_minutes`
- `effective_sign_out_closes_at = min(normal_sign_out_closes_at, sign_out_override_until)` when the override is set, otherwise `normal_sign_out_closes_at`

The computed status is:

1. before `check_in_opens_at` -> `before_check_in`
2. from `check_in_opens_at` until just before `start_datetime` -> `early_check_in`
3. from exact `start_datetime` through `late_threshold_time`, but only while current time is still before `end_datetime` -> `late_check_in`
4. after `late_threshold_time` until `end_datetime` -> `absent_check_in`
5. from `end_datetime` until just before `sign_out_opens_at` -> `sign_out_pending`
6. from `sign_out_opens_at` through `effective_sign_out_closes_at` -> `sign_out_open`
7. after `effective_sign_out_closes_at` -> `closed`

Important business rule:

- exact event start is already `late`

## Attendance Decisions

### Check-in

`get_attendance_decision()` returns:

- `before_check_in` -> reject
- before `effective_present_until_at` -> allow, mark `present`
- after that until `effective_late_until_at` -> allow, mark `late`
- after that until `end_datetime` -> allow, mark `absent`
- `sign_out_pending` -> reject new check-in
- `sign_out_open` -> reject new check-in
- `closed` -> reject

That means an event can already be `late_check_in` for workflow status purposes while the attendance decision still marks a student `present` because the near-start override is active.

### Sign-out

`get_sign_out_decision()` returns:

- allow only during the sign-out window from `end_datetime` through `end_datetime + sign_out_grace_minutes`
- if `sign_out_open_delay_minutes > 0`, sign-out stays rejected during `sign_out_pending`
- reject before sign-out opens
- reject after the effective sign-out close

## Open Sign-Out Early

The backend exposes:

- `POST /events/{event_id}/sign-out/open-early`
- compatibility alias: `POST /events/{event_id}/sign-out-override/open`

Behavior:

- permission requirement matches event attendance management access
- the event must already have started
- the event must still be before its current scheduled `end_datetime`
- cancelled events cannot open sign-out
- completed events cannot reopen sign-out
- the request body now supports:
  - `use_sign_out_grace_minutes`
  - `close_after_minutes`
- opening sign-out early sets `end_datetime = now`
- if `use_sign_out_grace_minutes = true`, the backend keeps the current `sign_out_grace_minutes`
- if `use_sign_out_grace_minutes = false`, `close_after_minutes` is required and the backend updates the event `sign_out_grace_minutes` to that value
- after that update, sign-out closes at `end_datetime + sign_out_grace_minutes`
- new check-ins are blocked as soon as the event is ended early
- existing active attendances may sign out immediately
- the old `sign_out_override_until` field is cleared and no longer drives the live close-window logic

Example request body:

```json
{
  "use_sign_out_grace_minutes": false,
  "close_after_minutes": 5
}
```

Implementation:

- `Backend/app/routers/events/workflow.py`

## Workflow Auto-Sync Mapping

The workflow sync service maps computed time status to stored event status like this:

- `before_check_in` -> `upcoming`
- `early_check_in` -> `upcoming`
- `late_check_in` -> `ongoing`
- `absent_check_in` -> `ongoing`
- `sign_out_pending` -> `ongoing`
- `sign_out_open` -> `ongoing`
- `closed` -> `completed`

So an event stays `ongoing` until all sign-out availability has ended.

Important:

- workflow auto-sync still ignores the attendance override cutoffs
- it continues to use the scheduled start, end, and sign-out windows only
- the override is attendance-only

Main file:

- `Backend/app/services/event_workflow_status.py`

## Routes That Use The Computed Decision

- `GET /events/{event_id}/time-status`
- `POST /events/{event_id}/verify-location`
- `POST /events/{event_id}/sign-out/open-early`
- `POST /attendance/manual`
- `POST /attendance/face-scan`
- `POST /attendance/{attendance_id}/time-out`
- `POST /attendance/face-scan-timeout`
- `POST /face/face-scan-with-recognition`

The manual and operator face-scan attendance routes now branch in this order:

1. if the student already has an active attendance with no `time_out`, treat the request as sign-out
2. otherwise evaluate the check-in window

That ordering is required so early sign-out opening works correctly.

## Response Fields

`get_event_status()` and the public route serializers now include:

- `event_status`
- `current_time`
- `check_in_opens_at`
- `start_time`
- `end_time`
- `late_threshold_time`
- `attendance_override_active`
- `effective_present_until_at`
- `effective_late_until_at`
- `sign_out_opens_at`
- `normal_sign_out_closes_at`
- `effective_sign_out_closes_at`
- `timezone_name`

## Example

If an event is:

- start: `1:00 PM`
- end: `2:00 PM`
- early check-in: `10`
- late threshold: `10`
- sign-out grace: `10`

And it is saved at `12:59 PM` with a near-start override that keeps the full attendance windows:

- scheduled start: `1:00 PM`
- scheduled end: `2:00 PM`
- effective present until: `1:29 PM`
- effective late until: `1:39 PM`

Then:

- workflow status still becomes `ongoing` at `1:00 PM`
- attendance decisions still mark students `present` until `1:29 PM`
- attendance decisions mark students `late` from `1:29 PM` through `1:39 PM`
- attendance decisions mark students `absent` after `1:39 PM` until sign-out opens at `2:00 PM`

then:

- `12:50 PM` to `12:59 PM` -> early check-in, status `present`
- `1:00 PM` to `1:10 PM` -> late check-in, status `late`
- `1:11 PM` to `1:59 PM` -> absent check-in, status `absent`
- `2:00 PM` to `2:10 PM` -> sign-out open
- after `2:10 PM` -> closed

If an event is ended early at `1:20 PM` and `sign_out_grace_minutes = 10`, then:

- the backend updates `end_datetime` to `1:20 PM`
- sign-out opens immediately at `1:20 PM`
- sign-out closes at `1:30 PM`

## Testing

Recommended checks:

1. Run `Backend\.venv\Scripts\python.exe -m pytest -q Backend/app/tests/test_event_time_status.py Backend/app/tests/test_event_workflow_status.py`.
2. As Campus Admin, update the school defaults and then create a new event without sending attendance-window fields.
3. As SG or ORG with `manage_events`, save a unit override and create a new event without sending attendance-window fields.
4. Confirm the created event stores the effective resolved values before checking time-status behavior.
5. Call `GET /events/{event_id}/time-status` before check-in opens, during early check-in, during late check-in, during absent check-in, during sign-out, and after close.
6. Call `POST /events/{event_id}/sign-out/open-early` with `{"use_sign_out_grace_minutes": true}` after the event has started and confirm the stored `end_datetime` is moved to now and sign-out opens immediately.
7. Call `POST /events/{event_id}/sign-out/open-early` with `{"use_sign_out_grace_minutes": false, "close_after_minutes": 5}` and confirm the event `sign_out_grace_minutes` becomes `5`.
8. Verify that `POST /events/{event_id}/verify-location` includes the updated time-window metadata.
9. Confirm the stored event `status` stays `ongoing` during sign-out and only becomes `completed` after the effective sign-out close.
