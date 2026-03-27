# Codebase Refactor Plan

Date: 2026-03-25

## 1. Executive Summary

This codebase is workable but has clear architectural drift. The main problems are not the core business flows themselves. The main problems are duplicate subsystems, compatibility layers that were never retired, inconsistent API routing, frontend auth/session sprawl, and stale deployment artifacts mixed into runtime code.

The safest strategy is incremental refactoring around the working flows, not a rewrite.

The current system has five immediate structural risks:

| Risk | Evidence | Impact |
| --- | --- | --- |
| Dead routers and services still live in the tree | `Backend/app/routers/notification_center.py`, `Backend/app/routers/ssg_events_alias.py`, `Backend/app/routers/ssg_notifications_admin.py` are not mounted in `Backend/app/main.py` | Misleading code, false maintenance burden, accidental reactivation risk |
| Duplicate business paths | Bulk import exists in both `Backend/app/routers/admin_import.py` and `Backend/app/routers/school_settings.py` | Bug divergence and duplicated fixes |
| Frontend auth and API coupling is spread across storage and direct fetch calls | `Frontend/src/App.tsx`, `Frontend/src/api/authApi.ts`, `Frontend/src/components/ProtectedRoute.tsx`, many pages using direct `fetch()` | Session bugs, hidden state, hard-to-reason routing failures |
| Startup is coupled to optional face-recognition dependencies | `Backend/app/services/face_recognition.py` imports `face_recognition` at module import time, and `Backend/app/main.py` eagerly mounts face routes | Unrelated backend startup and test failures |
| Deployment config is stale or broken | `docker-compose.yml` points to `./backend` and `./frontend`; `docker-compose.prod.yml` has `restart: unless-` | Broken local/prod bootstrap and false confidence |

The good news is that the working business-critical flows are identifiable and should be preserved:

- auth and password-reset flow
- user creation and campus-admin student creation
- attendance and public attendance
- events and event workflow status sync
- governance and governance hierarchy
- bulk student import through the admin-import path
- email delivery and notification center based on `NotificationLog`

The refactor should keep those flows operational while removing dead paths around them.

## 2. Codebase Cleanup Analysis

### Keep As-Is For Now

These are active, coherent enough, and should be protected while nearby dead code is removed first.

| Area | Paths | Why keep for now |
| --- | --- | --- |
| Active import pipeline | `Backend/app/routers/admin_import.py`, `Backend/app/services/student_import_service.py`, `Backend/app/repositories/import_repository.py`, `Backend/app/models/import_job.py` | This is the live import path used by `Frontend/src/pages/SchoolImportUsers.tsx` and should remain the supported flow |
| Active notification system | `Backend/app/routers/notifications.py`, `Backend/app/services/notification_center_service.py`, `Backend/app/models/platform_features.py` notification models | This is the mounted and used notification path; do not disturb until legacy notification code is removed |
| Active worker package | `Backend/app/workers/` | This is the package used by current Celery commands and beat schedule |
| Active migrations | `Backend/alembic/`, `Backend/alembic.ini` | This is the configured migration location and must remain the only supported migration system |
| Public attendance flow | `Backend/app/routers/public_attendance.py`, `Frontend/src/api/publicAttendanceApi.ts`, `Frontend/src/components/PublicAttendanceKiosk.tsx` | Isolated and already structured better than several other areas |
| Live campus-admin student creation flow | `Backend/app/routers/users.py` student-create route, `Frontend/src/pages/CreateCampusStudent.tsx`, `Frontend/src/api/userApi.ts` | Recently implemented and business-critical |
| Health endpoint and minimal app shell | `Backend/app/routers/health.py`, `Backend/app/main.py` base app wiring | Small and stable enough to preserve while larger route normalization work is staged |

### Refactor Soon

These are active but oversized, duplicated, or structurally unsafe.

