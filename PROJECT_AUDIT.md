# Project Audit: RIZAL_v1

Audit date: 2026-03-23

## Audit Scope And Method

- I inspected the repository structure under `Backend/`, `Frontend/`, `Databse/`, and `tools/`.
- I read the backend entrypoints, router modules, core configuration/security modules, major services, models, schemas, worker tasks, tests, and deployment files.
- I read the frontend entrypoints, routing layer, auth/state helpers, API modules, large page components, and deployment config.
- I extracted the mounted FastAPI route surface by importing `Backend/app/main.py` with local stubs for missing native face libraries. That mounted surface contained 149 API routes.
- I dumped `SQLAlchemy` metadata from the active ORM model set. That metadata contained 37 active tables plus `alembic_version` in the generated ERD document.
- I did not inspect a live production database directly. Database statements below are based on ORM metadata, migrations, and repository code unless marked otherwise.
- I could not run the full backend test suite in the current interpreter because `face_recognition` is missing and `Backend/app/tests/conftest.py` imports `app.main` at import time. That limitation is itself an audit finding.

## 1. Executive Summary

### What This Project Does

This is a school attendance platform called "VALID8" for:

- student login and profile access
- event creation and management
- event attendance tracking
- face-based attendance and face enrollment
- school-specific administration
- bulk student import
- governance / student-organization hierarchy management
- notification and security features
- subscription and governance/privacy settings

In plain English: it lets a platform admin create schools, lets each school manage students and events, lets students check in to events, and adds governance hierarchy and face-recognition features on top.

### Main Business Purpose

The primary business purpose is school-scoped event attendance management with stronger identity controls than a normal attendance app. The system is trying to sell a combination of:

- event attendance operations
- facial verification / attendance
- campus administration
- governance hierarchy for SSG/SG/ORG structures
- school branding / multi-school support

### Main User Flows

The most important flows implemented in code are:

1. Platform admin creates and manages schools in `Backend/app/routers/school.py`.
2. Campus admin logs in, manages departments/programs/users/events, imports students, and reviews password reset requests.
3. Student logs in, enrolls face data if required, views events, and records attendance.
4. Governance officers access scoped dashboards, members, announcements, and student notes through `Backend/app/routers/governance_hierarchy.py`.
5. Background workers process bulk imports, send onboarding/MFA/security emails, and synchronize event workflow state.

### High-Level Architecture

The implemented architecture is:

- Frontend: React 19 + TypeScript + Vite SPA in `Frontend/src/`
- Backend: FastAPI + SQLAlchemy + Pydantic + Celery in `Backend/app/`
- Database: PostgreSQL in production intent; SQLite is used in tests and partially in the dormant tenant helper
- Queue/cache: Redis for Celery broker/result backend
- File storage: local filesystem paths for import previews and school logos
- Deployment intent: Docker Compose locally, Railway/Vercel style cloud deployment for backend/frontend

Practical runtime architecture is a shared-database multi-tenant app where school scope is enforced in code and rows are school-tagged. It is not truly tenant-per-school at runtime.

### Production Readiness Assessment

My assessment is:

- Functionally ambitious
- Partially production-intended
- Structurally inconsistent
- Clearly AI-assisted or AI-generated across large parts of the codebase
- Not clean enough to trust blindly

This is not a toy demo, because some parts are real and fairly involved:

- event timing logic
- governance hierarchy
- MFA/session history
- import processing

But it is also not a clean, intentional production codebase. It looks like a real system that kept growing without a strong architectural owner. The current state is best described as:

`production-intended application with significant architectural drift, dead subsystems, duplicated flows, and AI-generated consistency problems`

## 2. Full Project Structure Breakdown

### Root Level

| Path | Purpose | Assessment |
| --- | --- | --- |
| `README.md` | root project readme | stale and too shallow |
| `.env` | root environment file used by Compose | dangerous if treated as the only source of truth |
| `docker-compose.yml` | main local stack definition | broken on Linux because it uses `./backend` and `./frontend` instead of `./Backend` and `./Frontend` |
| `docker-compose.prod.yml` | supposed production stack | stale and invalid because `restart: unless-` is truncated for Redis |
| `Backend/` | FastAPI backend and workers | core of the system |
| `Frontend/` | React SPA | core of the system |
| `Databse/` | database-related image assets | misspelled folder name; not a real database module |
| `tools/` | ad hoc helper scripts | useful but somewhat stale |
| multiple `*.txt` / `*.md` artifacts at root | planning dumps, API dumps, audit notes | cluttered; indicates low documentation discipline |

The root is noisy. It contains useful artifacts, but the signal-to-noise ratio is poor.

### Backend Structure

`Backend/` contains:

| Path | Purpose |
| --- | --- |
| `Backend/app/main.py` | FastAPI entrypoint |
| `Backend/app/core/` | config, DB, dependencies, security, tenant helpers |
| `Backend/app/models/` | SQLAlchemy models |
| `Backend/app/schemas/` | Pydantic request/response schemas |
| `Backend/app/routers/` | FastAPI route modules |
| `Backend/app/services/` | business logic / orchestration services |
| `Backend/app/repositories/` | repository layer, currently basically only import repo |
| `Backend/app/workers/` | active Celery app and tasks |
| `Backend/app/worker/` | legacy compatibility worker package; partly broken |
| `Backend/app/tests/` | backend tests |
| `Backend/alembic/` | Alembic config and migrations |
| `Backend/docs/` | backend-specific docs |
| `Backend/models/MiniFASNetV2.onnx` | anti-spoof / liveness model file |
| `Backend/scripts/run-service.sh` | service mode entrypoint for web/worker/beat/migrate |
| `Backend/requirements.txt` | Python dependencies |

#### Backend Entry Points

- API entrypoint: `Backend/app/main.py`
- DB/session compatibility wrapper: `Backend/app/database.py`
- Worker entrypoint: `Backend/app/workers/celery_app.py`
- Container runtime entrypoint: `Backend/scripts/run-service.sh`

#### How Backend Boots

1. `uvicorn app.main:app` starts `Backend/app/main.py`.
2. `main.py` imports `get_settings()` from `Backend/app/core/config.py`.
3. `main.py` imports all mounted router modules.
4. Those routers import services, models, dependencies, and security helpers.
5. `FastAPI` app is created and `CORSMiddleware` is registered.
6. Mounted routes are included.
7. school logo storage is mounted as static files from `settings.school_logo_public_prefix`.

Important side effect: because routers import face-recognition services at import time, missing native face dependencies can break unrelated app startup.

### Frontend Structure

`Frontend/` contains:

| Path | Purpose | Assessment |
| --- | --- | --- |
| `Frontend/src/main.tsx` | React entrypoint | standard |
| `Frontend/src/App.tsx` | routing and protected-route composition | central but too large |
| `Frontend/src/api/` | fetch helpers / API wrappers | inconsistent quality |
| `Frontend/src/pages/` | route-level pages | many oversized files |
| `Frontend/src/components/` | reusable UI components | mixed quality |
| `Frontend/src/dashboard/` | dashboard pages by role | clear enough |
| `Frontend/src/hooks/` | custom hooks | useful but limited |
| `Frontend/src/context/UserContext.tsx` | branding/user context | narrow scope |
| `Frontend/public/` | static assets | normal |
| `Frontend/vite.config.ts` | dev/build config | mostly fine |
| `Frontend/vercel.json` | SPA rewrite config | simple and valid |
| `Frontend/Dockerfile.prod` | production image build | fine |
| `Frontend/nginx.prod.conf` | static SPA + API proxy | good, but works around backend route inconsistency |
| `Frontend/README.md` | docs | essentially useless default Vite template |
| `Frontend/convex/` | unrelated Convex files | inferred abandoned experiment |
| `Frontend/events-api-mock/` | separate mock server | inferred abandoned experiment |

#### Frontend Entry Points

- Browser entrypoint: `Frontend/src/main.tsx`
- App routing shell: `Frontend/src/App.tsx`

#### How Frontend Boots

1. `main.tsx` applies stored theme.
2. It wraps the app in `BrowserRouter` and `UserProvider`.
3. `App.tsx` lazy-loads most pages.
4. `ProtectedRoute.tsx` enforces auth, role, password-change, and student face-enrollment gates.
5. Page components call `Frontend/src/api/*.ts` helpers.

### Databse Folder

`Databse/` contains only:

- `ai_logs.png`
- `database_schema.png`

This is not a functional module. It is an asset bucket with a typo in the folder name.

### Tools Folder

`tools/` contains:

- `generate_database_schema_png.py`
- `load_test.py`
- `start-ngrok.ps1`
- `stop-ngrok.ps1`

`tools/load_test.py` is useful, but it contains stale API knowledge. It calls `/api/governance/units/my-access`, while the mounted backend route is `/api/governance/access/me`.

### Configuration Across Environments

