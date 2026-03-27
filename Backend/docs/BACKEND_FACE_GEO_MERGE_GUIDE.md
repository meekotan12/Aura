# Backend Face And Geolocation Merge Guide

## Purpose

This document explains how the face recognition and geolocation verification logic from the `GITHUB` reference project was merged into the `RIZAL_v1` backend.

## Route Prefix Note

- canonical private routes in this guide now live under `/api/auth/security/*`, `/api/face/*`, `/api/events/*`, and `/api/attendance/*`
- public kiosk routes under `/public-attendance/*` stay unchanged
- the deprecated unprefixed private paths were removed

It covers:

- where the backend changes live
- how the main login and attendance flows work
- the routes involved
- the database changes
- a step-by-step tutorial for running and testing the backend flow

## Scope Of The Merge

The `GITHUB` folder was used as the reference implementation for:

- face encoding and matching
- passive anti-spoof / liveness verification
- privileged-user face verification after password login
- event geofence verification
- combined face plus location attendance scanning

Those features now live in `RIZAL_v1/Backend`. The active runtime backend is `Backend/`, not `GITHUB/Backend`.

## High-Level Architecture

There are two related but different face flows in the backend:

1. Privileged login face verification
   - used by `admin` and `school_IT`
   - password login can issue a pending face session first
   - the session becomes a full access session only after live face verification succeeds

2. Student face attendance
   - used for student face registration and event attendance scanning
   - verifies liveness, face match, geofence, and attendance timing
   - configured test accounts may bypass the biometric step while still using event scope, timing, and geofence validation

3. Public login-page attendance kiosk
   - used by the unauthenticated login page
   - lists nearby geofenced events based on browser GPS
   - runs multi-face attendance scanning without logging the student into the app
   - still uses the selected event scope to decide whether a matched face is eligible

Geolocation is used in event attendance, not in privileged login.

## Backend File Map

### Core services

- `Backend/app/services/face_recognition.py`
  - image decoding
  - face detection and encoding
  - face comparison
  - ONNX anti-spoof model loading and liveness checks
  - current live routes use the database-backed encoding flow
  - previously retained local-file helpers were removed after confirming they were not used by the frontend or active backend routes

- `Backend/app/services/event_geolocation.py`
  - event geofence field validation
  - event geofence verification response building
  - shared location verification used by both `events.py` and `face_recognition.py`
  - attendance travel-speed risk checks for face attendance scans

- `Backend/app/services/attendance_face_scan.py`
  - event-scoped student candidate loading
  - public kiosk attendance phase resolution
  - public sign-in/sign-out persistence rules

- `Backend/app/services/geolocation.py`
  - coordinate validation
  - accuracy validation
  - distance calculation
  - geofence decision logic
  - reason codes for location failures

- `Backend/app/services/auth_session.py`
  - pending face token issuance
  - full access token issuance
  - helper to check whether a privileged user already has a face reference

### Routers

- `Backend/app/routers/auth.py`
  - password login entry point
  - can return a pending face token for privileged roles

- `Backend/app/routers/security_center.py`
  - privileged-user face enrollment, liveness, and verification
  - used after password login for `admin` and `school_IT`

- `Backend/app/routers/face_recognition.py`
  - student face registration
  - student face verification
  - combined face plus location attendance scan

- `Backend/app/routers/public_attendance.py`
  - public login-page nearby-event discovery
  - public multi-face attendance scanning

- `Backend/app/routers/events/`
  - event create and update with geofence fields
  - event location verification route

### Models and schemas

- `Backend/app/models/platform_features.py`
  - `UserFaceProfile` for privileged-user face references

- `Backend/app/models/event.py`
  - event geofence fields

- `Backend/app/models/attendance.py`
  - attendance geo audit fields
  - liveness audit fields

- `Backend/app/schemas/face_recognition.py`
  - request and response contracts for face routes

- `Backend/app/schemas/face.py`
  - removed after the schema split because active modules now import the dedicated schema files directly

- `Backend/app/schemas/event.py`
  - event create, update, and response contracts
  - event geofence request and response fields
  - event location verification request and response models

### Migration