| Area | Paths | Why refactor soon |
| --- | --- | --- |
| Backend attendance | `Backend/app/routers/attendance.py` | ~1900 lines, mixed policy/query/response logic, high change risk |
| Backend events | `Backend/app/routers/events.py` | ~1300 lines, mixes CRUD, workflow, status sync, audience rules |
| Backend users | `Backend/app/routers/users.py` | User CRUD, role assignment, password flows, student creation, profile logic all mixed together |
| Backend school settings | `Backend/app/routers/school_settings.py` | Branding, audit logs, and a legacy import pipeline in one file |
| Backend email delivery | `Backend/app/services/email_service.py` | Functionally important but oversized and mixing transport, templating, and delivery policy |
| Governance hierarchy service | `Backend/app/services/governance_hierarchy_service.py` | ~2600 lines; needs domain splitting without changing behavior |
| Frontend app shell | `Frontend/src/App.tsx` | Global fetch monkey patch, route alias sprawl, hard to reason about |
| Frontend auth/session | `Frontend/src/api/authApi.ts`, `Frontend/src/components/ProtectedRoute.tsx` | Multiple token keys, direct storage reads, route guard logic depends on stored JSON shape |
| Frontend API modules | `Frontend/src/api/platformOpsApi.ts`, `Frontend/src/api/governanceHierarchyApi.ts`, `Frontend/src/api/schoolSettingsApi.ts` | Repeated header/error logic and too many endpoints per file |
| Frontend heavy pages | `Frontend/src/pages/Events.tsx`, `Frontend/src/pages/Records.tsx`, `Frontend/src/pages/ManageUsers.tsx`, `Frontend/src/pages/ManageSg.tsx`, `Frontend/src/pages/Reports.tsx` | Oversized stateful screens mixing data access, view logic, and business rules |
| Deployment files | `docker-compose.yml`, `docker-compose.prod.yml` | Case-sensitive path errors and invalid YAML in prod file |

### Quarantine

These look stale or duplicated, but removal should happen through a short quarantine window first so rollback is trivial.

| Area | Paths | Why quarantine first | What could break |
| --- | --- | --- | --- |
| Legacy notification subsystem | `Backend/app/routers/notification_center.py`, `Backend/app/models/notification.py`, `Backend/app/services/notification_service.py`, `Frontend/src/api/notificationsApi.ts`, `Frontend/src/components/NotificationBell.tsx` | Entire path is separate from the active notification center and uses old storage/model assumptions | External clients might still call `/api/notifications-center/*`; database may still contain `notifications` table |
| Experimental tenant-database subsystem | `Backend/app/core/tenant_database.py`, `tenant_database_prefix` config field | Not integrated into active runtime and imports `TenantUserDirectory`, which is not defined in `platform_features.py` | Future multi-tenant experiments, if anyone was depending on local unpublished work |
| Legacy SSG subsystem | `Backend/app/services/ssg_event_service.py`, `Backend/app/routers/ssg_events_alias.py`, `Backend/app/routers/ssg_notifications_admin.py`, `Backend/app/worker/tasks_notifications.py` | Depends on missing `app.models.ssg` and is not mounted or supported | Almost certainly nothing at runtime, but quarantine avoids accidental loss of historical reference |
| Old worker task files | `Backend/app/worker/tasks_attendance.py`, `Backend/app/worker/tasks_notifications.py` | One imports a missing function; one imports a broken service; both are outside the active worker package | Hidden operational scripts might still point to these exact task names |
| Alternate migrations tree | `Backend/migrations/` | Not referenced by `alembic.ini` and appears to be a stale duplicate | Team scripts or docs might still mention it |
| Repo artifact dump set | root `.txt` audits, SQL dumps, generated API dumps, `Databse/` image folder | Likely documentation residue rather than runtime assets | Some files may still be useful reference during cleanup; quarantine avoids premature loss |

### Delete Safely

These have strong evidence of being dead, generated, or broken and can be removed immediately after a fresh branch cut.