Configuration is fragmented:

- `Backend/app/core/config.py` reads `Backend/.env`, not the root `.env`.
- Docker Compose reads the root `.env`.
- Frontend reads `import.meta.env.VITE_API_URL` and `VITE_DEV_PROXY_TARGET`.
- Vite dev proxy rewrites `/api/*` to backend paths.
- Nginx production proxy also rewrites `/api/*`.

This split is a real maintainability risk. A developer can easily change the wrong `.env` and think the system is broken.

## 3. Detailed Application Flow

### Backend Request Lifecycle

The standard backend flow is:

1. `FastAPI` route receives a request.
2. dependency injection resolves `get_db()` and auth dependencies from `Backend/app/core/dependencies.py` and `Backend/app/core/security.py`.
3. router function performs light orchestration.
4. business rules may be delegated to a service under `Backend/app/services/`.
5. direct SQLAlchemy queries are often still executed inside routers.
6. the same request usually commits directly inside the router.

This is not a strict controller/service/repository architecture. It is a hybrid:

- some logic is centralized in services
- some logic remains in routers
- repository abstraction is used only for import paths

### Startup Flow

#### Backend

- `Backend/app/main.py` creates the app.
- CORS is loaded from `settings.cors_allowed_origins`.
- routers are included.
- school-logo static directory is created and mounted.

#### Worker

- `Backend/scripts/run-service.sh` reads `SERVICE_MODE`.
- `SERVICE_MODE=web` starts `uvicorn`.
- `SERVICE_MODE=worker` starts Celery worker.
- `SERVICE_MODE=beat` starts Celery beat.
- `SERVICE_MODE=migrate` runs `alembic upgrade head`.

### Authentication Flow

The implemented login flow is more complex than average:

1. `POST /login` in `Backend/app/routers/auth.py` authenticates email/password through `authenticate_user()` in `Backend/app/core/security.py`.
2. `validate_login_account_state()` rejects inactive users and inactive schools.
3. `should_require_mfa()` in `Backend/app/services/security_service.py` may require MFA.
4. If MFA is required:
   - an `mfa_challenges` row is created
   - email is sent through background task dispatch
   - response contains `token_type="mfa"` and no bearer token yet
5. After MFA, `issue_login_token_response()` in `Backend/app/services/auth_session.py` determines whether the user is privileged.
6. For `admin` or `campus_admin`, the first token is a `face_pending` token with `face_verification_pending=True`.
7. Privileged users must complete face verification at `/auth/security/face-verify`.
8. Non-privileged users get a full JWT with `jti` and `sid`, and a `user_sessions` row is created.
9. Protected endpoints enforce:
   - active account
   - active school
   - session validity, if JWT contains `jti`
   - password change gate
   - face verification gate for privileged users

This flow is conceptually solid. The weak point is that JWTs without `jti` bypass session checks.

### Password Reset Flow

The password reset flow is not email-token self-service. It is approval-based:

1. Student submits `POST /auth/forgot-password`.
2. Backend creates a `password_reset_requests` row if the target is a non-admin, school-scoped active user.
3. Campus admin or platform admin lists pending requests via `GET /auth/password-reset-requests`.
4. Campus admin approves via `POST /auth/password-reset-requests/{request_id}/approve`.
5. Backend generates a temporary password and emails it directly.

This is unusual but explicit in code. It is operationally heavier than a normal token-reset flow.

### Student Attendance Flow

The end-to-end attendance flow looks like this:

1. Student logs in.
2. `ProtectedRoute.tsx` forces password change or face enrollment when needed.
3. Student opens event pages, usually via `Frontend/src/pages/UpcomingEvents.tsx` and `Frontend/src/pages/StudentEventCheckIn.tsx`.
4. Frontend calculates attendance-window state using `Frontend/src/utils/eventAttendanceWindow.ts`.
5. Student attendance submission hits `Backend/app/routers/attendance.py`.
6. Backend time rules are computed again in `Backend/app/services/event_time_status.py`.
7. Geofence checks run through `Backend/app/services/event_geolocation.py`.
8. Attendance rows are inserted/updated in `attendances`.
9. Event workflow synchronization can finalize statuses and auto-create absences later.

The important design fact is that attendance logic exists on both frontend and backend. The backend is authoritative, but the frontend duplicates timing rules for UX.

### Event Management Flow

Campus admin event flow:

1. Frontend page `Frontend/src/pages/Events.tsx` calls `Frontend/src/api/eventsApi.ts`.
2. Backend routes in `Backend/app/routers/events.py` validate user scope and payload.
3. Department/program associations are stored via join tables:
   - `event_department_association`
   - `event_program_association`
4. Event timing defaults can come from school or governance-unit settings.
5. Background task `sync_event_workflow_statuses` periodically moves events across status states and finalizes attendance-related state.

### Bulk Import Flow

The new bulk import flow is the most important operational flow for school onboarding:

1. Frontend `Frontend/src/pages/SchoolImportUsers.tsx` uploads a file.
2. `POST /api/admin/import-students/preview` in `Backend/app/routers/admin_import.py` accepts `.csv` directly and normalizes `.xlsx` through `Backend/app/services/import_file_service.py`.
3. Validation runs in `Backend/app/services/import_validation_service.py`.
4. Approved preview rows are persisted as preview manifests under `IMPORT_STORAGE_DIR/previews/`.
5. Commit call `POST /api/admin/import-students` accepts a `preview_token`, not the original file.
6. `StudentImportService` reads the preview manifest.
7. `ImportRepository` bulk-creates missing departments/programs/program-department links.
8. repository bulk-inserts users, roles, and student profiles.
9. onboarding emails are dispatched outside the critical path.
10. job progress is read from `bulk_import_jobs`.

This is substantially better than the legacy inline import in `Backend/app/routers/school_settings.py`, but both systems still exist.

### Governance Flow

Governance is the most coupled flow in the system:

1. User hits a governance route.
2. `get_current_governance_route_user` and related helpers resolve the current user and school scope.
3. `Backend/app/services/governance_hierarchy_service.py` loads membership, parent units, permissions, and school/program/department relations.
4. The service enforces hierarchy constraints:
   - one school-wide SSG
   - SG under SSG
   - ORG under SG
   - SG department scoping
   - ORG program scoping inside SG department
5. Frontend `useGovernanceAccess()` caches `/api/governance/access/me` in memory and localStorage.
6. Protected routes may require governance unit types and specific permission codes.

This subsystem is powerful, but it is also a single very large service file that many other modules depend on.

### Background Jobs / Async Processing

Active async mechanisms:

- Celery worker in `Backend/app/workers/celery_app.py`
- Celery beat in `Backend/app/workers/celery_app.py`
- tasks in `Backend/app/workers/tasks.py`

Active task types:

- student bulk import processing
- event workflow synchronization
- onboarding emails
- MFA emails
- login security notifications

Dead or broken async compatibility modules also exist under `Backend/app/worker/`.

## 4. Database Analysis

### Database Technologies Used

- Primary intended database: PostgreSQL
- ORM: SQLAlchemy
- Migration tool: Alembic
- Test database: in-memory SQLite in `Backend/app/tests/conftest.py`
- Dormant tenant helper: can create SQLite tenant files or PostgreSQL tenant DB URLs, but is not operational in the current runtime

### Active Schema Shape

Active ORM metadata includes 37 tables:

- identity and school core
- academic structure
- events and attendance
- governance hierarchy
- import jobs
- notification/security/subscription/privacy tables

The generated ERD in `Backend/docs/DATABASE_ERD.md` reflects the active schema, not the dead/unmounted models.

### Practical Multi-Tenancy Model

The practical tenancy model is:

- single shared database
- `school_id` row scoping
- role and request-time authorization

`Backend/app/core/tenant_database.py` strongly suggests a planned per-school tenant-database model, but that module is not viable because it imports `TenantUserDirectory`, which is no longer present in active models. This is an important architectural truth:

`implemented system = shared-db school scoping`

not

`implemented system = one database per school`

### Schema Evolution And Migrations

- There are 39 migration files in `Backend/alembic/versions/`.
- Migration naming shows repeated feature accretion: SSG, event attendance, governance, imports, branding, security, notifications.
- Several migration filenames refer to legacy features that are not cleanly represented in the active runtime.
- `Backend/alembic/env.py` imports active model modules explicitly. It does not import `Backend/app/models/notification.py` or `Backend/app/models/event_attendance.py`, which means those models are outside the active Alembic target metadata.

This is schema drift.

### Major Schema Problems

1. `user_roles` is missing a uniqueness constraint on `(user_id, role_id)`.
2. `departments.school_id` is nullable.
3. `programs.school_id` is nullable.
4. `schools` stores both `name` and `school_name`.
5. some older/dead models are no longer part of the active migration graph.
6. notification functionality is split across `notification_logs` and an inactive `notifications` table model.
7. the dormant tenant subsystem references tables/models that no longer exist.