- `Backend/alembic/versions/f8b2c1d4e6a7_add_face_profiles_and_event_geo_fields.py`
  - adds privileged face profile storage
  - adds event geofence fields
  - adds attendance geolocation and liveness audit fields

## Route Map

### Authentication and privileged face routes

- `POST /auth/login`
  - validates email and password
  - for `admin` and `school_IT`, can return a pending face token instead of full access

- `GET /auth/security/face-status`
  - returns whether the current privileged account already has a registered face reference

- `POST /auth/security/face-liveness`
  - runs live liveness / anti-spoof evaluation on the submitted image

- `POST /auth/security/face-reference`
  - saves or replaces the privileged account face reference

- `DELETE /auth/security/face-reference`
  - removes the privileged account face reference

- `POST /auth/security/face-verify`
  - checks the live image against the enrolled reference
  - promotes a pending face token into a full access session on success

### Student face routes

- `POST /face/register`
  - registers a student face using base64 image input
  - may return `student_id = null` when the student profile has no assigned external student ID yet

- `POST /face/register-upload`
  - registers a student face using uploaded file input
  - may return `student_id = null` when the student profile has no assigned external student ID yet

- `POST /face/verify`
  - verifies a student face image against the stored face reference

- `POST /face/face-scan-with-recognition`
  - combined attendance route
  - checks face, liveness, location, and sign-in or sign-out state
  - now limits the match candidate pool to the selected event scope instead of the whole school
  - for emails listed in `FACE_SCAN_BYPASS_EMAILS`, the route may omit `image_base64` and resolves the student from the authenticated student account instead

### Public kiosk routes

- `POST /public-attendance/events/nearby`
  - receives browser GPS coordinates
  - returns nearby geofenced events whose attendance phase is currently active
  - can return events from different active schools if the device is inside those geofences

- `POST /public-attendance/events/{event_id}/multi-face-scan`
  - accepts one live camera frame plus current GPS coordinates
  - detects multiple faces in a frame
  - applies per-face liveness and face matching
  - records sign-in or sign-out using the event's current attendance phase
  - returns per-face results such as `time_in`, `time_out`, `out_of_scope`, `no_match`, and `liveness_failed`

### Event geolocation routes

- `POST /events/`
  - event creation
  - accepts geofence fields as part of the event payload

- `GET /events/{event_id}/time-status`
  - returns the computed attendance-window status from the event schedule

- `PUT /events/{event_id}`
  - event update
  - supports updating geofence fields

- `POST /events/{event_id}/verify-location`
  - location-only verification route for a single event
  - now also returns the computed event time status and attendance decision

## Data Model Changes

### `UserFaceProfile`

Privileged-user face references are not stored on the `users` table directly. They live in `UserFaceProfile`, linked one-to-one with the user. This keeps the privileged-user face flow separate from student registration fields.

### Event geofence fields

Events now support:

- `geo_latitude`
- `geo_longitude`
- `geo_radius_m`
- `geo_required`
- `geo_max_accuracy_m`
- `late_threshold_minutes`

These fields define the event geofence.

### Attendance audit fields

Attendance records store:

- GPS coordinates used during sign-in or sign-out
- GPS accuracy
- liveness result
- liveness confidence
- face similarity details

This gives the backend an audit trail for attendance decisions.

## Step-By-Step Tutorial

## 1. Prepare The Backend

1. Make sure the anti-spoof model exists at `Backend/models/MiniFASNetV2.onnx`.
2. Make sure the backend dependencies include `opencv-python-headless`, `onnxruntime`, `face-recognition`, and related packages in `Backend/requirements.txt`.
3. Run the database migration:

```bash
cd Backend
alembic upgrade head
```

4. Start the application stack from the project root:

```bash
docker compose up -d
```

## 2. Verify The Anti-Spoof Configuration

Check `Backend/app/core/config.py`.

Important setting:

- `ALLOW_LIVENESS_BYPASS_WHEN_MODEL_MISSING`

Recommended production-like behavior:

- set it to `False`

That prevents silent liveness bypass when the anti-spoof model or runtime is unavailable.

## 3. Privileged Login Flow

This flow is for `admin` and `school_IT`.

