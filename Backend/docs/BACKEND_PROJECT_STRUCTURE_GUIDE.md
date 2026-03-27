# Backend Project Structure Guide

## Purpose

This guide documents the current backend module layout so new work lands in the right layer and the app stays readable as it grows.

## Current Canonical Structure

```text
Backend/app/
├── main.py
├── core/
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   └── security.py
├── models/
├── repositories/
├── routers/
├── schemas/
├── services/
├── utils/
├── workers/
└── tests/
```

## Layer Responsibilities

- `core/`
  - shared application wiring
  - settings, database engine/session setup, shared dependencies, and auth/security helpers
- `models/`
  - SQLAlchemy table definitions and model relationships only
- `schemas/`
  - Pydantic request and response models
  - route-owned request payloads should not live inside routers
- `routers/`
  - HTTP routing, dependency injection, and response wiring
  - keep route handlers thin and delegate business rules to services
- `services/`
  - business rules, orchestration, validation, and reusable domain logic
- `workers/`
  - Celery app configuration and background task execution bodies
- `utils/`
  - small reusable helpers with no domain ownership

## Current Backend Conventions

- new SQLAlchemy ORM base definitions should import `declarative_base` from `sqlalchemy.orm`
- new Pydantic schemas should prefer:
  - `model_config = ConfigDict(...)`
  - `field_validator(...)`
  - `model_validate(..., from_attributes=True)` for ORM-to-schema conversion
  - `model_dump()` or `model_copy(...)` instead of older v1 serialization helpers
- schema example values should be declared through `json_schema_extra`
- forward-reference-heavy schemas should finish with `model_rebuild()` instead of `update_forward_refs()`

## Key Refactors Applied

- database engine, session factory, and shared DB dependency now live in:
  - `Backend/app/core/database.py`
  - `Backend/app/core/dependencies.py`
- canonical Celery modules now live in:
  - `Backend/app/workers/celery_app.py`
  - `Backend/app/workers/tasks.py`
- department and program CRUD business rules now live in:
  - `Backend/app/services/department_service.py`
  - `Backend/app/services/program_service.py`
- manual and bulk attendance request schemas now live in:
  - `Backend/app/schemas/attendance_requests.py`
- auth-side async dispatch orchestration now lives in:
  - `Backend/app/services/auth_task_dispatcher.py`
- Phase 4 router packages now live in:
  - `Backend/app/routers/users/`
    - `accounts.py`
    - `students.py`
    - `roles.py`
    - `passwords.py`
    - `shared.py`
  - `Backend/app/routers/events/`
    - `crud.py`
    - `queries.py`
    - `workflow.py`
    - `attendance_queries.py`
    - `shared.py`
  - `Backend/app/routers/attendance/`
    - `check_in_out.py`
    - `reports.py`
    - `overrides.py`
    - `records.py`
    - `shared.py`
- Phase 4 service packages now live in:
  - `Backend/app/services/email_service/`
    - `config.py`
    - `transport.py`
    - `rendering.py`
    - `use_cases.py`
  - `Backend/app/services/governance_hierarchy_service/`
    - `permissions.py`
    - `unit_lifecycle.py`
    - `membership.py`
    - `engagement.py`
    - `shared.py`

## Phase 4 Exceptions

- `Backend/app/routers/admin_import.py` remains the current explicit oversized-router exception and still needs a later domain split
- `Backend/app/services/governance_hierarchy_service/shared.py` remains a large internal compatibility layer while the new governance package submodules stabilize
- `Backend/app/routers/school_settings.py` no longer needs the planned split because earlier cleanup reduced it below the size threshold
- new code should target the package submodules above instead of adding more logic to the compatibility-heavy shared modules

## Phase 1 Cleanup Notes

- the active backend runtime no longer includes the broken legacy SSG router aliases:
  - `Backend/app/routers/ssg_events_alias.py`
  - `Backend/app/routers/ssg_notifications_admin.py`
- the broken legacy SSG service and task file were removed from the active tree:
  - `Backend/app/services/ssg_event_service.py`
  - `Backend/app/worker/tasks_notifications.py`
- legacy notification-center files were moved into quarantine and are not part of the supported runtime:
  - `archive/2026-03-refactor-quarantine/Backend/app/models/notification.py`
  - `archive/2026-03-refactor-quarantine/Backend/app/routers/notification_center.py`
  - `archive/2026-03-refactor-quarantine/Backend/app/schemas/notification_center.py`
  - `archive/2026-03-refactor-quarantine/Backend/app/services/notification_service.py`
- the experimental tenant database module was also moved into quarantine:
  - `archive/2026-03-refactor-quarantine/Backend/app/core/tenant_database.py`
- quarantined files are kept only for rollback/reference and must not be imported by new code

## How To Place New Code

- add new tables or SQLAlchemy relationships in `models/`
- add request and response payloads in `schemas/`
- add reusable domain logic in `services/`
- keep routers focused on:
  - request parsing
  - dependency injection
  - calling a service
  - returning the service result
- put Celery task bodies in `workers/tasks.py` or a small worker-focused module under `workers/`

## Compatibility Notes

- `app.routers.users`, `app.routers.events`, and `app.routers.attendance` now resolve to package roots instead of single files, but the public router imports remain stable
- `app.services.email_service` and `app.services.governance_hierarchy_service` now resolve to package roots instead of single files, but the public service imports remain stable
- canonical private HTTP routes now live under `/api/*`
- removed compatibility shims:
  - `Backend/app/database.py`
  - `Backend/app/services/auth_background.py`
  - `Backend/app/worker/`
- removed deprecated private route aliases:
  - `/users/*`
  - `/events/*`
  - `/attendance/*`
  - `/programs/*`
  - `/departments/*`
  - `/auth/security/*`
  - `/face/*`
- Celery producers and operational commands must now use canonical `app.workers.*` import paths and task names only
- `archive/2026-03-refactor-quarantine/` is not part of the supported backend import path

## Configuration Notes

- local development can use `Backend/.env` for backend settings
- `Backend/.env` values override process env vars when present
- Alembic reads the same `Backend/.env` for `DATABASE_URL` when present

## How To Test

1. Run `python -m compileall Backend/app`.
2. Run `alembic upgrade head` from `Backend/` so the remaining legacy event-attendance tables are removed if present.
3. Run `Backend\.venv\Scripts\python.exe -m pytest -q Backend/app/tests/test_api.py Backend/app/tests/test_email_service.py Backend/app/tests/test_governance_hierarchy_api.py Backend/app/tests/test_auth_task_dispatcher.py`.
4. Start Celery with the canonical module path:
   - worker: `celery -A app.workers.celery_app.celery_app worker --loglevel=info`
   - beat: `celery -A app.workers.celery_app.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule`
5. Smoke-test:
   - `POST /login`
   - `POST /auth/mfa/verify`
   - `GET /api/users/me/`
   - `POST /api/admin/import-students/preview`
   - `POST /api/admin/import-students`
   - `POST /api/attendance/manual`
   - `GET /api/departments`
   - `GET /api/programs`