### Explicit Vs Inferred Notes

- Explicit: active ORM tables listed in `Base.metadata`.
- Explicit: `Backend/docs/DATABASE_ERD.md` documents the same active tables.
- Inferred: some older migrations likely created legacy tables not used anymore.
- Inferred: production DB may contain residue from old migrations/features even if current ORM no longer maps them.

## 5. Components And Modules

### Backend Core Modules

| Module | What it does | What depends on it | Assessment |
| --- | --- | --- | --- |
| `Backend/app/main.py` | creates FastAPI app and mounts routers/static files | entire API | simple but imports too much at startup |
| `Backend/app/core/config.py` | central settings object | all backend layers | important but env split is confusing |
| `Backend/app/core/database.py` | engine/session factory/pool diagnostics | routers, services, workers | fine |
| `Backend/app/core/security.py` | JWT decoding, role checks, school-status checks, auth dependencies | almost every protected route | critical, moderately solid, but jti bypass risk |
| `Backend/app/core/dependencies.py` | `get_db()` | all routers | fine |
| `Backend/app/database.py` | compatibility re-export | legacy imports | indicates architecture drift |
| `Backend/app/core/tenant_database.py` | planned tenant DB provisioning | no active runtime path | broken / misleading |

### Backend Service Modules

| Module | What it does | Used by | Assessment |
| --- | --- | --- | --- |
| `Backend/app/services/auth_session.py` | token/session response generation | auth routes | good centralization |
| `Backend/app/services/security_service.py` | MFA, sessions, login history, revocation | auth + security center | one of the stronger modules |
| `Backend/app/services/event_time_status.py` | event timing rules and attendance windows | events, attendance, public attendance | good central logic, Manila-biased |
| `Backend/app/services/event_workflow_status.py` | automatic event status progression | worker + some routes | useful |
| `Backend/app/services/student_import_service.py` | import job processing | admin import + workers | important and improved recently |
| `Backend/app/repositories/import_repository.py` | bulk insert/import persistence | student import service | effective but very specialized |
| `Backend/app/services/governance_hierarchy_service.py` | hierarchy, permissions, dashboards, notes, announcements | many routers and frontend flows | too large, too central, high-risk |
| `Backend/app/services/logo_storage_service.py` | logo validation and storage | school branding routes | relatively defensive |
| `Backend/app/services/notification_center_service.py` | notification preference/logging/email dispatch | notifications + auth + workers | partly real, partly placeholder |
| `Backend/app/services/face_recognition.py` | face encoding, matching, liveness | face/security/public attendance routes | operationally fragile because of heavy import dependencies |
| `Backend/app/services/ssg_event_service.py` | old SSG event subsystem | dead legacy routes/tasks | broken |
| `Backend/app/services/notification_service.py` | writes old `notifications` table | dead SSG feature | dead |

### Backend Router Modules

Important mounted routers:

- `users.py`
- `events.py`
- `attendance.py`
- `auth.py`
- `school.py`
- `school_settings.py`
- `admin_import.py`
- `notifications.py`
- `security_center.py`
- `governance.py`
- `governance_hierarchy.py`
- `public_attendance.py`

Suspicious or inactive routers:

- `notification_center.py` exists but is not mounted in `main.py`.
- `ssg_events_alias.py` exists but is not mounted and has broken imports.
- `ssg_notifications_admin.py` exists but is not mounted and has broken imports.

### Frontend Core Modules

| Module | What it does | Assessment |
| --- | --- | --- |
| `Frontend/src/main.tsx` | bootstraps app and provider tree | normal |
| `Frontend/src/App.tsx` | route graph and lazy loading | central but too large |
| `Frontend/src/components/ProtectedRoute.tsx` | route gating by role/governance/password/face state | important, localStorage-heavy |
| `Frontend/src/api/authApi.ts` | login, token persistence, logout behavior | central, inconsistent storage strategy |
| `Frontend/src/hooks/useGovernanceAccess.ts` | governance access cache and hook | useful but adds hidden client-side state |
| `Frontend/src/context/UserContext.tsx` | branding/user adornments | narrow and not a full auth store |
| `Frontend/src/pages/Events.tsx` | event UI and orchestration | too large |
| `Frontend/src/pages/ManageUsers.tsx` | campus admin user CRUD page | too large |
| `Frontend/src/pages/Records.tsx` | attendance records UI | too large |
| `Frontend/src/pages/StudentEventCheckIn.tsx` | student event attendance UX | too large, duplicates backend time logic |
| `Frontend/src/pages/SchoolImportUsers.tsx` | import preview/polling UX | functionally important, copy is stale |
| `Frontend/src/pages/NotificationCenter.tsx` | user notification inbox page | depends on dead backend feature |

## 6. Libraries, Frameworks, And Tooling

### Backend Libraries

| Library | Why it is here | Assessment |
| --- | --- | --- |
| `fastapi` | HTTP API framework | correct choice |
| `SQLAlchemy` | ORM and DB access | correct choice |
| `alembic` | migrations | correct choice |
| `psycopg2-binary` | PostgreSQL driver | expected |
| `celery` | background jobs | correct choice |
| `redis` | Celery broker/result backend | expected |
| `python-jose` | JWT handling | standard |
| `passlib` + `bcrypt` | password hashing | standard but import performance/security should be reviewed |
| `openpyxl` | Excel import/template handling | required for current import implementation |
| `face-recognition`, `dlib`, `opencv-python-headless`, `onnxruntime`, `numpy`, `pillow` | face matching and liveness | functional but operationally heavy |
| `email_validator` | email validation | good |
| `python-dotenv` | env loading | fine |
| `SQLAlchemy-Utils` | extra SQLAlchemy helpers | appears unused in inspected code |

### Frontend Libraries

| Library | Why it is here | Assessment |
| --- | --- | --- |
| `react`, `react-dom`, `react-router-dom` | SPA runtime/routing | expected |
| `typescript` | type system | expected |
| `vite` | frontend build/dev server | expected |
| `bootstrap` | styling/layout | used widely |
| `react-icons`, `@fortawesome/*` | icon sets | redundant to have both |
| `chart.js`, `react-chartjs-2`, `recharts` | charts | using both chart stacks is redundant |
| `leaflet`, `react-leaflet` | geolocation/map UI | appropriate |
| `react-modal` | modal dialogs | okay |
| `react-toastify` | toasts | okay |
| `axios` | HTTP client | appears used only in `recordsApi.ts`, which itself appears unused |
| `cors`, `json-server` | mock server / local experiments | not part of the main frontend runtime |
| `framer-motion` | animations | lightly used; acceptable |

### Tooling

- no `.github/` workflows were present
- Vercel config exists for frontend
- Docker production images exist
- Railway deployment is implied by repo artifacts and docs
- no strong lint/test/CI gate is visible from the repository root

## 7. API And Integration Analysis

### API Surface Overview

Mounted API surface extracted from `Backend/app/main.py`:

- 149 mounted routes
- mixed prefix strategy:
  - bare prefixes like `/users`, `/events`, `/attendance`, `/departments`
  - `/api/...` prefixes for school/governance/import/notifications/subscription
- duplicate routes exist for `/users` and `/users/`

This is one of the main API design inconsistencies.

### Router-Level API Review

| Router | Main endpoints | Auth pattern | Notes |
| --- | --- | --- | --- |
| `Backend/app/routers/auth.py` | `/token`, `/login`, `/auth/mfa/verify`, `/auth/change-password`, forgot-password and password-reset-approval routes | mixed public/protected | login flow is richer than typical |
| `Backend/app/routers/security_center.py` | `/auth/security/*` for MFA status, sessions, login history, face reference, face verify, liveness | authenticated; role-dependent | security features are relatively mature |
| `Backend/app/routers/users.py` | `/users`, `/users/{id}`, `/users/{id}/roles`, `/users/{id}/reset-password`, student profile routes | mostly admin/campus admin | duplicated `/users` and `/users/` paths |
| `Backend/app/routers/events.py` | `/events/*` CRUD, stats, time-status, location verification | authenticated | route file is very large |
| `Backend/app/routers/attendance.py` | `/attendance/*` manual/face/bulk/sign-out/reports/stats | authenticated | huge router with mixed concerns |
| `Backend/app/routers/departments.py` | `/departments/*` | read for all authenticated users, write for campus admin | fine except route prefix inconsistency |
| `Backend/app/routers/programs.py` | `/programs/*` | same as departments | fine except route prefix inconsistency |
| `Backend/app/routers/school.py` | `/api/school/*` school CRUD/branding/school IT management | admin or campus admin depending route | overlaps older school-settings responsibilities |
| `Backend/app/routers/school_settings.py` | `/school-settings/*` branding/audit logs/legacy import | admin or campus admin | contains an old inline import subsystem |
| `Backend/app/routers/admin_import.py` | `/api/admin/import-*` preview/commit/status/error downloads | admin or campus admin | current preferred bulk import API |
| `Backend/app/routers/notifications.py` | `/api/notifications/*` preferences, logs, dispatch | authenticated; admin for some actions | uses `notification_logs`, not inbox notifications |
| `Backend/app/routers/governance.py` | `/api/governance/settings`, `consents`, `requests`, retention | role-dependent | privacy/governance settings |
| `Backend/app/routers/governance_hierarchy.py` | `/api/governance/access/me`, `units`, `members`, `permissions`, `announcements`, `student-notes`, `ssg/setup` | governance-aware auth | most feature-rich governance API |
| `Backend/app/routers/public_attendance.py` | `/public-attendance/events/nearby`, `/public-attendance/events/{event_id}/multi-face-scan` | public | kiosk-style public APIs |
| `Backend/app/routers/audit_logs.py` | `/api/audit-logs` | admin/campus admin | simple |
| `Backend/app/routers/subscription.py` | `/api/subscription/*` | admin/campus admin | basic settings/reminders |
| `Backend/app/routers/health.py` | `/health` | public DB-backed check | useful |