| Path | Why it appears safe to delete | Evidence | Break risk | Action |
| --- | --- | --- | --- | --- |
| `Backend/app/routers/ssg_events_alias.py` | Unmounted and imports modules that do not exist | Not included in `Backend/app/main.py`; imports `app.routers.ssg` and `app.schemas.ssg` which are absent | Extremely low | Delete now |
| `Backend/app/routers/ssg_notifications_admin.py` | Unmounted duplicate router depending on broken legacy service | Not included in `Backend/app/main.py`; depends on `app.services.ssg_event_service` | Extremely low | Delete now |
| `Backend/app/services/ssg_event_service.py` | References missing `app.models.ssg` and only feeds dead legacy paths | No `app.models.ssg` exists; only legacy router/task references remain | Extremely low | Delete now |
| `Backend/app/worker/tasks_notifications.py` | Only calls broken SSG service from dead worker package | Sole purpose is legacy reminder task on dead subsystem | Extremely low | Delete now |
| `Frontend/src/components/NotificationBell.tsx` | Not imported anywhere and only uses legacy notification API | No incoming references in `Frontend/src`; legacy backend router is unmounted | None for current app | Delete now |
| `Frontend/src/api/recordsApi.ts` | No callers and route usage is inconsistent with active API modules | No incoming references; isolated old axios wrapper | None for current app | Delete now |
| `Frontend/dist/` | Generated build output | Produced by Vite build, not source | None if rebuild available | Delete now and gitignore |
| `Frontend/node_modules/` | Dependency install output | Recreated by package manager | None if package-lock is kept | Delete now and keep out of git |
| `Frontend/.vercel/` | Tool-generated metadata | Not needed for source control | None | Delete now |
| `Frontend/devserver.err.log` | Generated local log | Not source | None | Delete now |
| `Frontend/devserver.out.log` | Generated local log | Not source | None | Delete now |
| `oauth_refresh_token_flow.log` | Generated operational log | Not source and contains transient OAuth flow output | None | Delete now |
| `Frontend/events-api-mock/` | Standalone mock package with no app references | No frontend source references | Low | Delete now |

### Verify Before Deletion

These are likely removable, but removal should happen only after one verification pass or one release of compatibility logging.

| Path | Why it looks removable | Verification needed |
| --- | --- | --- |
| `Backend/app/routers/notification_center.py` | Unmounted legacy router using deprecated notification table | Check for external clients hitting `/api/notifications-center/*` in logs |
| `Backend/app/models/notification.py` | Legacy notification table model not used by active mounted system | Confirm no active code path imports it after legacy router removal; drop table by migration later |
| `Backend/app/models/event_attendance.py` | No active imports found; active attendance uses `Attendance` in `attendance.py` | Check live DB for `event_attendance` table and confirm nothing queries it |
| `Backend/app/database.py` | Compatibility shim for old imports | Remove only after all `app.database` imports are gone |
| `Backend/app/services/auth_background.py` | Compatibility re-export only | Remove after confirming no imports remain |
| `Backend/app/worker/celery_app.py` and `Backend/app/worker/tasks.py` | Import-path compatibility shims | Keep until all ops docs and task callers use `app.workers.*` |
| `Backend/app/worker/tasks_attendance.py` | Broken and likely dead | Confirm no external worker schedules use `app.worker.tasks.mark_event_absentees` |
| `Backend/migrations/` | Stale duplicate migration tree | Verify no team scripts reference it |
| `Backend/migration_script.py` | Placeholder script with hardcoded DB URL | Confirm no operator still uses it manually |
| `Backend/run_simple_test.py` | Ad-hoc wrapper around pytest | Confirm nobody uses it in local onboarding docs |
| `Backend/face_encodings.pkl` | Looks like local face-model artifact | Confirm not used by manual face tooling |
| `Backend/e2e_import_invalid.xlsx` | Could be a fixture or one-off artifact | Confirm whether tests or docs still expect it |
| `Frontend/src/api/attendanceApi.ts` | No incoming references found | One search pass after route cleanup |
| `Frontend/src/api/upcomingEventsApi.ts` | No incoming references found | One search pass after events page cleanup |
| `Frontend/src/pages/Attendance.tsx` | Not routed and appears to be a thin wrapper | Confirm no lazy import remains |
| `Frontend/src/pages/CreateUsers.tsx` | Not routed and superseded by manage users/create student flows | Confirm no manual route alias still points to it |
| `Frontend/src/components/FaceAttendanceSystem.tsx` | No incoming references found | Confirm not planned for kiosk replacement |
| `Frontend/src/components/HomeContainer.tsx` | No incoming references found | Confirm no pending use in dashboard redesign |
| `Frontend/src/utils/facialScan.ts` | No incoming references found | Confirm no hidden dynamic import |
| `Frontend/src/utils/governanceWorkspaceStore.ts` | No incoming references found | Confirm governance pages do not use it via indirect import |
| `Frontend/src/utils/ssgWorkspaceStore.ts` | No incoming references found | Confirm SSG pages do not use it via indirect import |
| `Frontend/convex/` and `Frontend/.env.local` Convex values | No visible runtime usage | Confirm no future branch depends on Convex experiments |

