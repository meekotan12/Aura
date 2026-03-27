# Backend Database Cleanup Guide

## Purpose

This guide documents the removal of legacy database tables that are no longer used by the active `Backend/app` models, routers, or services.

## Removed Legacy Tables

The cleanup migration removes these unused tables when they exist:

- `ai_logs`
- `anomaly_logs`
- `attendance_predictions`
- `event_attendance`
- `event_consumption_logs`
- `event_flags`
- `event_predictions`
- `model_metadata`
- `notifications`
- `outbox_events`
- `recommendation_cache`
- `security_alerts`
- `ssg_event_attendance`
- `student_risk_scores`

## Why These Tables Were Removed

- they are not represented by the current SQLAlchemy models in `Backend/app/models`
- they are not queried by the mounted routers in `Backend/app/main.py`
- they do not support the current notifications, security, governance, import, attendance, event, or auth flows
- the repo dump showed them as empty legacy tables

## Migrations

- migration file: `Backend/alembic/versions/9b3e1f2c4d5a_drop_legacy_unused_tables.py`
  - drops the first batch of legacy unused tables with `DROP TABLE IF EXISTS ... CASCADE`
- migration file: `Backend/alembic/versions/a6c4e2f1b9d7_drop_legacy_event_attendance_tables.py`
  - drops the remaining legacy `event_attendance` and `ssg_event_attendance` tables with `DROP TABLE IF EXISTS ... CASCADE`
- downgrade: intentionally unsupported because the removed tables are legacy-only and not part of the active backend

## How To Apply

If you run Alembic inside Docker:

- `docker compose exec backend alembic upgrade head`

If you run Alembic from the host machine:

- point Alembic at the real PostgreSQL database used by the app
- then run `alembic upgrade head` from `Backend/`

## How To Test

1. Apply the migration on the target PostgreSQL database.
2. Verify the removed tables no longer exist:

   ```sql
   SELECT table_name
   FROM information_schema.tables
   WHERE table_schema = 'public'
     AND table_name IN (
       'ai_logs',
       'anomaly_logs',
       'attendance_predictions',
       'event_attendance',
       'event_consumption_logs',
       'event_flags',
       'event_predictions',
       'model_metadata',
       'notifications',
       'outbox_events',
       'recommendation_cache',
       'security_alerts',
       'ssg_event_attendance',
       'student_risk_scores'
     );
   ```

3. Smoke-test active backend features:
   - login and password reset
   - attendance routes
   - event routes
   - notification center routes
   - security center routes
   - governance cleanup routes
   - student bulk import routes

## Notes

- this cleanup does not remove current model-backed tables
- this cleanup does not remove `alembic_version`
- this cleanup is safe to run on databases where the legacy tables are already absent because it uses `IF EXISTS`