### Broken / Inactive API Patterns

1. `Frontend/src/api/notificationsApi.ts` calls `/api/notifications-center/me`, but `Backend/app/routers/notification_center.py` is not mounted in `main.py`.
2. `Backend/app/models/notification.py` backs that route, but it is not part of active Alembic metadata imports.
3. `Frontend/src/api/recordsApi.ts` uses Axios and calls `/api/records`, but I found no mounted backend `/api/records` route and no call sites for that API file.
4. `tools/load_test.py` uses a stale governance route.
5. API URL handling on the frontend contains an explicit `/api/api` collapse workaround in `Frontend/src/api/apiUrl.ts`, which exists only because backend route prefixes are inconsistent.

### Third-Party Integrations

Implemented or partially implemented integrations:

- SMTP via `smtplib` in `Backend/app/services/email_service.py`
- Redis via Celery
- face-recognition stack via `face_recognition`, `dlib`, `onnxruntime`, `opencv`

Not truly integrated / placeholder:

- SMS dispatch in `Backend/app/services/notification_center_service.py` is a placeholder that logs `SMS provider not configured`.
- subscription/billing is settings-oriented; I found no real Stripe/payments integration.
- `Frontend/events-api-mock/` is not integrated into main runtime.

### Mounted Route Inventory Notes

The raw mounted route surface is large. The important operational truth is:

- the mounted routes are the source of truth for what is really alive
- `notification_center.py`, `ssg_events_alias.py`, and `ssg_notifications_admin.py` are not part of that live surface
- any frontend path pointing to those dead routes should be treated as broken until proven otherwise

## 8. State Management And Data Handling

### Frontend State

Frontend state management is ad hoc and spread across:

- `localStorage`
- `sessionStorage`
- React component state
- a narrow `UserContext`
- custom hooks such as `useGovernanceAccess`

This is not a coherent app-state architecture.

### Auth State

Auth data is duplicated in browser storage:

- `authToken`
- `token`
- `access_token`
- `user`
- `userData`

This duplication lives in `Frontend/src/api/authApi.ts`. It increases drift risk and makes debugging harder.

### Governance State

`Frontend/src/hooks/useGovernanceAccess.ts` maintains:

- localStorage cache `valid8.governance.access`
- in-memory singleton cache
- inflight request sharing

This is practical, but it creates hidden coupling between route guards and governance pages.

### Data Fetching

API fetching is inconsistent:

- some files use `buildApiUrl()` from `Frontend/src/api/apiUrl.ts`
- some files hardcode `BASE_URL`
- one file (`recordsApi.ts`) still uses `axios`

This matters because the backend mixes `/api/...` and bare routes. The frontend compensates for backend inconsistency instead of the backend fixing its route design.

### Forms, Validation, Loading, Errors

Patterns observed:

- forms are mostly managed with local `useState`
- validation is mostly manual
- loading and error state are duplicated in many large page components
- retries are mostly manual or absent
- 401 handling is partly centralized, partly page-specific

This is workable, but it scales poorly. The oversized page files already show the cost.

### Hidden Coupling / Anti-Patterns

1. `ProtectedRoute.tsx` depends on the exact shape of the `user` object stored in localStorage.
2. several pages independently implement token lookup and 401 behavior.
3. frontend timing logic duplicates backend timing logic.
4. branding/theme state is partially derived from auth response and partially fetched later.
5. API path workarounds (`/api/api`) are encoded into the frontend.

## 9. Authentication, Authorization, And Security

### What Is Implemented Well

- account active-state enforcement
- school active-state enforcement
- MFA challenge flow for privileged login
- face-verification gate for `admin` and `campus_admin`
- session table with revocation support
- login history
- generic forgot-password response to reduce account enumeration
- logo upload validation in `logo_storage_service.py`

### Role Model

Auth roles are effectively:

- `admin`
- `campus_admin`
- `student`

Governance roles (`ssg`, `sg`, `org`) are not treated as base auth roles in `Backend/app/services/auth_session.py`. Governance permissions are modeled separately through membership and permission tables.

### Security Risks

1. `SECRET_KEY` defaults to `change-this-secret-in-production` in `Backend/app/core/config.py`.
2. JWT session enforcement only occurs if the token has `jti`; `assert_session_valid()` returns early for `None`.
3. tokens are stored in localStorage, which is vulnerable to XSS-driven theft.
4. public attendance throttling uses an in-process dictionary in `Backend/app/routers/public_attendance.py`; it is not shared across instances.
5. face libraries are imported globally and can block service startup.
6. file uploads are validated for logos, but import upload size and file handling still rely on filesystem storage and operational discipline.
7. `Backend/Dockerfile.prod` creates `appuser` but does not switch to `USER appuser`, so the container still runs as root.

### Access Control Risks

- The governance system appears to store `governance_unit_permissions`, but actual checks are driven by `governance_member_permissions`. That means unit-level permissions may not be doing what their names suggest.
- `departments` and `programs` being nullable by school weakens tenant data isolation at the schema level.
- `UserRole` duplicates are possible because `(user_id, role_id)` is not unique.

### CSRF / XSS / Injection Notes

- API auth is bearer-token based, so classical cookie CSRF is less central.
- LocalStorage token storage makes XSS more dangerous.
- I did not see raw SQL string-building patterns suggesting obvious SQL injection in the main paths; most DB access is SQLAlchemy ORM-based.
- SVG upload validation blocks `<script>` and `javascript:` references, which is good.

## 10. Business Logic Deep Dive

### Event Attendance Rules

Core event timing rules are centralized in `Backend/app/services/event_time_status.py`:

- early check-in opens before start time
- present vs late cutoffs use `late_threshold_minutes`
- sign-out uses `sign_out_grace_minutes`
- optional present/late override windows can replace normal cutoffs
- timezone defaults to `Asia/Manila`

This is real business logic, not placeholder logic.

### Event Workflow Rules

`Backend/app/services/event_workflow_status.py` and related worker tasks move events through lifecycle states and finalize attendance-related behavior. This is one of the more maintainable parts because time-state progression is at least partly centralized.

### Governance Rules

`Backend/app/services/governance_hierarchy_service.py` implements rules such as:

- only one SSG per school
- SG must belong under SSG
- ORG must belong under SG
- SG is department-scoped
- ORG is program-scoped within its SG department
- member permissions gate management features

The rules themselves are fairly explicit. The main problem is concentration: too many rules live in one file.

### Import Rules

Current import rules in `Backend/app/routers/admin_import.py`, `student_import_service.py`, and `import_repository.py` include:

- preview-first commit token
- duplicate detection in preview
- bulk creation of departments/programs/program links
- school-scoped locking
- shared password-pending hash per import job
- deferred onboarding email dispatch

This logic is materially better than the legacy path in `school_settings.py`.

### Password And Onboarding Rules

- new imported users are put into password-pending onboarding state
- first access is expected through forgot-password approval flow
- temporary-password reset requests remain admin-approved

This is coherent internally, but it is not a standard SaaS onboarding pattern.

### Logic Duplication

The biggest duplications I found are:

1. two user import systems
2. duplicated attendance time-window logic between backend and frontend
3. duplicated notification concepts
4. overlapping school branding/settings behavior across `school.py` and `school_settings.py`
5. overlapping auth/token utilities scattered across pages and `authApi.ts`

## 11. Code Quality And AI-Generated Code Audit

### Strong AI-Generated Signals

I see repeated patterns that strongly suggest AI generation:

- nearly every backend file begins with a synthetic `Use / Where to use / Role` docstring
- comments like `# ===== ADD THIS METHOD =====`
- comments like `# REMOVED lazy="joined"`
- helper comments that read like prompt artifacts
- placeholder business data such as `address=f"{payload.school_name} Address"` in `Backend/app/routers/school.py`
- frontend defaults that invent data, such as `subscription_status: "trial"` and `active_status: true` in `Frontend/src/authFlow.ts`

### Reliability Assessment By Area

Most reliable areas:

- `Backend/app/services/event_time_status.py`
- `Backend/app/services/security_service.py`
- `Backend/app/services/auth_session.py`
- current bulk import path (`admin_import.py` + `student_import_service.py` + `import_repository.py`)
- logo validation service

Needs strong human review:

- `Backend/app/services/governance_hierarchy_service.py`
- `Backend/app/routers/attendance.py`
- `Backend/app/routers/events.py`
- `Backend/app/routers/users.py`
- `Frontend/src/pages/Events.tsx`
- `Frontend/src/pages/ManageUsers.tsx`
- `Frontend/src/pages/Records.tsx`
- `Frontend/src/pages/StudentEventCheckIn.tsx`

Looks stale, dead, or misleading:

- `Backend/app/core/tenant_database.py`
- `Backend/app/models/notification.py`
- `Backend/app/models/event_attendance.py`
- `Backend/app/routers/notification_center.py`
- `Backend/app/routers/ssg_events_alias.py`
- `Backend/app/routers/ssg_notifications_admin.py`
- `Backend/app/services/ssg_event_service.py`
- `Backend/app/services/notification_service.py`
- `Backend/app/worker/tasks_attendance.py`
- `Backend/app/worker/tasks_notifications.py`
- `Frontend/src/api/recordsApi.ts`
- `Frontend/src/pages/NotificationCenter.tsx` as currently wired

### Architectural Smells

- giant router files
- giant page files
- inconsistent API prefixes
- compatibility layers that never got retired
- planned subsystems left half-implemented
- stale migrations/docs/deployment files
- frontend compensating for backend inconsistencies

## 12. Dependency Graph / Coupling Analysis

### Major Dependency Relationships

Core backend dependency shape:

- `main.py` -> routers
- routers -> `core/security.py`, `core/dependencies.py`, models, services
- services -> models, config, other services
- workers -> services and repositories

The most central backend nodes are:

- `Backend/app/core/security.py`
- `Backend/app/services/governance_hierarchy_service.py`
- `Backend/app/services/event_time_status.py`
- `Backend/app/services/security_service.py`

Core frontend dependency shape:

- `main.tsx` -> `App.tsx`
- `App.tsx` -> pages + `ProtectedRoute.tsx`
- pages -> API modules
- `authApi.ts` + `useGovernanceAccess.ts` + localStorage -> many pages

### Tightly Coupled Areas

1. Governance hierarchy logic is tightly coupled to:
   - users
   - events
   - attendance
   - governance dashboards
   - route access control
2. Auth state is tightly coupled to localStorage structure.
3. Attendance flow is tightly coupled across:
   - frontend page logic
   - geolocation helpers
   - event time status service
   - attendance router
4. Import flow is tightly coupled to filesystem preview manifests and Celery availability.

### Fragile Areas

- governance service refactors could break many routes
- face-recognition dependency issues can break unrelated startup/test paths
- route-prefix changes can break frontend API helpers and Nginx/Vite proxy assumptions
- schema cleanup around notifications or tenant DBs could break stale code that still imports those modules

### What Should Be Refactored First

1. remove dead subsystems and stale routes/models
2. normalize API prefixes
3. consolidate import flows to one supported path
4. split governance service into smaller modules
5. introduce a real frontend auth/state abstraction

## 13. Environment, Build, And Deployment

### Local Development Setup

Backend local assumptions:

- Python deps from `Backend/requirements.txt`
- PostgreSQL and Redis available, often via Docker
- optional SMTP via Mailpit
- face-recognition native stack installed if face routes/tests need to import cleanly

Frontend local assumptions:

- Node/npm
- `VITE_API_URL` or Vite proxy config

### Important Environment Variables

Key backend env vars from `Backend/app/core/config.py`:

- `DATABASE_URL`
- `DATABASE_ADMIN_URL`
- `DB_POOL_SIZE`
- `DB_MAX_OVERFLOW`
- `DB_POOL_TIMEOUT_SECONDS`
- `DB_POOL_RECYCLE_SECONDS`
- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTH_ENABLE_MFA`
- `FACE_MATCH_THRESHOLD`
- `LIVENESS_MIN_SCORE`
- `ALLOW_LIVENESS_BYPASS_WHEN_MODEL_MISSING`
- `ANTI_SPOOF_SCALE`
- `ANTI_SPOOF_MODEL_PATH`
- `GEO_MAX_ALLOWED_ACCURACY_M`
- `GEO_MAX_TRAVEL_SPEED_MPS`
- `EVENT_STATUS_SYNC_ENABLED`
- `EVENT_STATUS_SYNC_INTERVAL_SECONDS`
- `PUBLIC_ATTENDANCE_ENABLED`
- `PUBLIC_ATTENDANCE_MAX_FACES_PER_FRAME`
- `PUBLIC_ATTENDANCE_SCAN_COOLDOWN_SECONDS`
- `PUBLIC_ATTENDANCE_EVENT_LOOKAHEAD_HOURS`
- `TENANT_DATABASE_PREFIX`
- `IMPORT_MAX_FILE_SIZE_MB`
- `IMPORT_CHUNK_SIZE`
- `IMPORT_STORAGE_DIR`
- `IMPORT_RATE_LIMIT_COUNT`
- `IMPORT_RATE_LIMIT_WINDOW_SECONDS`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `CELERY_TASK_TIME_LIMIT_SECONDS`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`
- `LOGIN_URL`
- `SCHOOL_LOGO_STORAGE_DIR`
- `SCHOOL_LOGO_MAX_FILE_SIZE_MB`
- `SCHOOL_LOGO_PUBLIC_PREFIX`
- `CORS_ALLOWED_ORIGINS`

Key frontend env vars:

- `VITE_API_URL`
- `VITE_DEV_PROXY_TARGET`

### Deployment Files Review

Good:

- `Backend/scripts/run-service.sh`
- `Frontend/Dockerfile.prod`
- `Frontend/nginx.prod.conf`
- `Frontend/vercel.json`

Problematic:

- `docker-compose.yml` uses wrong directory case for Linux
- `docker-compose.prod.yml` is invalid
- `Backend/Dockerfile.prod` still runs as root
- `Backend/docs/BACKEND_PRODUCTION_DEPLOYMENT_GUIDE.md` claims compose consolidation and corrected casing, but the repo still contradicts that

### CI/CD

I found:

- no `.github/workflows`
- no obvious CI pipeline files
- no enforced quality gate in-repo

This means release discipline likely depends on manual deployment and human memory.

## 14. Testing And Reliability

### What Tests Exist

There are 17 backend test files under `Backend/app/tests/`, including:

- API tests
- governance hierarchy API tests
- bulk import tests
- event timing and workflow tests
- security/auth tests
- public attendance tests
- email/config tests

This is better than many AI-generated repos.

### What Is Not Tested

- frontend has effectively no test suite
- dead subsystems are not tested meaningfully
- deployment files are not validated by CI
- notification-center inbox path is not covered as an actually mounted feature
- full production-like auth/session behavior is not well simulated

### Test Quality Concerns

`Backend/app/tests/conftest.py` imports `app.main`, so missing face-recognition dependencies can break all tests, even tests unrelated to face features.

Many tests use tokens without `jti`, which means they do not fully exercise session revocation behavior. That makes auth tests less faithful than they look.

### Highest-Risk Untested Areas

1. frontend auth/session flow
2. privileged face-verification flow end-to-end
3. dead-vs-active notification behavior
4. deployment configuration validity
5. governance permission edge cases around unit permissions vs member permissions

## 15. Documentation Gap Analysis

### What Is Documented Well

Backend docs are relatively numerous:

- `Backend/docs/BACKEND_CHANGELOG.md`
- `Backend/docs/BACKEND_BULK_IMPORT_GUIDE.md`
- `Backend/docs/BACKEND_GOVERNANCE_HIERARCHY_GUIDE.md`
- `Backend/docs/BACKEND_EVENT_TIME_STATUS_GUIDE.md`
- `Backend/docs/DATABASE_ERD.md`

### What Is Not Documented Well

- actual frontend architecture
- auth/session/storage model
- route prefix conventions
- which subsystems are dead vs active
- which import path is the supported one
- deployment source of truth
- operational requirements for face-recognition dependencies

### Missing Docs You Need As Owner

1. one authoritative architecture overview
2. one authoritative deployment guide that matches the actual files
3. an active-vs-dead subsystem list
4. a supported API surface map
5. frontend maintainership docs
6. auth/session lifecycle docs
7. recovery/runbook docs for imports, workers, Redis, and face model failures

