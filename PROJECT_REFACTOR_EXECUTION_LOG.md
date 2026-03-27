# Refactor Execution Log

Use this file to track what was changed, what was deleted, and how to roll back each cleanup step.

## Entry Template

### Date

YYYY-MM-DD

### Phase

Phase name or milestone

### Summary

Short description of the cleanup or refactor completed.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |
| `path/to/file` | Why it was deleted | How to restore |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |
| `path/to/file` | `archive/...` | Why it was quarantined | YYYY-MM-DD |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `path/to/file` | What changed | Low/Medium/High |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/example` | added/deprecated/removed | Alias, migration, or removal date |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |
| `revision_id` | What schema changed | downgrade path |

### Behavior Changes

- User-visible changes only.

### Validation Performed

- Tests run
- Manual flows checked
- Deployment checks completed

### Rollback Notes

- Exact command, branch, or release to restore previous behavior.

## Entries

### Date

2026-03-25

### Phase

Cleanup follow-up: private route alias removal

### Summary

Removed the deprecated unprefixed private backend routes, normalized the remaining frontend API callers to `/api/*`, and updated backend tests/docs to treat `/api/*` as the only supported private route family.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/app/main.py` | Removed hidden unprefixed private router mounts and kept only canonical `/api` mounts | Medium |
| `Backend/app/core/security.py` | Updated face-onboarding security exemptions to the canonical `/api/auth/security/face-*` paths | Medium |
| `Backend/app/tests/test_api.py` | Migrated remaining private-route assertions to `/api/*` and added regression checks that legacy aliases now return `404` | Low |
| `Backend/app/tests/test_governance_hierarchy_api.py` | Migrated governance attendance, event, department, and program calls to `/api/*` | Medium |
| `Frontend/src/api/academicApi.ts` | Migrated academic API calls to canonical `/api/departments/*` and `/api/programs/*` | Low |
| `Frontend/src/api/attendanceApi.ts` | Migrated attendance and event attendance calls to canonical `/api/events/*` and `/api/attendance/*` | Medium |
| `Frontend/src/api/faceScanApi.ts` | Migrated face registration and verification calls to canonical `/api/face/*` | Low |
| `Frontend/src/api/userApi.ts` | Migrated user/profile/student CRUD calls to canonical `/api/users/*` | Medium |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/users/*` | removed | Use `/api/users/*` |
| `/events/*` | removed | Use `/api/events/*` |
| `/attendance/*` | removed | Use `/api/attendance/*` |
| `/programs/*` | removed | Use `/api/programs/*` |
| `/departments/*` | removed | Use `/api/departments/*` |
| `/auth/security/*` | removed | Use `/api/auth/security/*` |
| `/face/*` | removed | Use `/api/face/*` |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- Private backend traffic must now use `/api/*` only.
- Old unprefixed private route aliases now return `404`.

### Validation Performed

- `python -m pytest -q app/tests/test_api.py app/tests/test_governance_hierarchy_api.py`
- `npm run build`

### Rollback Notes

- Re-add the unprefixed private mounts in `Backend/app/main.py` only if a real external dependency still exists and cannot be migrated immediately.

### Date

2026-03-25

### Phase

Phase 6 schema and compatibility cleanup

### Summary

Removed the last backend import-path and worker-name compatibility shims, added the final legacy event-attendance table cleanup migration, and removed the old frontend `/school_it_*` route aliases.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |
| `Backend/app/database.py` | Deprecated compatibility wrapper after import migration to `app.core.database` | Restore from version control if an out-of-tree script still imports `app.database` |
| `Backend/app/services/auth_background.py` | Deprecated compatibility re-export after auth callers moved to `auth_task_dispatcher` | Restore from version control if an out-of-tree import still depends on the old module |
| `Backend/app/worker/__init__.py` | Deprecated worker package wrapper | Restore from version control if an out-of-tree import still depends on `app.worker` |
| `Backend/app/worker/celery_app.py` | Deprecated worker app wrapper | Restore from version control if an out-of-tree command still imports `app.worker.celery_app` |
| `Backend/app/worker/tasks.py` | Deprecated task wrapper after canonical task names were adopted | Restore from version control if an out-of-tree import still depends on `app.worker.tasks` |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/app/workers/tasks.py` | Removed legacy `app.worker.tasks.*` alias registrations and kept only canonical task names | Medium |
| `Backend/app/tests/test_auth_task_dispatcher.py` | Added regression coverage that Phase 6 leaves only canonical worker task names registered | Low |
| `Backend/alembic/versions/a6c4e2f1b9d7_drop_legacy_event_attendance_tables.py` | Added idempotent cleanup migration for the final legacy event-attendance tables | Medium |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added the Phase 6 backend cleanup entry | Low |
| `Backend/docs/BACKEND_DATABASE_CLEANUP_GUIDE.md` | Documented the remaining legacy event-attendance table removal | Low |
| `Backend/docs/BACKEND_PROJECT_STRUCTURE_GUIDE.md` | Removed the old worker/database compatibility-path guidance | Low |
| `Backend/docs/BACKEND_AUTH_LOGIN_PERFORMANCE_GUIDE.md` | Removed the old worker compatibility-wrapper note and documented canonical task naming only | Low |
| `Frontend/src/App.tsx` | Removed legacy `/school_it_*` compatibility redirects | Low |
| `Frontend/src/utils/redirects.ts` | Removed legacy `/school_it_*` redirect allowlist entries | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/school_it_*` | removed | Use the canonical `/campus_admin_*` routes only |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |
| `a6c4e2f1b9d7` | Drop legacy `event_attendance` and `ssg_event_attendance` tables if they still exist | Downgrade unsupported; restore from database backup if needed |

### Behavior Changes

- Backend imports must now use `app.core.database`, `app.services.auth_task_dispatcher`, and `app.workers.*` only.
- Celery no longer registers legacy `app.worker.tasks.*` names.
- Old frontend `/school_it_*` bookmarks and redirect targets no longer resolve; callers must use `/campus_admin_*`.

### Validation Performed

- `python -m pytest -q app/tests/test_auth_task_dispatcher.py app/tests/test_admin_import_preview_flow.py`
- `npm run build`

### Rollback Notes

- Restore the deleted compatibility files and the legacy task aliases from version control if an external script or queued integration still depends on the old paths.
- Re-add the `/school_it_*` redirects only if telemetry or support traffic shows live user dependence on the removed frontend aliases.

### Date

2026-03-25

### Phase

Phase 5 frontend access-layer start

### Summary

Started Phase 5 by centralizing frontend stored-user parsing into one auth helper, removing direct `localStorage("user")` reads from the route/access layer and admin/security pages, and migrating `platformOpsApi` onto the shared API client helpers.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Frontend/src/lib/api/client.ts` | Added shared authenticated request helpers with centralized JSON and void response error handling | Medium |
| `Frontend/src/lib/auth/storedUser.ts` | Added the canonical frontend stored-user/session parser and role/school helpers | Medium |
| `Frontend/src/api/platformOpsApi.ts` | Migrated security, audit-log, notification, subscription, and data-governance API calls onto the shared client helpers | Medium |
| `Frontend/src/components/ProtectedRoute.tsx` | Replaced raw user JSON parsing with the shared stored-user helper | Medium |
| `Frontend/src/hooks/useGovernanceAccess.ts` | Replaced direct user-id storage parsing with the shared stored-user helper | Low |
| `Frontend/src/hooks/useGovernanceWorkspace.ts` | Replaced direct stored-session parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/SecurityCenter.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/AuditLogs.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/NotificationCenter.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/DataGovernance.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/SchoolPasswordResetRequests.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/SubscriptionCenter.tsx` | Replaced direct stored-user parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/ManageUsers.tsx` | Replaced direct stored-role parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/StudentFaceEnrollment.tsx` | Replaced direct stored-user parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/StudentEventCheckIn.tsx` | Replaced direct stored-user parsing with the shared stored-user helper | Low |
| `Frontend/src/pages/FacialVerification.tsx` | Replaced direct stored-user parsing with the shared stored-user helper | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- No frontend route paths changed in this slice.
- The affected pages and hooks now derive current-user role, school, and display-name information from one normalized helper instead of hand-parsing `localStorage("user")`.
- `platformOpsApi` now uses the shared client-side auth/error path instead of module-local `fetch` wrappers.

### Validation Performed

- searched the frontend tree and confirmed no remaining direct `localStorage.getItem("user")` calls
- `npm run build`

### Rollback Notes

- Remove `Frontend/src/lib/auth/storedUser.ts` and restore the previous per-page local storage parsing if the normalized session helper proves incompatible with older stored payloads.
- Revert the `platformOpsApi` migration if any platform/security API call shows a client-side regression.

### Date

2026-03-25

### Phase

Phase 5 frontend access-layer completion

### Summary

Completed Phase 5 by removing the remaining page-owned auth/token/storage logic, routing the last high-traffic pages through feature API modules, and centralizing academic, user, attendance, and face-scan requests behind the shared frontend client.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Frontend/src/api/academicApi.ts` | Added shared department/program lookup and CRUD helpers for academic-management and governance pages | Medium |
| `Frontend/src/api/attendanceApi.ts` | Expanded attendance/report/manual-attendance calls onto the shared authenticated client | Medium |
| `Frontend/src/api/faceScanApi.ts` | Added shared face registration, verification, upload, and attendance-scan helpers | Medium |
| `Frontend/src/api/userApi.ts` | Added shared user/profile/student-profile CRUD helpers and photo upload support | Medium |
| `Frontend/src/pages/AcademicManagement.tsx` | Removed local auth fetch wrapper and moved department/program CRUD onto `academicApi` | Medium |
| `Frontend/src/pages/ChangePassword.tsx` | Replaced raw stored-user parsing with the canonical stored-user helper | Low |
| `Frontend/src/pages/CreateUsers.tsx` | Removed page-level auth fetch wrapper and moved create-user/student-profile flows onto shared APIs | Medium |
| `Frontend/src/pages/FaceScan.tsx` | Removed page-level auth fetch wrapper and moved face flows onto `faceScanApi` | Medium |
| `Frontend/src/pages/GovernanceHierarchyManagement.tsx` | Replaced page-level academic lookup fetches with `academicApi` | Low |
| `Frontend/src/pages/ManageOrg.tsx` | Replaced page-level academic lookup fetches with `academicApi` | Low |
| `Frontend/src/pages/ManageSg.tsx` | Replaced page-level academic lookup fetches with `academicApi` | Low |
| `Frontend/src/pages/ManageUsers.tsx` | Removed page-level auth fetch wrapper and moved user CRUD/photo upload onto shared APIs | Medium |
| `Frontend/src/pages/ManualAttendance.tsx` | Removed page-level auth fetch wrapper and moved manual attendance actions onto domain APIs | Medium |
| `Frontend/src/pages/Profile.tsx` | Removed page-level auth fetch wrapper and moved current-user/profile updates onto shared APIs | Medium |
| `Frontend/src/pages/Records.tsx` | Removed page-level tokenized fetch logic and moved attendance report loading onto `attendanceApi` | Medium |
| `Frontend/src/pages/Reports.tsx` | Replaced raw stored-user parsing and page-local report fetches with shared helpers | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- No frontend route paths changed in this slice.
- No page component now owns raw token logic or direct stored-user parsing; the Phase 5 exit criterion is met.
- Academic management, user-management, profile, records, reports, manual attendance, and face-scan flows now share the same client-side auth/error path through feature API modules.
- Governance setup pages no longer make page-local authenticated academic lookup requests.

### Validation Performed

- searched `Frontend/src/pages` and confirmed `getAuthToken`, `fetchWithAuth`, `buildApiUrl`, `apiFetch(...)`, `buildAuthHeaders`, raw stored-user parsing, and `localStorage.getItem("user")` no longer appear there
- `npm run build`

### Rollback Notes

- Revert the new frontend API modules and the listed page migrations together if any page-level request regression appears, because these pages now depend on the shared request/client path.
- If a specific page regresses, you can temporarily restore only that page's previous local request wrapper while keeping the normalized stored-user helper in place.

### Date

2026-03-25

### Phase

Phase 4 backend module split

### Summary

Split the largest active backend routers and services into domain packages, preserved the old public import paths at package roots, and fixed student-account onboarding so it no longer depends on a pre-seeded `student` role row.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |
| `Backend/app/routers/users.py` | Replaced by `Backend/app/routers/users/` package | Restore from version control |
| `Backend/app/routers/events.py` | Replaced by `Backend/app/routers/events/` package | Restore from version control |
| `Backend/app/routers/attendance.py` | Replaced by `Backend/app/routers/attendance/` package | Restore from version control |
| `Backend/app/services/email_service.py` | Replaced by `Backend/app/services/email_service/` package | Restore from version control |
| `Backend/app/services/governance_hierarchy_service.py` | Replaced by `Backend/app/services/governance_hierarchy_service/` package | Restore from version control |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/app/routers/users/__init__.py` | Added package root compatibility exports and legacy root aliases for the split user router | Medium |
| `Backend/app/routers/users/accounts.py` | Moved account-management routes out of the old monolith | Medium |
| `Backend/app/routers/users/students.py` | Moved student routes out of the old monolith and made `student` role creation resilient in fresh databases | Medium |
| `Backend/app/routers/users/roles.py` | Moved role-assignment routes out of the old monolith | Low |
| `Backend/app/routers/users/passwords.py` | Moved password-reset routes out of the old monolith | Low |
| `Backend/app/routers/users/shared.py` | Centralized shared user-router helpers and compatibility utilities | Medium |
| `Backend/app/routers/events/__init__.py` | Added package root router for split event domains | Medium |
| `Backend/app/routers/events/crud.py` | Moved event create, update, and delete handlers into a domain module | Medium |
| `Backend/app/routers/events/queries.py` | Moved event listing and detail queries into a domain module | Medium |
| `Backend/app/routers/events/workflow.py` | Moved workflow and time-status event handlers into a domain module | Medium |
| `Backend/app/routers/events/attendance_queries.py` | Moved attendance-facing event queries into a domain module | Low |
| `Backend/app/routers/events/shared.py` | Centralized shared event-router helpers | Medium |
| `Backend/app/routers/attendance/__init__.py` | Added package root router for split attendance domains | Medium |
| `Backend/app/routers/attendance/check_in_out.py` | Moved attendance write paths into a domain module | Medium |
| `Backend/app/routers/attendance/reports.py` | Moved reporting endpoints into a domain module | Medium |
| `Backend/app/routers/attendance/overrides.py` | Moved manual override and excusal endpoints into a domain module | Medium |
| `Backend/app/routers/attendance/records.py` | Moved record and read endpoints into a domain module | Low |
| `Backend/app/routers/attendance/shared.py` | Centralized shared attendance-router helpers | Medium |
| `Backend/app/services/email_service/__init__.py` | Added package root compatibility exports for the split email service | Medium |
| `Backend/app/services/email_service/config.py` | Isolated delivery-config helpers | Low |
| `Backend/app/services/email_service/transport.py` | Isolated SMTP and Gmail API transport code while preserving monkeypatch-sensitive entry points | Medium |
| `Backend/app/services/email_service/rendering.py` | Isolated email template rendering helpers | Low |
| `Backend/app/services/email_service/use_cases.py` | Isolated welcome, reset, and MFA senders | Low |
| `Backend/app/services/governance_hierarchy_service/__init__.py` | Added package root compatibility exports for the split governance service | Medium |
| `Backend/app/services/governance_hierarchy_service/permissions.py` | Added governance permissions domain module | Low |
| `Backend/app/services/governance_hierarchy_service/unit_lifecycle.py` | Added governance unit-lifecycle domain module | Low |
| `Backend/app/services/governance_hierarchy_service/membership.py` | Added governance membership domain module | Low |
| `Backend/app/services/governance_hierarchy_service/engagement.py` | Added governance announcement and student-engagement domain module | Low |
| `Backend/app/services/governance_hierarchy_service/shared.py` | Preserved the existing implementation as a temporary internal compatibility layer | Medium |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added the Phase 4 backend split entry | Low |
| `Backend/docs/BACKEND_PROJECT_STRUCTURE_GUIDE.md` | Documented the new package layout and explicit remaining exceptions | Low |
| `Backend/docs/BACKEND_GOVERNANCE_HIERARCHY_GUIDE.md` | Updated governance service placement to the new package layout | Low |
| `Backend/docs/BACKEND_GOOGLE_EMAIL_DELIVERY_GUIDE.md` | Updated email service placement to the new package layout | Low |
| `Backend/docs/BACKEND_AUTH_LOGIN_PERFORMANCE_GUIDE.md` | Updated email service path references | Low |
| `Backend/docs/BACKEND_ATTENDANCE_STATUS_GUIDE.md` | Updated attendance router path references | Low |
| `Backend/docs/BACKEND_EVENT_AUTO_STATUS_GUIDE.md` | Updated event and attendance router path references | Low |
| `Backend/docs/BACKEND_EVENT_TIME_STATUS_GUIDE.md` | Updated event workflow path references | Low |
| `Backend/docs/BACKEND_FACE_GEO_MERGE_GUIDE.md` | Updated event router path references | Low |
| `PROJECT_REFACTOR_EXECUTION_LOG.md` | Added the Phase 4 execution entry | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- No public route paths or response schemas changed in this phase.
- `POST /users/students/` now creates the canonical `student` role row on demand if it has not been seeded yet.
- Public imports such as `app.routers.users` and `app.services.email_service` now resolve to package roots instead of single files, but callers keep the same import paths.

### Validation Performed

- `python -m pytest -q app/tests/test_api.py`
- `python -m pytest -q app/tests/test_email_service.py app/tests/test_governance_hierarchy_api.py app/tests/test_auth_task_dispatcher.py`
- `python -m pytest -q app/tests/test_api.py app/tests/test_email_service.py app/tests/test_governance_hierarchy_api.py app/tests/test_auth_task_dispatcher.py`
- checked current module sizes after the split and documented explicit remaining exceptions:
  - `Backend/app/routers/admin_import.py`
  - `Backend/app/services/governance_hierarchy_service/shared.py`

### Rollback Notes

- Restore the deleted monolith files from version control and remove the replacement package directories if the package-root compatibility approach proves problematic.
- If the student onboarding fallback is not desired, revert the `student` role auto-create logic in `Backend/app/routers/users/students.py`.

### Date

2026-03-25

### Phase

Planning baseline

### Summary

Created the codebase refactor plan and the execution log template to track future cleanup work.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `PROJECT_REFACTOR_PLAN.md` | Added implementation-ready cleanup and refactor plan | Low |
| `PROJECT_REFACTOR_EXECUTION_LOG.md` | Added execution log template and baseline entry | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- No runtime behavior changes. Documentation only.

### Validation Performed

- Repository structure review
- Router mount audit
- Frontend usage scan
- Deployment file review

### Rollback Notes

- Revert the documentation commit or restore these files from version control.

### Date

2026-03-25

### Phase

Phase 1 cleanup

### Summary

Archived legacy notification-center and tenant-database modules, removed broken dead SSG files from the active tree, and deleted one unused frontend API wrapper.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |
| `Backend/app/routers/ssg_events_alias.py` | Broken unmounted alias router | Restore from version control |
| `Backend/app/routers/ssg_notifications_admin.py` | Broken unmounted duplicate router | Restore from version control |
| `Backend/app/services/ssg_event_service.py` | Broken service importing missing models | Restore from version control |
| `Backend/app/worker/tasks_notifications.py` | Dead legacy task for broken SSG service | Restore from version control |
| `Frontend/src/api/recordsApi.ts` | Unused frontend API wrapper with no callers | Restore from version control |
| `oauth_refresh_token_flow.log` | Transient operational log | Restore only if an old log copy is needed |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |
| `Backend/app/core/tenant_database.py` | `archive/2026-03-refactor-quarantine/Backend/app/core/tenant_database.py` | Experimental inactive subsystem | 2026-04-25 |
| `Backend/app/models/notification.py` | `archive/2026-03-refactor-quarantine/Backend/app/models/notification.py` | Legacy notification table model | 2026-04-25 |
| `Backend/app/models/event_attendance.py` | `archive/2026-03-refactor-quarantine/Backend/app/models/event_attendance.py` | Inactive legacy attendance model | 2026-04-25 |
| `Backend/app/routers/notification_center.py` | `archive/2026-03-refactor-quarantine/Backend/app/routers/notification_center.py` | Unmounted legacy router | 2026-04-25 |
| `Backend/app/schemas/notification_center.py` | `archive/2026-03-refactor-quarantine/Backend/app/schemas/notification_center.py` | Schema used only by legacy router | 2026-04-25 |
| `Backend/app/services/notification_service.py` | `archive/2026-03-refactor-quarantine/Backend/app/services/notification_service.py` | Legacy notification helper | 2026-04-25 |
| `Backend/app/worker/tasks_attendance.py` | `archive/2026-03-refactor-quarantine/Backend/app/worker/tasks_attendance.py` | Broken legacy worker task | 2026-04-25 |
| `Frontend/src/api/notificationsApi.ts` | `archive/2026-03-refactor-quarantine/Frontend/src/api/notificationsApi.ts` | Frontend wrapper for quarantined legacy notification API | 2026-04-25 |
| `Frontend/src/components/NotificationBell.tsx` | `archive/2026-03-refactor-quarantine/Frontend/src/components/NotificationBell.tsx` | Unused frontend component for quarantined legacy notification API | 2026-04-25 |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added Phase 1 cleanup entry | Low |
| `Backend/docs/BACKEND_PROJECT_STRUCTURE_GUIDE.md` | Documented quarantined modules and removed active runtime paths | Low |
| `PROJECT_REFACTOR_EXECUTION_LOG.md` | Added Phase 1 cleanup entry | Low |
| `archive/2026-03-refactor-quarantine/README.md` | Added quarantine archive rules and inventory summary | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/api/notifications-center/*` | quarantined backend implementation | Verify no external consumers, then delete archive later |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- No supported mounted backend route was intentionally changed in this step.
- Legacy notification-center and SSG code is no longer present in the active runtime tree.

### Validation Performed

- Searched for stale imports after deletion and quarantine
- Confirmed removed files no longer exist in active paths
- Confirmed quarantine archive exists

### Rollback Notes

- Restore deleted files from version control.
- Restore quarantined files by moving them back out of `archive/2026-03-refactor-quarantine/`.

### Date

2026-03-25

### Phase

Phase 2 runtime hardening

### Summary

Centralized frontend auth-token storage and fetch interception, made face-recognition dependency loading lazy on the backend, and fixed stale Docker Compose configuration.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/app/services/face_recognition.py` | Lazy-loaded optional face runtime and converted import-time failure into explicit request-time `503` | Medium |
| `Backend/app/routers/security_center.py` | Updated face status readiness reporting for missing runtime dependencies | Low |
| `docker-compose.yml` | Fixed build and volume path casing to match `Backend/` and `Frontend/` | Low |
| `docker-compose.prod.yml` | Fixed invalid Redis restart policy | Low |
| `Frontend/src/lib/auth/sessionStore.ts` | Added canonical frontend auth-token storage helper | Medium |
| `Frontend/src/lib/api/client.ts` | Added shared API client/interceptor and auth-side response handling | Medium |
| `Frontend/src/App.tsx` | Replaced inline fetch interception logic with shared client interceptor install | Low |
| `Frontend/src/api/authApi.ts` | Stopped triple-writing token keys and moved onto shared session/client helpers | Medium |
| `Frontend/src/api/passwordResetApi.ts` | Moved onto shared auth header and API helper path | Low |
| `Frontend/src/api/userApi.ts` | Moved onto shared auth header and API helper path | Low |
| `Frontend/src/api/schoolSettingsApi.ts` | Moved auth-state clearing and token reads onto shared helpers | Low |
| `Frontend/src/api/platformOpsApi.ts` | Moved auth header building onto shared helper | Low |
| `Frontend/src/api/governanceHierarchyApi.ts` | Moved auth header building onto shared helper | Low |
| `Frontend/src/api/eventsApi.ts` | Moved auth header building onto shared helper | Low |
| `Frontend/src/api/facialVerificationApi.ts` | Moved token resolution and auth header building onto shared helper | Low |
| `Frontend/src/api/studentFaceEnrollmentApi.ts` | Moved auth header building onto shared helper | Low |
| `Frontend/src/api/studentEventCheckInApi.ts` | Moved auth header building onto shared helper | Low |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added Phase 2 hardening entry | Low |
| `Backend/docs/BACKEND_PRODUCTION_DEPLOYMENT_GUIDE.md` | Added startup and compose validation notes | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/face/*` | runtime behavior hardened | Existing route shapes preserved |
| `/auth/security/face-status` | readiness reporting hardened | Existing route shape preserved |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- Missing `face_recognition` no longer prevents backend startup.
- Face endpoints now fail explicitly with `503` when the runtime dependency is absent.
- Frontend now writes the auth token to one canonical key and migrates legacy token keys on login.

### Validation Performed

- `python -m compileall Backend/app`
- `npm run build`
- `docker compose -f docker-compose.yml config -q`
- `docker compose -f docker-compose.prod.yml config -q`

### Rollback Notes

- Revert the Phase 2 hardening commit.
- Restore the old inline fetch handler in `Frontend/src/App.tsx` if the shared client causes regressions.
- Restore the previous eager import behavior in `Backend/app/services/face_recognition.py` only if a dependency detection bug is found.

### Date

2026-03-25

### Phase

Migration cleanup and Phase 3 import consolidation

### Summary

Moved the remaining active frontend pages and route guard off direct multi-key token reads, and retired the duplicate legacy school-settings import implementation so the admin-import pipeline is the only supported bulk-import path.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Frontend/src/pages/ChangePassword.tsx` | Switched password-change onboarding flow to shared auth/session storage helpers | Low |
| `Frontend/src/pages/GovernanceHierarchyManagement.tsx` | Removed direct token reads and moved lookup requests onto shared auth headers and API fetch | Low |
| `Frontend/src/pages/ManageOrg.tsx` | Removed direct token reads and moved lookup requests onto shared auth headers and API fetch | Low |
| `Frontend/src/pages/ManageSg.tsx` | Removed direct token reads and moved lookup requests onto shared auth headers and API fetch | Low |
| `Frontend/src/pages/ManualAttendance.tsx` | Replaced page-local token/session clearing logic with shared auth session and API error handling | Medium |
| `Frontend/src/pages/Reports.tsx` | Removed direct token reads from report fetch path and shared user/session access | Low |
| `Frontend/src/components/ProtectedRoute.tsx` | Replaced direct `localStorage` user reads with the shared session store | Medium |
| `Backend/app/routers/school_settings.py` | Removed duplicate legacy import implementation and replaced it with explicit deprecated `410 Gone` routes | Medium |
| `Backend/app/tests/test_api.py` | Added regression tests for deprecated school-settings import routes | Low |
| `Backend/docs/BACKEND_BULK_IMPORT_GUIDE.md` | Documented the supported admin-import path and deprecated legacy routes | Low |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added Phase 3 import-consolidation entry | Low |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/school-settings/me/users/import-template` | deprecated | Returns `410 Gone`; use `/api/admin/import-students/template` |
| `/school-settings/me/users/import` | deprecated | Returns `410 Gone`; use `/api/admin/import-students/preview` then `/api/admin/import-students` |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- Active frontend auth flows no longer rely on page-level `authToken/token/access_token` fallback logic in the patched pages.
- `ProtectedRoute` now reads the canonical session store instead of raw `localStorage`.
- The duplicate school-settings import flow is no longer executable; callers now receive an explicit replacement message.

### Validation Performed

- `python -m pytest -q app/tests/test_api.py -k legacy_school_settings_import`
- `npm run build`

### Rollback Notes

- Revert the frontend session-migration patch if any protected-page auth regression is observed.
- Restore the pre-deprecation `school_settings.py` import handlers only if a real external client still depends on them.

### Date

2026-03-25

### Phase

Phase 3 route normalization

### Summary

Made `/api/*` the canonical private backend route family for active frontend flows, kept the old unprefixed private routes as backend compatibility aliases, and removed the frontend proxy rewrite dependency for those routes.

### Files Deleted

| Path | Reason | Safe rollback |
| --- | --- | --- |

### Files Quarantined

| Original path | Quarantine path | Reason | Planned delete date |
| --- | --- | --- | --- |

### Files Refactored

| Path | Change | Risk |
| --- | --- | --- |
| `Backend/app/main.py` | Mounted private routers under canonical `/api` paths while keeping hidden legacy aliases | Medium |
| `Backend/app/tests/test_api.py` | Added regression tests for canonical `/api` route aliases on users and security routers | Low |
| `Backend/docs/BACKEND_CHANGELOG.md` | Added Phase 3 route-normalization entry | Low |
| `Backend/docs/BACKEND_PROJECT_STRUCTURE_GUIDE.md` | Documented canonical `/api` private route strategy and legacy alias window | Low |
| `Backend/docs/BACKEND_FRONTEND_AUTH_ONBOARDING_GUIDE.md` | Updated frontend auth and face-onboarding routes to canonical `/api` paths | Low |
| `Backend/docs/BACKEND_PRODUCTION_DEPLOYMENT_GUIDE.md` | Documented that reverse proxies must preserve the `/api` prefix | Low |
| `Frontend/src/api/apiUrl.ts` | Removed repeated-prefix workaround and normalized `VITE_API_URL` handling around canonical `/api` paths | Medium |
| `Frontend/src/api/eventsApi.ts` | Moved event and attendance calls onto canonical `/api` private paths | Medium |
| `Frontend/src/api/facialVerificationApi.ts` | Moved privileged security calls onto `/api/auth/security/*` | Medium |
| `Frontend/src/api/platformOpsApi.ts` | Moved security-center calls onto `/api/auth/security/*` | Medium |
| `Frontend/src/api/studentEventCheckInApi.ts` | Moved event verification and face attendance scan calls onto canonical `/api` paths | Medium |
| `Frontend/src/api/studentFaceEnrollmentApi.ts` | Moved user-profile and student face-registration calls onto canonical `/api` paths | Medium |
| `Frontend/src/api/upcomingEventsApi.ts` | Moved upcoming-events queries onto `/api/events` | Low |
| `Frontend/src/pages/AcademicManagement.tsx` | Moved department and program CRUD calls onto canonical `/api` routes | Low |
| `Frontend/src/pages/CreateUsers.tsx` | Moved legacy user/dependency constants onto canonical `/api` routes | Low |
| `Frontend/src/pages/FaceScan.tsx` | Moved face registration and verification flows onto canonical `/api/face/*` routes | Medium |
| `Frontend/src/pages/ManageUsers.tsx` | Moved user, department, and program calls onto canonical `/api` routes | Medium |
| `Frontend/src/pages/ManualAttendance.tsx` | Updated debug logging to the canonical `/api/events` path family | Low |
| `Frontend/src/pages/Profile.tsx` | Moved profile reads and writes onto `/api/users/*` | Low |
| `Frontend/src/pages/Records.tsx` | Moved attendance reporting calls onto `/api/attendance/*` | Low |
| `Frontend/vite.config.ts` | Removed `/api` prefix stripping from the dev proxy and added explicit proxied docs aliases | Medium |
| `Frontend/nginx.prod.conf` | Stopped stripping `/api` from private backend requests while keeping `/api/docs` and `/api/redoc` compatibility | Medium |

### Routes Added Or Deprecated

| Route | Change type | Compatibility plan |
| --- | --- | --- |
| `/api/users/*` | added | Canonical private route family; keep `/users/*` alias for one deprecation cycle |
| `/api/events/*` | added | Canonical private route family; keep `/events/*` alias for one deprecation cycle |
| `/api/attendance/*` | added | Canonical private route family; keep `/attendance/*` alias for one deprecation cycle |
| `/api/programs/*` | added | Canonical private route family; keep `/programs/*` alias for one deprecation cycle |
| `/api/departments/*` | added | Canonical private route family; keep `/departments/*` alias for one deprecation cycle |
| `/api/auth/security/*` | added | Canonical private route family; keep `/auth/security/*` alias for one deprecation cycle |
| `/api/face/*` | added | Canonical private route family; keep `/face/*` alias for one deprecation cycle |

### Migrations Added

| Migration | Purpose | Rollback |
| --- | --- | --- |

### Behavior Changes

- Active frontend private API calls no longer depend on proxy-side `/api` stripping to reach backend routers.
- `/api/*` is now the documented private route family for users, events, attendance, departments, programs, security-center, and face endpoints.
- Old unprefixed private routes still work temporarily as backend compatibility aliases.

### Validation Performed

- `python -m pytest -q app/tests/test_api.py -k canonical_api_prefix`
- `npm run build`

### Rollback Notes

- Revert the Phase 3 route-normalization patch to restore proxy-rewrite-only behavior.
- If frontend proxy regressions appear, temporarily restore `/api` stripping in `Frontend/vite.config.ts` and `Frontend/nginx.prod.conf` while investigating.