1. The user submits email and password to `POST /auth/login`.
2. `auth.py` calls the auth session helpers in `auth_session.py`.
3. New onboarding accounts can also receive `password_change_recommended=true` as a non-blocking suggestion.
4. If the user wants to change the password immediately, the frontend can call `POST /auth/change-password`.
5. If the user skips that suggestion, the frontend can persist the skip through `POST /auth/password-change-prompt/dismiss`.
6. If the role requires face verification, the backend issues a pending face token instead of a full access token.
7. The frontend calls `GET /auth/security/face-status`.
8. If there is no registered face:
   - the frontend captures a live image
   - the frontend can call `POST /auth/security/face-liveness`
   - the frontend saves the reference through `POST /auth/security/face-reference`
9. For login verification, the frontend submits a live image to `POST /auth/security/face-verify`.
10. On success, the backend promotes the pending face session into a full access session.

### Logic summary

- password is the first factor
- password-change suggestion is optional for new accounts and is not used as a gate
- live face is the second factor
- registration is required only when no privileged face reference exists yet
- student face registration still uses `/face/register`; the `/auth/security/face-*` endpoints remain reserved for privileged login onboarding

## 4. Student Face Registration Flow

1. The student submits a face image to `POST /face/register` or `POST /face/register-upload`.
2. `face_recognition.py` decodes the image and calls the face-recognition service.
3. The backend performs:
   - face detection
   - face encoding extraction
   - passive liveness / anti-spoof check
4. On success, the student face data is stored for future attendance matching.
5. The success response can include `student_id = null` if the profile is valid but does not yet have a school-issued identifier.

### Important behavior

- registration should use a live camera image
- liveness should be enforced before the registration is accepted

## 5. Event Geofence Setup

1. Create or update an event through `POST /events/` or `PUT /events/{event_id}`.
2. Include:
   - `geo_latitude`
   - `geo_longitude`
   - `geo_radius_m`
   - `geo_required`
   - `geo_max_accuracy_m`
   - `late_threshold_minutes`
3. `events.py` validates the geofence fields before saving them.

Example event geofence payload fields:

```json
{
  "geo_latitude": 8.1575,
  "geo_longitude": 123.8431,
  "geo_radius_m": 100,
  "geo_required": true,
  "geo_max_accuracy_m": 35,
  "late_threshold_minutes": 10
}
```

## 6. Student Attendance Sign-In / Sign-Out Flow

1. The frontend opens the student event sign-in screen.
2. The browser captures:
   - a live face image
   - the current GPS position
   - the reported GPS accuracy
3. The frontend submits the combined attendance request to `POST /face/face-scan-with-recognition`.
4. `face_recognition.py` performs:
   - event lookup
   - dynamic event time-status validation
   - event geofence verification through `event_geolocation.py`
   - recent-travel sanity check
   - liveness check
   - face recognition match
5. If the student has no active attendance record for the event:
   - the backend records `time_in`
   - the check-in is marked `present` or `late` from the computed event time status
6. If the student already has `time_in` but no `time_out`:
   - the backend records `time_out`
   - the backend finalizes status
7. Status becomes:
   - `present` when the attendance window aligns with the event schedule and the time-in is within the late threshold
   - `late` when the attendance window aligns with the event schedule but the time-in passed the event late threshold
   - `absent` when the attendance window does not align with the event schedule

## 7. Location-Only Verification Flow

If you need to test location without face scanning:

1. Call `POST /events/{event_id}/verify-location`.
2. Send:

```json
{
  "latitude": 8.1575,
  "longitude": 123.8431,
  "accuracy_m": 20
}
```

3. The backend returns a geofence decision plus distance and reason details.
4. The same response now also includes:
   - computed `time_status`
   - computed `attendance_decision`

## Logic Walkthrough

## A. Pending Face Login Sessions

`Backend/app/services/auth_session.py` is the bridge between password login and face verification.

Main idea:

- privileged roles do not receive full access immediately
- they first receive a pending token with face verification state
- successful face verification upgrades that session

This logic keeps the second factor in the backend instead of trusting the frontend alone.

## B. Face Recognition And Liveness

`Backend/app/services/face_recognition.py` handles:

- image decoding from base64 or upload
- extracting one face encoding from the image
- comparing encodings with stored reference data
- loading and running the ONNX anti-spoof model