## 16. Project Risks And Refactor Priorities

### Urgent Fixes

1. Remove or clearly quarantine dead subsystems:
   - `tenant_database.py`
   - dead notification center path
   - dead SSG event subsystem
2. Fix deployment truth:
   - correct `docker-compose.yml`
   - either fix or delete `docker-compose.prod.yml`
   - run backend container as non-root
3. Add unique constraint on `user_roles(user_id, role_id)`.
4. Make `departments.school_id` and `programs.school_id` non-null if data model truly requires school scoping.
5. Enforce session validation for all issued JWTs, including tests and any alternate token flows.

### Near-Term Refactors

1. Pick one supported import API and deprecate the other.
2. Normalize all backend routes under a consistent prefix strategy.
3. Replace frontend token/key duplication with a single auth store abstraction.
4. Split `governance_hierarchy_service.py` into smaller modules.
5. Move face-recognition imports behind optional runtime boundaries so startup/tests do not explode.

### Long-Term Improvements

1. introduce a true frontend state/data-fetching layer
2. standardize response envelopes and error handling
3. prune unused libraries
4. add CI for backend tests, frontend build, and compose validation
5. reconsider the approval-based password-reset UX if product requirements allow it

## 17. Ownership Handoff Report

If I were handing this project to a new technical owner, I would say this first:

### What You Must Understand First

1. This is a shared-database, school-scoped system, not a functioning tenant-database architecture.
2. Governance hierarchy is the most complex and most fragile part of the codebase.
3. There are dead features still present in the repository, especially notifications and SSG legacy code.
4. The current bulk import path is in `admin_import.py`; the old `school_settings.py` import path is legacy and diverges.
5. Frontend auth and routing are heavily localStorage-driven and not cleanly centralized.

### Dangerous Areas

- `Backend/app/services/governance_hierarchy_service.py`
- `Backend/app/routers/attendance.py`
- `Backend/app/routers/events.py`
- `Backend/app/core/security.py`
- `Backend/app/services/face_recognition.py`
- `Frontend/src/App.tsx`
- `Frontend/src/components/ProtectedRoute.tsx`
- `Frontend/src/pages/StudentEventCheckIn.tsx`

### Fragile Dependencies

- face-recognition native stack
- Redis/Celery for import and notifications
- filesystem storage for import previews and logos
- localStorage key shape for frontend auth
- proxy assumptions around `/api` prefixing

### Recommended Next Actions In Order

1. create an active/dead subsystem inventory and stop shipping dead routes/models as if they are supported
2. fix deployment files and env source-of-truth issues
3. normalize API routes and frontend API calls
4. consolidate import paths
5. split governance service and add focused tests around permissions
6. centralize frontend auth/session state
7. add CI that at minimum runs backend tests, frontend build, and config validation

## A. Project Map

```text
Browser
  -> Frontend/src/main.tsx
  -> Frontend/src/App.tsx
  -> ProtectedRoute + role/governance gates
  -> page component
  -> Frontend/src/api/*.ts
  -> HTTP
  -> Backend/app/main.py
  -> router module
  -> core security + DB dependency
  -> service(s) and/or direct ORM queries
  -> PostgreSQL / filesystem / Redis / SMTP

Background flow
  HTTP import request
  -> admin_import router
  -> preview manifest on disk
  -> Celery task
  -> StudentImportService + ImportRepository
  -> DB writes
  -> email task dispatch

Static/media flow
  school branding route
  -> logo_storage_service
  -> SCHOOL_LOGO_STORAGE_DIR
  -> static mount at /media/school-logos
```

High-level code map:

- `Backend/app/main.py`: API entry
- `Backend/app/core/`: config, DB, security
- `Backend/app/models/`: ORM schema
- `Backend/app/routers/`: HTTP endpoints
- `Backend/app/services/`: main business logic
- `Backend/app/workers/`: async tasks
- `Frontend/src/App.tsx`: route graph
- `Frontend/src/api/`: client API wrappers
- `Frontend/src/pages/`: route pages
- `Frontend/src/components/`: shared UI

## B. Database Reference

Notes:

- `!` means non-null.
- `?` means nullable.
- defaults shown only when important.
- relationships are based on active ORM metadata.
- this table covers active ORM tables; dead models are listed after it.

### Core Identity And School

| Table | Fields | Keys / Indexes | Relationships / Notes |
| --- | --- | --- | --- |
| `users` | `id:int!`; `email:varchar(255)!`; `school_id:int?`; `password_hash:varchar(255)!`; `first_name:varchar(100)?`; `middle_name:varchar(100)?`; `last_name:varchar(100)?`; `is_active:bool?=true`; `must_change_password:bool!=true`; `should_prompt_password_change:bool!=false`; `created_at:datetime!` | PK `id`; unique `email`; indexes on `email`, `school_id`, `is_active`, `must_change_password` | FK to `schools`; parent for roles, sessions, security settings, profiles, consents, governance memberships |
| `roles` | `id:int!`; `name:varchar(50)!` | PK `id`; unique/indexed `name` | joined through `user_roles` |
| `user_roles` | `id:int!`; `user_id:int?`; `role_id:int?` | PK `id`; indexes on `user_id`, `role_id`; missing unique `(user_id, role_id)` | many-to-one to `users` and `roles`; schema flaw |
| `schools` | `id:int!`; `name:varchar(255)!`; `school_name:varchar(255)!`; `school_code:varchar(50)?`; `address:varchar(500)!`; `logo_url:varchar(1000)?`; `primary_color:varchar(7)!`; `secondary_color:varchar(7)?`; `subscription_status:varchar(30)!`; `active_status:bool!`; `subscription_plan:varchar(100)!`; `subscription_start:date!`; `subscription_end:date?`; `created_at:datetime!`; `updated_at:datetime!` | PK `id`; unique `school_code`; index `school_name` | parent for most school-scoped tables; duplicate `name`/`school_name` is suspicious |
| `school_settings` | `school_id:int!`; `primary_color:varchar(7)!`; `secondary_color:varchar(7)!`; `accent_color:varchar(7)!`; `event_default_early_check_in_minutes:int!=30`; `event_default_late_threshold_minutes:int!=10`; `event_default_sign_out_grace_minutes:int!=20`; `updated_at:datetime!`; `updated_by_user_id:int?` | PK `school_id` | one-to-one with `schools`; overlaps some branding stored directly on `schools` |
| `school_audit_logs` | `id:int!`; `school_id:int!`; `actor_user_id:int?`; `action:varchar(100)!`; `status:varchar(30)!=success`; `details:text?`; `created_at:datetime!` | PK `id`; indexes on `school_id`, `actor_user_id`, `created_at` | audit trail for school/admin actions |
| `school_subscription_settings` | `school_id:int!`; `plan_name:varchar(50)!=free`; `user_limit:int!=500`; `event_limit_monthly:int!=100`; `import_limit_monthly:int!=10`; `renewal_date:date?`; `auto_renew:bool!=false`; `reminder_days_before:int!=14`; `updated_by_user_id:int?`; `updated_at:datetime!` | PK `school_id` | one-to-one with `schools`; no real billing provider linkage found |
| `school_subscription_reminders` | `id:int!`; `school_id:int!`; `reminder_type:varchar(40)!=renewal_warning`; `status:varchar(20)!=pending`; `due_at:datetime!`; `sent_at:datetime?`; `error_message:text?`; `created_at:datetime!` | PK `id`; indexes on `school_id`, `status`, `due_at`, `created_at` | reminder job log table |
| `user_security_settings` | `user_id:int!`; `mfa_enabled:bool!=false`; `trusted_device_days:int!=14`; `updated_at:datetime!` | PK `user_id` | one-to-one with `users` |
| `user_sessions` | `id:varchar(36)!`; `user_id:int!`; `token_jti:varchar(64)!`; `ip_address:varchar(64)?`; `user_agent:varchar(500)?`; `created_at:datetime!`; `last_seen_at:datetime!`; `revoked_at:datetime?`; `expires_at:datetime!` | PK `id`; unique `token_jti`; indexes on `user_id`, `token_jti`, `created_at`, `expires_at` | session revocation/history table |
| `login_history` | `id:int!`; `user_id:int?`; `school_id:int?`; `email_attempted:varchar(255)!`; `success:bool!`; `auth_method:varchar(50)!`; `failure_reason:varchar(100)?`; `ip_address:varchar(64)?`; `user_agent:varchar(500)?`; `created_at:datetime!` | PK `id`; indexes on `user_id`, `school_id`, `success`, `created_at` | login audit table |
| `mfa_challenges` | `id:varchar(36)!`; `user_id:int!`; `code_hash:varchar(255)!`; `channel:varchar(30)!`; `attempts:int!=0`; `ip_address:varchar(64)?`; `user_agent:varchar(500)?`; `expires_at:datetime!`; `consumed_at:datetime?`; `created_at:datetime!` | PK `id`; indexes on `user_id`, `expires_at`, `created_at` | temporary MFA challenge storage |
| `user_face_profiles` | `user_id:int!`; `face_encoding:blob!`; `provider:varchar(50)!=face_recognition`; `reference_image_sha256:varchar(64)?`; `last_verified_at:datetime?`; `created_at:datetime!`; `updated_at:datetime!` | PK `user_id` | privileged-user face reference storage |
| `password_reset_requests` | `id:int!`; `user_id:int!`; `school_id:int!`; `requested_email:varchar(255)!`; `status:varchar(20)!=pending`; `requested_at:datetime!`; `resolved_at:datetime?`; `reviewed_by_user_id:int?` | PK `id`; indexes on `user_id`, `school_id`, `requested_email`, `status`, `requested_at`, `reviewed_by_user_id` | approval-based password reset workflow |