## 3. Safe Deletion Inventory Table

Delete these first. They reduce noise without touching core flows.

| Priority | Path | Reason | Rollback |
| --- | --- | --- | --- |
| Urgent | `Frontend/node_modules/` | Generated dependency cache committed to repo | Re-run install |
| Urgent | `Frontend/dist/` | Generated build output committed to repo | Re-run build |
| Urgent | `Frontend/.vercel/` | Tool metadata, not source | Recreate on deploy |
| Urgent | `Frontend/devserver.err.log` | Generated log | None needed |
| Urgent | `Frontend/devserver.out.log` | Generated log | None needed |
| Urgent | `oauth_refresh_token_flow.log` | Generated operational log | None needed |
| Urgent | `Backend/app/routers/ssg_events_alias.py` | Broken unmounted alias | Restore from git if needed |
| Urgent | `Backend/app/routers/ssg_notifications_admin.py` | Broken unmounted duplicate | Restore from git if needed |
| Urgent | `Backend/app/services/ssg_event_service.py` | Broken service with missing model imports | Restore from git if needed |
| Urgent | `Backend/app/worker/tasks_notifications.py` | Dead task on broken SSG service | Restore from git if needed |
| Near-term | `Frontend/src/components/NotificationBell.tsx` | Unused UI for dead notification path | Restore from git if needed |
| Near-term | `Frontend/src/api/recordsApi.ts` | Unused API wrapper | Restore from git if needed |
| Near-term | `Frontend/events-api-mock/` | Unused standalone mock app | Restore from git if needed |

## 4. Quarantine-First Candidates

Quarantine means move into a clearly named archive path or branch before deletion. Recommended path: `archive/2026-03-refactor-quarantine/`.

| Candidate | Why quarantine first | Evidence | Delete after |
| --- | --- | --- | --- |
| Legacy notification bundle | Could still have external consumers | Backend router unmounted, frontend bell unused, but route path may still exist historically | 1 release with access-log confirmation |
| Tenant database subsystem | Broken and not integrated, but conceptually strategic if multi-tenant work returns | No active imports beyond config/tests; missing `TenantUserDirectory` model definition | Architecture review sign-off |
| Old worker attendance task | Broken import path but task name may still exist in scheduler scripts | `tasks_attendance.py` imports non-existent `mark_absent_attendance` | Worker schedule audit |
| Alternate migrations dir | Stale duplicate but docs may still mention it | `alembic.ini` points to `alembic`; `Backend/migrations/` has no versions | Docs and scripts cleanup complete |
| Root artifact/document dump | Mostly stale, but useful during this cleanup pass | Many audit and dump files not tied to runtime | After extracting anything still valuable into docs |
| Legacy data models `notification.py` and `event_attendance.py` | Likely removable code, but DB cleanup requires migration discipline | No active code path depends on them; legacy migrations created tables | After schema audit and migration rollout |

## 5. Refactor Roadmap By Phase

### Phase 0: Baseline Safety Net

- Priority: Urgent
- Objective: Create enough protection to refactor without silently breaking working flows.

Tasks:

- Capture current route inventory from `Backend/app/main.py`.
- Add a route smoke-test list for auth, users, events, attendance, governance, import, notifications, face, and health endpoints.
- Add browser-level smoke checklist for login, create student, import preview/import, event attendance, governance unit load, forgot-password.
- Snapshot current deployment env files and docker manifests.
- Create the execution log document and require every deletion/refactor PR to append to it.

Dependencies:

- None

Risks:

- False confidence if tests are too shallow

Exit criteria:

- A repeatable smoke test exists for every business-critical flow.

### Phase 1: Remove Proven Dead Code And Broken Artifacts

- Priority: Urgent
- Objective: Reduce noise and eliminate obviously broken paths without touching supported flows.

Tasks:

- Delete the safe-deletion inventory.
- Quarantine the legacy SSG subsystem, legacy notification bundle, tenant subsystem, and stale migration directory.
- Remove generated frontend artifacts from source control and enforce `.gitignore`.
- Remove unmounted broken routers from backend package exports if present.