Recommended behavior:

- do not allow liveness bypass in normal operation
- require a valid anti-spoof result for registration and verification

## C. Geofence Verification

`Backend/app/services/event_geolocation.py` and `Backend/app/services/geolocation.py` now split responsibilities:

`event_geolocation.py` handles:

- event-aware location validation for routes
- response shaping for `POST /events/{event_id}/verify-location`
- face-attendance location checks and travel-risk detection

`geolocation.py` handles:

1. normalize and validate the student coordinates
2. normalize and validate the event coordinates
3. validate the geofence radius
4. validate GPS accuracy
5. calculate distance
6. apply buffered or unbuffered geofence decision
7. return a stable reason code

Current live-path note:

- the active runtime flow uses `geofence_check()` and `haversine_m()`
- previously retained utility-only helpers `recommended_accuracy_limit_m()` and `is_accuracy_ok()` were removed after confirming they were not part of the current frontend-backed routes or router workflow

Current reason codes include:

- `invalid_user_coordinates`
- `invalid_event_coordinates`
- `invalid_geofence_radius`
- `geofence_radius_out_of_range`
- `accuracy_missing`
- `invalid_accuracy`
- `accuracy_exceeds_limit`
- `outside_geofence`
- `outside_geofence_buffered`

## D. Attendance Finalization

The attendance route does not mark a student `present` at sign-in alone.

Current behavior:

- sign-in creates a provisional record
- sign-out completes the record
- the backend checks whether the recorded attendance window overlaps the scheduled event window
- only then is the final status set to `present` or `late`
- when an event is marked `completed`, missing attendees are auto-created as `absent`

This avoids marking a student present when they only signed in briefly or outside the event timing, and it keeps non-attendees from being left without an attendance outcome.

## E. Public Kiosk Scope Rules

The public kiosk does not authenticate the student into the web app. It only records attendance against the selected event.

Current scope behavior:

- campus-wide event:
  - no departments or programs on the event
  - all registered student faces in that school are eligible

- SG-style department event:
  - event has department scope and no program scope
  - only students from that department are eligible

- ORG-style program event:
  - event has program scope
  - only students in that program are eligible
  - if the event also includes a department, the student must match that department too

When a face matches a registered student in the school but not the selected event scope, the public API returns an `out_of_scope` result with generic messaging instead of exposing student-directory details.

## Suggested Testing Order

1. Run `alembic upgrade head`.
2. Confirm the backend can load the anti-spoof model.
3. Test privileged login:
   - password login
   - face reference enrollment
   - face verification
4. Create an event with geofence fields.
5. Test `POST /events/{event_id}/verify-location`.
6. Test student face registration.
7. Test student event sign-in.
8. Test student event sign-out.
9. Test the public kiosk:
   - load nearby events from `/login`
   - select one nearby event
   - scan multiple faces in one frame
   - confirm duplicate students are throttled and out-of-scope students are rejected
10. Confirm the final attendance status after sign-out.

## Practical Notes

- browser GPS is not enough to fully block fake GPS apps
- the current backend can reject low-quality readings and some suspicious behavior, but it cannot guarantee anti-spoof GPS detection
- face anti-spoof is passive liveness, not a full active challenge like blink or head-turn verification
- very small geofence radii can cause false rejections if browser GPS accuracy is poor

## Current Effective Runtime In `RIZAL_v1`

The active backend runtime is:

- `Backend/app/routers/auth.py`
- `Backend/app/routers/security_center.py`
- `Backend/app/routers/face_recognition.py`
- `Backend/app/routers/public_attendance.py`
- `Backend/app/routers/events/`
- `Backend/app/services/face_recognition.py`
- `Backend/app/services/attendance_face_scan.py`
- `Backend/app/services/event_geolocation.py`
- `Backend/app/services/geolocation.py`
- `Backend/app/services/auth_session.py`

The `GITHUB` directory is now only a reference copy unless it is started separately on purpose.

## Future Documentation Rule

For every backend change that affects behavior, routes, schemas, models, or migrations:

1. update `Backend/docs/BACKEND_CHANGELOG.md`
2. update this guide if the face or geolocation flow changed
3. document new routes, reason codes, environment variables, and migration requirements