### Academic Structure, Events, And Attendance

| Table | Fields | Keys / Indexes | Relationships / Notes |
| --- | --- | --- | --- |
| `departments` | `id:int!`; `school_id:int?`; `name:varchar!` | PK `id`; unique `(school_id, name)`; indexes `id`, `school_id` | belongs to `schools`; nullable `school_id` is a schema smell |
| `programs` | `id:int!`; `school_id:int?`; `name:varchar!` | PK `id`; unique `(school_id, name)`; indexes `id`, `school_id` | belongs to `schools`; nullable `school_id` is a schema smell |
| `program_department_association` | `program_id:int!`; `department_id:int!` | composite PK | joins programs to departments |
| `student_profiles` | `id:int!`; `user_id:int?`; `school_id:int!`; `student_id:varchar(50)?`; `department_id:int?`; `program_id:int?`; `year_level:int!=1`; `face_encoding:blob?`; `is_face_registered:bool?=false`; `face_image_url:varchar(500)?`; `registration_complete:bool?=false`; `section:varchar(50)?`; `rfid_tag:varchar(100)?`; `last_face_update:datetime?` | PK `id`; unique `user_id`; unique `rfid_tag`; unique `(school_id, student_id)`; indexes on school/student/department/program/face flags/section | core student academic + biometric profile table |
| `events` | `id:int!`; `school_id:int!`; `name:varchar(100)!`; `location:varchar(200)?`; `geo_latitude:float?`; `geo_longitude:float?`; `geo_radius_m:float?`; `geo_required:bool!=false`; `geo_max_accuracy_m:float?`; `early_check_in_minutes:int!=30`; `late_threshold_minutes:int!=10`; `sign_out_grace_minutes:int!=20`; `sign_out_override_until:datetime?`; `present_until_override_at:datetime?`; `late_until_override_at:datetime?`; `start_datetime:datetime!`; `end_datetime:datetime!`; `status:varchar(9)!` | PK `id`; indexes on `id`, `school_id` | event master table |
| `event_department_association` | `event_id:int!`; `department_id:int!` | composite PK | event scope join table |
| `event_program_association` | `event_id:int!`; `program_id:int!` | composite PK | event scope join table |
| `attendances` | `id:int!`; `student_id:int?`; `event_id:int?`; `time_in:datetime!`; `time_out:datetime?`; `method:varchar(50)?`; `status:varchar(7)!=present`; `check_in_status:varchar(16)?`; `check_out_status:varchar(16)?`; `verified_by:int?`; `notes:varchar(500)?`; `geo_distance_m:float?`; `geo_effective_distance_m:float?`; `geo_latitude:float?`; `geo_longitude:float?`; `geo_accuracy_m:float?`; `liveness_label:varchar(32)?`; `liveness_score:float?` | PK `id`; indexes on `id`, `student_id`, `event_id` | core attendance record table; `method` is free text rather than enum |

### Import, Notification, Privacy, And Ops

| Table | Fields | Keys / Indexes | Relationships / Notes |
| --- | --- | --- | --- |
| `bulk_import_jobs` | `id:varchar(36)!`; `created_by_user_id:int?`; `target_school_id:int!`; `status:varchar(20)!=pending`; `original_filename:varchar(255)!`; `stored_file_path:varchar(1024)!`; `failed_report_path:varchar(1024)?`; `total_rows:int!=0`; `processed_rows:int!=0`; `success_count:int!=0`; `failed_count:int!=0`; `eta_seconds:int?`; `error_summary:text?`; `is_rate_limited:bool!=false`; `started_at:datetime?`; `completed_at:datetime?`; `created_at:datetime!`; `updated_at:datetime!`; `last_heartbeat:datetime?` | PK `id`; indexes on `created_by_user_id`, `target_school_id`, `status`, `created_at` | import orchestration state |
| `bulk_import_errors` | `id:int!`; `job_id:varchar(36)!`; `row_number:int!`; `error_message:text!`; `row_data:json?`; `created_at:datetime!` | PK `id`; indexes on `job_id`, `created_at` | per-row import error storage |
| `email_delivery_logs` | `id:int!`; `job_id:varchar(36)?`; `user_id:int?`; `email:varchar(255)!`; `status:varchar(20)!`; `error_message:text?`; `retry_count:int!=0`; `created_at:datetime!`; `updated_at:datetime!` | PK `id`; indexes on `job_id`, `user_id`, `email`, `status` | import/email delivery status |
| `user_notification_preferences` | `user_id:int!`; `email_enabled:bool!=true`; `sms_enabled:bool!=false`; `sms_number:varchar(40)?`; `notify_missed_events:bool!=true`; `notify_low_attendance:bool!=true`; `notify_account_security:bool!=true`; `notify_subscription:bool!=true`; `updated_at:datetime!` | PK `user_id` | notification preferences |
| `notification_logs` | `id:int!`; `school_id:int?`; `user_id:int?`; `category:varchar(50)!`; `channel:varchar(20)!`; `status:varchar(20)!`; `subject:varchar(255)!`; `message:text!`; `error_message:text?`; `metadata_json:json?`; `created_at:datetime!` | PK `id`; indexes on `school_id`, `user_id`, `category`, `channel`, `status`, `created_at` | active notification/audit log system |
| `data_governance_settings` | `school_id:int!`; `attendance_retention_days:int!=1095`; `audit_log_retention_days:int!=3650`; `import_file_retention_days:int!=180`; `auto_delete_enabled:bool!=false`; `updated_by_user_id:int?`; `updated_at:datetime!` | PK `school_id` | privacy/retention settings per school |
| `user_privacy_consents` | `id:int!`; `user_id:int!`; `school_id:int!`; `consent_type:varchar(50)!`; `consent_granted:bool!=true`; `consent_version:varchar(20)!=v1`; `source:varchar(50)!=web`; `created_at:datetime!` | PK `id`; indexes on `user_id`, `school_id`, `consent_type`, `created_at` | consent tracking |
| `data_requests` | `id:int!`; `school_id:int!`; `requested_by_user_id:int?`; `target_user_id:int?`; `request_type:varchar(20)!`; `scope:varchar(50)!=user_data`; `status:varchar(20)!=pending`; `reason:text?`; `details_json:json?`; `output_path:varchar(1024)?`; `handled_by_user_id:int?`; `created_at:datetime!`; `resolved_at:datetime?` | PK `id`; indexes on `school_id`, `request_type`, `status`, `requested_by_user_id`, `target_user_id`, `created_at` | governance/privacy request processing |
| `data_retention_run_logs` | `id:int!`; `school_id:int!`; `dry_run:bool!=true`; `status:varchar(20)!=completed`; `summary:text?`; `created_at:datetime!` | PK `id`; indexes on `school_id`, `created_at` | retention job execution log |

### Governance Hierarchy