Dependencies:

- Phase 0 smoke coverage

Risks:

- Accidental deletion of undocumented external compatibility endpoints

Exit criteria:

- Repo tree no longer contains broken unmounted SSG routers or committed build artifacts.

### Phase 2: Stabilize Runtime Boundaries

- Priority: Urgent
- Objective: Fix the structural issues that cause startup, auth, and deployment instability.

Tasks:

- Fix `docker-compose.yml` path case to `./Backend` and `./Frontend`.
- Fix `docker-compose.prod.yml` invalid `restart: unless-`.
- Isolate face-recognition imports behind lazy loading or feature-gated service initialization so unrelated startup does not require `face_recognition`.
- Keep face routes mounted only if dependencies are available, or fail with explicit feature-disabled responses instead of import crashes.
- Introduce one frontend auth/session store as the only code allowed to read/write auth tokens.
- Stop storing the same token under `authToken`, `token`, and `access_token`; keep one canonical key and a migration read path.
- Remove `window.fetch` monkey patch from `Frontend/src/App.tsx` and replace with an HTTP client wrapper/interceptor.

Dependencies:

- Phase 1 cleanup complete

Risks:

- Auth regressions if token migration is not handled carefully
- Face flows breaking if feature gating is implemented incorrectly

Exit criteria:

- App boots without optional face dependencies.
- Frontend auth reads and writes go through one session module only.
- Deployment manifests work on case-sensitive systems.

### Phase 3: Consolidate Duplicate Business Paths

- Priority: Near-term
- Objective: One supported flow per business capability.

Tasks:

- Officially deprecate `school_settings` user import endpoints and keep `admin_import` as the only supported import pipeline.
- Remove frontend dead notification bell path and keep `NotificationLog`-based notification center only.
- Normalize campus-admin naming and keep `school_it_*` frontend route aliases for one deprecation cycle only.
- Publish a canonical private API prefix strategy under `/api`.
- Add backend compatibility aliases for high-risk old routes where needed, not frontend-only hacks.
- Remove `collapseRepeatedApiPrefix` after API route normalization is complete.

Dependencies:

- Phase 2 auth and startup stabilization

Risks:

- Hidden frontend or external clients still depending on old routes

Exit criteria:

- Every business capability has one documented supported API path.

### Phase 4: Split Oversized Backend Modules By Domain

- Priority: Near-term
- Objective: Move from giant routers/services to bounded contexts without changing behavior.

Tasks:

- Split `users.py` into account management, role assignment, student management, and password reset routes/services.
- Split `events.py` into event CRUD, eligibility/audience, workflow status, and attendance-facing event queries.
- Split `attendance.py` into check-in/out, reporting, overrides, and kiosk/public concerns.
- Split `school_settings.py` into branding/settings and school admin operations.
- Split `email_service.py` into transport, template rendering, and use-case senders.
- Split `governance_hierarchy_service.py` into unit lifecycle, membership, permissions, and announcements/student-notes modules.

Dependencies:

- Phase 3 route and flow consolidation

Risks:

- Behavior drift in deeply intertwined files

Exit criteria:

- No backend router over 500-700 lines without explicit exception.
- Domain services are named by use case, not by catch-all role.

### Phase 5: Split Frontend By Feature And Remove Hidden Rules

- Priority: Near-term
- Objective: Keep backend as source of truth and simplify the frontend into feature-oriented modules.

Tasks:

- Create one `lib/api/client.ts` for auth headers, error mapping, retry rules, and 401/403 behavior.
- Replace page-level direct fetch calls with domain API modules and view hooks.
- Move route guarding into a central auth/governance access layer instead of parsing local storage in components.
- Break large pages into container plus presentational sections.
- Remove frontend copies of backend routing quirks and business rules where possible.

Dependencies:

- Phase 2 session/client foundation

Risks:

- UI regressions from moving request logic

Exit criteria:

- No page component should own raw token logic or direct storage parsing.

### Phase 6: Schema And Compatibility Cleanup

- Priority: Later
- Objective: Remove the final compatibility shims and dead tables after the app has stabilized on the new structure.

Tasks:

- Drop legacy `notifications` and `event_attendance` tables if confirmed unused.
- Remove `Backend/app/database.py` shim after all imports use `app.core.database`.
- Remove `Backend/app/services/auth_background.py` after callers use `auth_task_dispatcher`.
- Remove `Backend/app/worker/` compatibility package once task names and docs are fully migrated.
- Remove old `school_it_*` route aliases after one release and telemetry review.

Dependencies:

- Phases 1 through 5 complete

Risks:

- Late discovery of operational scripts still depending on shims

Exit criteria:

- No compatibility shims remain for deprecated import paths or route names.

## 6. Target Clean Architecture

### Backend

Bounded contexts:

- `auth_security`
- `users_roles`
- `schools_tenancy`
- `events`
- `attendance`
- `governance`
- `imports`
- `notifications`
- `admin_ops`
- `face_verification`

Rules:

- Backend remains source of truth for tenant scoping, role checks, eligibility, and attendance policies.
- Each bounded context owns its router, schemas, service layer, repository/query layer, and tests.
- Compatibility aliases live under an explicit `api/compat` area and have a planned removal date.
- Email, storage, Celery, and external integrations move under infrastructure adapters, not mixed into domain modules.

### Frontend

Feature slices:

- `auth`
- `users`
- `schools`
- `events`
- `attendance`
- `governance`
- `imports`
- `notifications`
- `platform`
- `face`

Rules:

- Frontend does not duplicate backend scoping or role rules.
- One session store owns auth state.
- One HTTP client owns header injection and error handling.
- Pages orchestrate feature hooks and sections; API calls live outside pages.

### Shared Contracts And Schemas

- Use backend OpenAPI as the schema source of truth.
- Generate TypeScript contracts and, if acceptable, typed client stubs for stable endpoints.
- Do not manually re-declare payload shapes in multiple frontend API files unless the backend contract cannot express them.

### Async Jobs And Workers

- Keep one active worker package: `app.workers`.
- Organize tasks by domain: `imports`, `auth`, `events`, `notifications`.
- Task registration should support legacy task names only where there is a proven operator dependency.
- Scheduled jobs should be declared in one place with clear ownership and documentation.

### Infrastructure And Deployment

- Keep one authoritative local compose file and one authoritative production deployment manifest.
- Put cloud-specific config under `infra/railway/` or equivalent.
- Separate local development services from production assumptions.
- Eliminate broken or stale deployment files rather than leaving them half-working.

### Testing And CI

- Backend:
  - `tests/unit`
  - `tests/integration`
  - `tests/api`
- Frontend:
  - `src/features/*/*.test.tsx`
  - route smoke tests for auth and protected flows
- CI:
  - backend lint/static checks
  - backend targeted smoke tests
  - frontend typecheck/build
  - schema contract generation check
  - docker config validation

## 7. Recommended Folder Structure

### Backend

```text
Backend/
  app/
    api/
      routes/
        auth.py
        users.py
        schools.py
        events.py
        attendance.py
        governance.py
        imports.py
        notifications.py
        face.py
      compat/
        legacy_school_it_routes.py
        legacy_notification_center.py
    domain/
      auth_security/
        models.py
        schemas.py
        service.py
        repository.py
      users_roles/
      schools_tenancy/
      events/
      attendance/
      governance/
      imports/
      notifications/
      face_verification/
    infrastructure/
      db/
        session.py
        base.py
      email/
        transport.py
        templates.py
        service.py
      tasks/
        celery_app.py
        imports.py
        auth.py
        events.py
        notifications.py
      settings.py
    main.py
  alembic/
  docs/
  tests/
```

### Frontend

```text
Frontend/
  src/
    app/
      router.tsx
      providers.tsx
    lib/
      api/
        client.ts
        errors.ts
      auth/
        sessionStore.ts
      routing/
        redirects.ts
    features/
      auth/
      users/
      schools/
      events/
      attendance/
      governance/
      imports/
      notifications/
      face/
    pages/
    components/
    styles/
```

## 8. Migration Strategy

Recommended order:

1. Freeze and baseline.
2. Delete generated artifacts and broken dead files.
3. Quarantine legacy notification, tenant, old worker, and stale migration paths.
4. Fix deployment manifests and optional dependency startup behavior.
5. Centralize frontend session and HTTP behavior.
6. Consolidate to one supported import path and one supported notification path.
7. Normalize backend routes under canonical prefixes and keep compatibility aliases temporarily.
8. Split oversized backend files by bounded context.
9. Split oversized frontend pages by feature and remove direct fetch/storage coupling.
10. Remove remaining compatibility shims and drop dead tables by migration.

Execution rules:

- Never delete a compatibility endpoint and a frontend caller in the same change unless smoke coverage already exists.
- Do not change route names and auth/session storage in the same PR.
- Do not change email delivery internals during the auth/session refactor.
- Drop dead tables only after code removal has been deployed and observed cleanly.
- Every phase must be reversible by branch or release rollback.

## 9. Top 20 Highest-Priority Cleanup Actions

1. Delete committed generated frontend artifacts: `Frontend/node_modules/`, `Frontend/dist/`, `.vercel/`, local logs.
2. Delete broken unmounted SSG routers and the broken `ssg_event_service.py`.
3. Quarantine the legacy notification subsystem and stop treating it as supported.
4. Fix `docker-compose.yml` path case to match `Backend` and `Frontend`.
5. Fix `docker-compose.prod.yml` invalid `restart: unless-`.
6. Remove eager import coupling to `face_recognition` so unrelated startup no longer fails.
7. Introduce a single frontend auth/session store and deprecate multiple token keys.
8. Replace the global `window.fetch` monkey patch in `Frontend/src/App.tsx` with a central API client.
9. Consolidate frontend API error/header logic into one shared client.
10. Officially deprecate `Backend/app/routers/school_settings.py` import endpoints in favor of `admin_import.py`.
11. Remove `Frontend/src/components/NotificationBell.tsx` and `Frontend/src/api/notificationsApi.ts` after quarantine confirmation.
12. Split `Backend/app/routers/users.py` by user lifecycle use case.
13. Split `Backend/app/routers/attendance.py` into smaller route modules and service helpers.
14. Split `Backend/app/routers/events.py` and move workflow/status logic into dedicated service modules.
15. Split `Backend/app/services/email_service.py` into transport, template, and sender modules.
16. Split `Backend/app/services/governance_hierarchy_service.py` by unit lifecycle, membership, permissions, and notes/announcements.
17. Remove direct `localStorage` reads from `ProtectedRoute.tsx` and pages.
18. Normalize campus-admin naming and retire `school_it_*` route aliases after one release.
19. Remove `Backend/app/database.py` and `Backend/app/services/auth_background.py` after import cleanup.
20. Drop legacy `notifications` and `event_attendance` tables only after code removal and access-log verification.

## 10. Risks And Rollback Notes

### Highest Risks

| Risk | Why it matters | Mitigation | Rollback |
| --- | --- | --- | --- |
| Auth/session regression | Frontend currently reads auth state from multiple keys and JSON blobs | Introduce read-compatibility before write-normalization | Revert session-store PR only |
| Hidden external route dependencies | Some dead-looking routes may still be called outside the current frontend | Log and monitor old route hits before final deletion | Restore compatibility router from quarantine |
| Face feature startup failure | Face module import currently affects whole backend startup | Feature-gate and lazy-load dependencies | Re-enable eager path if gated implementation misbehaves |
| Bulk import regression | Two import systems currently coexist | Preserve `admin_import` as source of truth and do not refactor it in same PR as auth/session | Revert import consolidation PR only |
| Worker task name breakage | Legacy task names may still be scheduled somewhere | Keep legacy task names registered inside active `app.workers.tasks` until ops confirmation | Restore shim registration |
| Schema cleanup too early | Old tables may still exist in production even if code is dead | Delay drops until after code removal and telemetry review | Roll back migration or restore code path temporarily |

### Rollback Rules

- Use branch-based rollback for deletions and quarantines.
- Use release-based rollback for auth/session, route normalization, and face startup changes.
- Do not bundle schema drops with application refactors in the same release.
- Preserve data migrations as separate reversible units.

## 11. Refactor Execution Log Requirement

Every cleanup PR should also update `PROJECT_REFACTOR_EXECUTION_LOG.md` with:

- date
- phase
- files deleted
- files moved to quarantine
- files refactored
- routes added or deprecated
- migrations added
- user-visible behavior changes
- rollback notes