| Table | Fields | Keys / Indexes | Relationships / Notes |
| --- | --- | --- | --- |
| `governance_permissions` | `id:int!`; `permission_code:varchar(20)!`; `permission_name:varchar(100)!`; `description:text?` | PK `id`; unique/indexed `permission_code` | permission catalog |
| `governance_units` | `id:int!`; `parent_unit_id:int?`; `school_id:int!`; `department_id:int?`; `program_id:int?`; `created_by_user_id:int?`; `unit_name:varchar(255)!`; `unit_code:varchar(20)!`; `unit_type:varchar(3)!`; `description:text?`; `created_at:datetime!`; `updated_at:datetime!` | PK `id`; indexes on `parent_unit_id`, `school_id`, `department_id`, `program_id`, `unit_type` | hierarchy root/child units for SSG/SG/ORG |
| `governance_members` | `id:int!`; `governance_unit_id:int!`; `user_id:int!`; `position_title:varchar(100)?`; `assigned_by_user_id:int?`; `assigned_at:datetime!`; `is_active:bool!=true` | PK `id`; unique `(governance_unit_id, user_id)`; indexes on unit/user/assigned_by/is_active | membership records |
| `governance_member_permissions` | `id:int!`; `governance_member_id:int!`; `permission_id:int!`; `granted_by_user_id:int?`; `created_at:datetime!` | PK `id`; unique `(governance_member_id, permission_id)`; indexes on member/permission/granted_by | actual permission grants used by checks |
| `governance_unit_permissions` | `id:int!`; `governance_unit_id:int!`; `permission_id:int!`; `granted_by_user_id:int?`; `created_at:datetime!` | PK `id`; unique `(governance_unit_id, permission_id)`; indexes on unit/permission/granted_by | stored, but appears not to drive runtime auth decisions |
| `governance_announcements` | `id:int!`; `governance_unit_id:int!`; `school_id:int!`; `title:varchar(255)!`; `body:text!`; `status:varchar(9)!`; `created_by_user_id:int?`; `updated_by_user_id:int?`; `created_at:datetime!`; `updated_at:datetime!` | PK `id`; indexes on unit/school/status/created_by/updated_by | governance announcement content |
| `governance_student_notes` | `id:int!`; `governance_unit_id:int!`; `student_profile_id:int!`; `school_id:int!`; `note:text!`; `tags:json?`; `created_by_user_id:int?`; `updated_by_user_id:int?`; `created_at:datetime!`; `updated_at:datetime!` | PK `id`; indexes on unit/student/school/created_by/updated_by | private governance notes on students |

### Dead / Drifted Models Outside Active Metadata

- `Backend/app/models/notification.py`
  - defines `notifications`
  - used by unmounted `notification_center.py`
  - not part of active Alembic env imports
- `Backend/app/models/event_attendance.py`
  - defines `event_attendance`
  - not part of active model exports or active metadata

## C. Component Reference

| Component / Module | Purpose | Key dependencies | Current usage / concern |
| --- | --- | --- | --- |
| `Backend/app/main.py` | FastAPI app bootstrap | routers, config, static files | true backend entry |
| `Backend/app/core/security.py` | auth, JWT, role checks | jose, DB, School/User models | central and high-risk |
| `Backend/app/services/auth_session.py` | login token/session response shaping | security, security_service | good consolidation point |
| `Backend/app/services/security_service.py` | MFA, sessions, login history | platform feature models | strong module |
| `Backend/app/services/event_time_status.py` | attendance/event time calculations | datetime, zoneinfo | reliable core logic |
| `Backend/app/services/event_workflow_status.py` | auto state progression | events/attendance | important scheduled logic |
| `Backend/app/services/student_import_service.py` | import job processing | import repo, email dispatch | important, improved |
| `Backend/app/repositories/import_repository.py` | bulk import persistence | SQLAlchemy | specialized but useful |
| `Backend/app/services/governance_hierarchy_service.py` | governance rules and dashboards | many models/services | most coupled subsystem |
| `Backend/app/routers/attendance.py` | attendance API | security, event services | too large |
| `Backend/app/routers/events.py` | event API | security, event services | too large |
| `Backend/app/routers/users.py` | user CRUD/profile API | security, email, governance | too large |
| `Frontend/src/App.tsx` | route graph | pages, ProtectedRoute | oversized central router |
| `Frontend/src/components/ProtectedRoute.tsx` | auth + governance gate | localStorage, governance hook | hidden coupling |
| `Frontend/src/api/authApi.ts` | login/session client logic | fetch, localStorage | important, messy storage model |
| `Frontend/src/hooks/useGovernanceAccess.ts` | governance access cache | localStorage, API | useful but sticky state |
| `Frontend/src/pages/SchoolImportUsers.tsx` | bulk import UI | schoolSettingsApi | key operational screen |
| `Frontend/src/pages/ManageUsers.tsx` | campus admin user UI | user endpoints | very large file |
| `Frontend/src/pages/Events.tsx` | events management UI | events API | very large file |
| `Frontend/src/pages/StudentEventCheckIn.tsx` | check-in UX | camera/geolocation/event timing | very large and fragile |
| `Frontend/src/pages/NotificationCenter.tsx` | inbox UI | notificationsApi | points to dead backend path |

## D. Library Reference

| Library | Where used | Why used | Fit |
| --- | --- | --- | --- |
| `FastAPI` | backend | HTTP API framework | appropriate |
| `SQLAlchemy` | backend | ORM and query building | appropriate |
| `Alembic` | backend | DB migrations | appropriate |
| `Celery` | backend workers | async/background jobs | appropriate |
| `Redis` | workers | Celery broker/backend | appropriate |
| `python-jose` | backend auth | JWT encode/decode | appropriate |
| `passlib` / `bcrypt` | backend auth | password hashing | appropriate |
| `openpyxl` | backend import/template | Excel file support | appropriate |
| `face-recognition` / `dlib` | backend face features | embeddings/face matching | heavy but necessary for current design |
| `onnxruntime` / `opencv-python-headless` | backend liveness | anti-spoof/liveness | appropriate but operationally heavy |
| `Pillow` | backend/logo validation | raster image verification | appropriate |
| `React` | frontend | SPA UI | appropriate |
| `React Router` | frontend | client routing | appropriate |
| `Vite` | frontend | dev/build tool | appropriate |
| `Bootstrap` | frontend | layout/styling | appropriate |
| `Leaflet` / `react-leaflet` | frontend | map/geofence UI | appropriate |
| `chart.js` + `recharts` | frontend | charting | redundant to keep both long-term |
| `axios` | frontend | HTTP client | mostly unnecessary; fetch is dominant |
| `json-server` / `cors` | frontend mock area | local experiments/mock server | not part of main product |
| `SQLAlchemy-Utils` | backend deps | supposed DB helpers | appears unused |

## E. Explain Like I’m The Maintainer

Mentally model this system as four real subsystems and several misleading leftovers.

The four real subsystems are:

1. school-scoped user/event/attendance management
2. auth/security with MFA, face verification, and session history
3. governance hierarchy for SSG/SG/ORG access and dashboards
4. bulk import with background processing

Everything else should be treated skeptically until verified.

The biggest conceptual trap in this repository is thinking it is cleaner than it is. It is not. A lot of the code reads like it was generated to satisfy a feature request, not designed as part of a long-lived system.

If you keep ownership, use this mental rule:

- trust the active mounted API and active ORM metadata first
- trust the docs second
- trust dead files and old abstractions last

In other words:

- `main.py` tells you what is real
- active models in `Base.metadata` tell you what schema is real
- huge services tell you where the actual rules live
- everything not mounted or not in active metadata is suspect until proven otherwise

## Top 20 Files You Should Read First

1. `Backend/app/main.py` - shows what is actually mounted and therefore actually alive.
2. `Backend/app/core/security.py` - controls auth, role checks, school scope, and request gating.
3. `Backend/app/services/auth_session.py` - explains the real login/session token model.
4. `Backend/app/services/security_service.py` - covers MFA, sessions, login history, and revocation.
5. `Backend/app/services/governance_hierarchy_service.py` - most complex subsystem and biggest coupling point.
6. `Backend/app/routers/governance_hierarchy.py` - public API surface for governance features.
7. `Backend/app/routers/attendance.py` - largest operational router and major business path.
8. `Backend/app/services/event_time_status.py` - authoritative attendance timing logic.
9. `Backend/app/services/event_workflow_status.py` - background lifecycle rules for events.
10. `Backend/app/routers/events.py` - event CRUD and event runtime orchestration.
11. `Backend/app/routers/admin_import.py` - current supported bulk import API.
12. `Backend/app/services/student_import_service.py` - actual high-volume import behavior.
13. `Backend/app/repositories/import_repository.py` - the import performance-critical DB path.
14. `Backend/app/models/user.py` - identity, roles, and student profile shape.
15. `Backend/app/models/governance_hierarchy.py` - governance schema and permission objects.
16. `Frontend/src/App.tsx` - entire frontend route graph and page-level access model.
17. `Frontend/src/components/ProtectedRoute.tsx` - frontend enforcement of auth/governance/password/face state.
18. `Frontend/src/api/authApi.ts` - browser-side auth persistence and logout/session logic.
19. `Frontend/src/pages/StudentEventCheckIn.tsx` - most fragile end-user flow on the frontend.
20. `Frontend/src/pages/SchoolImportUsers.tsx` - the UI for the backend flow that will matter most at scale.

## Final Honest Assessment

This repo is valuable, but it is not clean.

It contains real functionality and some genuinely useful centralized logic, but it also contains dead branches, duplicate systems, stale deployment artifacts, and obvious AI-generated scaffolding. You can take ownership of it, but you should do so by first shrinking the number of things that pretend to be real.

The right ownership move is not to add more features immediately. The right ownership move is to establish a trustworthy core:

- one supported import path
- one supported notification story
- one route prefix convention
- one auth state model on the frontend
- one deployment source of truth
- one explicit list of dead code to delete
