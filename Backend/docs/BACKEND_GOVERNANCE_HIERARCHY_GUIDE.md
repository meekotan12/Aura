# Backend Governance Hierarchy Guide

## Purpose

This guide documents the governance hierarchy foundation for `Campus Admin (canonical database role: campus_admin, legacy alias: school_IT) -> SSG -> SG -> ORG` and explains how the backend enforces parent-child creation rules, single-SSG setup, officer-level permissions, and student scope safety.

## Route Prefix Note

- canonical private backend routes in this guide now live under `/api/*`
- this especially applies to `/api/users/*`, `/api/events/*`, `/api/attendance/*`, `/api/programs/*`, `/api/departments/*`, `/api/auth/security/*`, and `/api/governance/*`
- the deprecated unprefixed private paths were removed

## Placement

- models:
  - `Backend/app/models/governance_hierarchy.py`
- schemas:
  - `Backend/app/schemas/governance_hierarchy.py`
- services:
  - `Backend/app/services/governance_hierarchy_service/`
    - `__init__.py`
    - `permissions.py`
    - `unit_lifecycle.py`
    - `membership.py`
    - `engagement.py`
    - `shared.py` (temporary internal compatibility layer)
- router:
  - `Backend/app/routers/governance_hierarchy.py`
- migration:
  - `Backend/alembic/versions/6f8c1234ab56_add_governance_hierarchy_management.py`
  - `Backend/alembic/versions/7c9e4b2a1d33_add_governance_member_permissions_and_single_ssg_guard.py`
  - `Backend/alembic/versions/8b7e6d5c4a3f_add_governance_unit_description_and_ssg_.py`
  - `Backend/alembic/versions/9c4d2e7f1a8b_seed_missing_sg_and_org_roles.py`
  - `Backend/alembic/versions/b4c8f12d9e77_cleanup_legacy_role_records.py`
  - `Backend/alembic/versions/c3d91e4ab2f6_drop_legacy_governance_role_artifacts.py`
  - `Backend/alembic/versions/d8e2f4c1b7aa_scope_departments_and_programs_per_school.py`
  - `Backend/alembic/versions/f2a6b8c9d0e1_add_governance_announcements_and_student_.py`

The router stays thin and delegates all hierarchy rules to the service layer so scope validation does not get duplicated across endpoints.

Current service-path note:

- the active create flow now relies directly on `_ensure_can_create_child_unit()` for child-unit creation checks
- governance route and feature checks now rely directly on `get_user_governance_unit_types()` and permission-based helpers
- the older unused convenience wrappers `can_create_child_unit()` and `user_has_governance_unit_type()` were removed after confirming they were not part of the current runtime flow
- new governance code should land in the package submodules above, not in `shared.py`, unless it is a deliberate compatibility extraction

## Campus Data Isolation

Academic scope records are now enforced per campus at the backend level.

- `departments.school_id` now owns each department row
- `programs.school_id` now owns each program row
- department names are unique only inside one school
- program names are unique only inside one school
- Campus Admin users can only list and fetch departments or programs inside their own campus
- governance creation rejects `department_id` or `program_id` values from another school
- import validation, student profile validation, event academic scope validation, and governance scope validation now all use same-school department/program lookups only

This removes the old leak where two campuses could accidentally share the same global department or program record.

## Data Model

### `governance_units`

Stores the hierarchy tree for `SSG`, `SG`, and `ORG`.

Fields:

- `id`
- `unit_code`
- `unit_name`
- `description`
- `unit_type`
- `parent_unit_id`
- `school_id`
- `department_id`
- `program_id`
- `created_by_user_id`
- `is_active`
- `event_default_early_check_in_minutes`
- `event_default_late_threshold_minutes`
- `event_default_sign_out_grace_minutes`
- `created_at`
- `updated_at`

Notes:

- `unit_code` is unique per `school_id`
- only one `SSG` unit is allowed per `school_id`
- only one active `SG` unit is allowed per `department_id`
- only one active `ORG` unit is allowed per `program_id`
- `SSG` units are school-wide, so `department_id` and `program_id` must be `null`
- `department_id` is the intended college-level scope in this project
- `SG` units are department-wide and must not store `program_id`
- `ORG` units represent program-level scope and must store both the parent `department_id` and their own `program_id`
- the fixed campus SSG can now store an editable `description` for the Campus Admin UI card
- `department_id` and `program_id` must belong to the same `school_id` as the governance unit
- `SG` and `ORG` can now optionally store override defaults for future event attendance windows
- `SSG` does not store a separate override and continues to inherit school defaults

### `governance_members`

Links a user to a governance unit.

Fields:

- `id`
- `governance_unit_id`
- `user_id`
- `position_title`
- `assigned_by_user_id`
- `assigned_at`
- `is_active`

Notes:

- one active membership row is stored per `governance_unit_id + user_id`
- imported users stay `student` first
- `SSG`, `SG`, and `ORG` memberships do not attach separate base roles
- all governance levels now use governance membership and permission codes only
- `SSG` memberships now require an explicit `position_title`; the backend no longer fills in a default officer title

## Final Role Model

Base auth roles:

- `admin`
- `campus_admin`
- `student`

Governance roles:

- `SSG`
- `SG`
- `ORG`

Important behavior:

- all imported student accounts remain `student`
- governance access is granted by active membership plus permissions
- the system no longer depends on separate base roles such as `ssg`, `sg`, `org`, or `event-organizer`

## Server-Side Protected Route Guards

Protected governance routes are now rejected by the backend before handler logic runs unless the caller is role-aligned for governance access.

The router-level guard accepts these actor types:

- `admin`
- `campus_admin`
- `student`
- legacy governance-role users still present in older data
- users with active governance membership, even if their base role is transitional

This matters because governance officers can be valid actors through membership plus permissions, not only through a base role string.

Examples:

- `GET /api/governance/access/me`
- `GET /api/governance/students`
- `POST /api/governance/units`
- `POST /api/governance/units/{governance_unit_id}/members`
- `POST /api/governance/units/{governance_unit_id}/announcements`

Campus Admin-only governance routes still use a stricter guard:

- `GET /api/governance/announcements/monitor`
- `GET /api/governance/ssg/setup`

These require `admin` or `campus_admin` before the service layer runs.

### `governance_member_permissions`

Stores granted permissions per governance member.

Fields:

- `id`
- `governance_member_id`
- `permission_id`
- `granted_by_user_id`
- `created_at`

Notes:

- permissions are now assigned to officers, not only to the unit
- this lets one SSG officer have `manage_events` while another only has `view_students`
- the current user's effective governance access now comes from active `governance_member_permissions`

### `governance_permissions`

Stores the permission catalog for governance units.

Fields:

- `id`
- `permission_code`
- `permission_name`
- `description`

This uses `governance_permissions` instead of a generic `permissions` table so the purpose stays obvious and does not collide with future auth-level permission work.

### `governance_unit_permissions`

Stores granted permissions per governance unit.

Fields:

- `id`
- `governance_unit_id`
- `permission_id`
- `granted_by_user_id`
- `created_at`

### `governance_announcements`

Stores SSG, SG, and ORG announcements in the database.

Fields:

- `id`
- `governance_unit_id`
- `school_id`
- `title`
- `body`
- `status`
- `created_by_user_id`
- `updated_by_user_id`
- `created_at`
- `updated_at`

Notes:

- announcements are scoped to one governance unit
- SSG, SG, and ORG announcement pages now read from the backend instead of browser storage
- `manage_announcements` is required to list, create, update, publish, archive, or delete records in that unit
- Campus Admin can also monitor these records school-wide through a separate read-only route

### `governance_student_notes`

Stores governance-only tags and notes for a student inside one governance unit.

Fields:

- `id`
- `governance_unit_id`
- `student_profile_id`
- `school_id`
- `tags`
- `notes`
- `created_by_user_id`
- `updated_by_user_id`
- `created_at`
- `updated_at`

Notes:

- one row is stored per `governance_unit_id + student_profile_id`
- notes stay scoped to the governance unit that created them
- these notes do not change the student's base role
- `view_students` or `manage_students` can read the note record
- only `manage_students` can create or update the note record

## Academic Scope Model

This project does not use a separate `colleges` table in the governance hierarchy.

The intended academic structure in this system is:

- `school_id`
- `department_id`
- `program_id`

Current hierarchy meaning:

- `SSG`
  - represents the whole campus-wide student government
- `department_id`
  - is the college-level academic scope
  - examples: `College of Engineering`, `College of Education`
- `SG`
  - represents the student government for one college-level `department_id`
- `program_id`
  - is the program scope under that college-level department
  - examples: `BS Computer Engineering`, `BS Civil Engineering`
- `ORG`
  - represents the program-level organization under the parent `SG`

Campus Admin therefore manages only:

- campus-wide `SSG`
- college-level `departments`
- program-level `programs`

There is no extra governance or academic `college_id` layer planned in this model.

## Permission Codes

Seeded permission codes:

- `create_sg`
- `create_org`
- `manage_students`
- `view_students`
- `manage_members`
- `manage_events`
- `manage_attendance`
- `manage_announcements`
- `assign_permissions`

## Event Default Precedence

Future governance events now resolve attendance-window defaults in this order:

1. explicit per-event request values
2. `ORG` override defaults on the current ORG unit
3. `SG` override defaults on the current SG unit
4. school defaults on `school_settings`
5. hard fallback `30 / 10 / 20`

This means:

- Campus Admin controls the school-wide baseline
- `SG` with `manage_events` can save department-wide future-event defaults for that SG
- `ORG` with `manage_events` can save program-wide future-event defaults for that ORG
- resetting the SG/ORG override to `null` returns that unit to the school default

## Route Summary

### `GET /api/governance/announcements/monitor`

Returns a Campus Admin monitoring list of governance announcements inside the current school only.

Rules:

- only `Campus Admin` or admin users with school context can access this route
- results are always filtered by the caller's `school_id`
- SSG, SG, and ORG announcements from another campus are excluded
- optional filters:
  - `status`
  - `unit_type`
  - `q`
  - `limit`

Response includes:

- announcement fields
- `governance_unit_code`
- `governance_unit_name`
- `governance_unit_type`
- `governance_unit_description`

### `POST /api/governance/units`

Creates a governance unit.

Rules:

- only `Campus Admin` can create `SSG`
- only one `SSG` can exist per school
- only active `SSG` members from the parent unit with `create_sg` can create `SG`
- only one active `SG` can exist per department
- only active `SG` members from the parent unit with `create_org` can create `ORG`
- only one active `ORG` can exist per program
- `SG` must include `department_id` and cannot include `program_id`
- `ORG` must include `program_id`
- `ORG` must stay inside the same `department_id` as its parent `SG`
- `ORG.program_id` must be linked to the parent `SG` department
- `department_id` and `program_id` are rejected if they belong to another campus

### `PATCH /api/governance/units/{governance_unit_id}`

Updates a governance unit.

Current phase-1 use:

- rename or edit the single campus `SSG`
- only `Campus Admin` can edit the `SSG`
- authorized `SSG` officers with `create_sg` on the parent `SSG` can edit `SG`
- authorized `SG` officers with `create_org` on the parent `SG` can edit `ORG`

### `GET /api/governance/ssg/setup`

Returns the Campus Admin SSG setup payload.

Rules:

- only `Campus Admin` can call this route
- if the school has no active `SSG` yet, the backend automatically creates the default campus SSG
- the default bootstrap values are:
  - `unit_code = SSG`
  - `unit_name = Supreme Students Government`
  - a default campus-wide description
- the response includes:
  - the full SSG unit detail
  - `total_imported_students` for the Manage SSG stats row

### `GET /api/governance/units`

Lists visible governance units inside the actor's school scope.

Response includes:

- lightweight unit summary fields
- `member_count` for active members in that unit

Notes:

- this route is intended for fast list screens such as `Manage SG` and `Manage ORG`
- it does not return the full member roster or unit permission objects
- use `GET /api/governance/units/{governance_unit_id}` when the frontend needs one selected unit's full detail

### `GET /api/governance/units/{governance_unit_id}`

Returns full unit details, including members and granted permissions.

### `GET /api/governance/units/{governance_unit_id}/dashboard-overview`

Returns the lightweight data used by the `SSG`, `SG`, and `ORG` dashboard cards.

Response includes:

- `published_announcement_count`
- `total_students`
- `recent_announcements`
  - only the latest dashboard items, not the whole history
- `child_units`
  - lightweight summaries with `member_count`

Rules:

- visible to actors who can already view that governance unit
- preserves the current dashboard permission behavior:
  - announcement data stays empty unless the actor can manage announcements in that unit
  - student totals stay `0` unless the actor can view or manage students in that unit
- avoids the old N+1 dashboard flow where the frontend fetched full child-unit details one by one and loaded the whole student list just to compute totals

### `GET /api/governance/units/{governance_unit_id}/event-defaults`

Returns the effective event-default settings for one governance unit.

Response includes:

- raw override values for that SG or ORG unit
- effective values after school fallback is applied
- `inherits_school_defaults`

Rules:

- visible to actors who can already view that governance unit
- useful for the SG and ORG Events settings panels

### `PUT /api/governance/units/{governance_unit_id}/event-defaults`

Creates or updates future-event default overrides for one governance unit.

Rules:

- `Campus Admin` can update these defaults inside the same school
- SG or ORG officers must have `manage_events` in that same unit
- `SSG` update attempts are rejected because school defaults must be changed through Campus Admin school settings
- sending `null` clears that SG/ORG override field and restores school fallback behavior

### `DELETE /api/governance/units/{governance_unit_id}`

Soft-deactivates an `SG` or `ORG`.

Rules:

- the fixed campus `SSG` cannot be deleted
- only actors who can edit that unit can deactivate it
- units with active child governance units must deactivate those children first
- deactivation hides the unit from the active list and removes active member access through that unit

### `GET /api/governance/access/me`

Returns the current user's active governance memberships and aggregated permission codes.

Use cases:

- hide empty SSG feature menus until permissions are granted
- gate SSG-only frontend routes like `Events`, `Records`, and `Manual Attendance`
- support future permission-based feature rollout without hard-coding SSG defaults

### `POST /api/governance/units/{governance_unit_id}/members`

Assigns or reactivates a governance member.

Rules:

- `Campus Admin` can manage `SSG` memberships in the same school
- `SSG` memberships stay Campus Admin-managed so lower levels cannot override the campus SSG
- child-unit memberships are managed from the parent unit:
  - `SSG` with `manage_members` manages `SG`
  - `SG` with `manage_members` manages `ORG`
- for `SSG`, the selected user must already exist as an imported student inside the same school
- for `SG`, the selected user must already exist as an imported student inside the same school and the same `department_id`
- for `ORG`, the selected user must already exist as an imported student inside the same school and the same `program_id`
- `SSG`, `SG`, and `ORG` access is derived from governance membership plus officer permission codes only
- `position_title` is required for all current governance memberships
- if that student already has an inactive membership in the same governance unit, the backend reactivates the existing membership row instead of creating a duplicate
- member permission codes are now validated per unit type:
  - `SSG` officers can receive `create_sg`
  - `SG` officers can receive `create_org`
  - invalid mixes such as `create_sg` on an `SG` member are rejected

### `PATCH /api/governance/members/{governance_member_id}`

Updates a governance member.

Current phase-1 use:

- change the selected imported student
- change `position_title`
- replace the officer's permission set
- for `SSG`, clearing `position_title` is rejected so officer records do not fall back to a default title
- permission-only edits now require `assign_permissions`
- member identity or position edits now require `manage_members`

### `DELETE /api/governance/members/{governance_member_id}`

Deactivates a governance member and clears the officer's governance permissions.

Current phase-1 use:

- remove an officer from the campus `SSG`
- `SSG` with `manage_members` can also remove `SG` officers from the selected department SG
- `SG` with `manage_members` can also remove `ORG` officers from the selected program ORG
- deleting a governance member deactivates that membership so the same student can be assigned again later and reactivate the same record

### `GET /api/governance/units/{governance_unit_id}/announcements`

Lists announcements for one governance unit.

Rules:

- requires `manage_announcements` in that same unit
- Campus Admin can inspect the unit inside the same school scope

### `POST /api/governance/units/{governance_unit_id}/announcements`

Creates an announcement under one governance unit.

Rules:

- requires `manage_announcements` in that same unit
- announcement scope is the governance unit itself, not the whole school automatically

### `PATCH /api/governance/announcements/{announcement_id}`

Updates title, body, or status for one announcement.

### `DELETE /api/governance/announcements/{announcement_id}`

Deletes one announcement record.

### `GET /api/governance/units/{governance_unit_id}/student-notes/{student_profile_id}`

Returns the current governance note for one student in one governance unit.

Rules:

- requires `view_students` or `manage_students`
- the student must be inside that unit's allowed scope

### `PUT /api/governance/units/{governance_unit_id}/student-notes/{student_profile_id}`

Creates or updates the governance note for one student in one governance unit.

Rules:

- requires `manage_students`
- tags are normalized and deduplicated
- the student must be inside that unit's allowed scope

### `GET /api/governance/students/search`

Searches imported student candidates for governance assignment.

Query params:

- `q`
- `governance_unit_id`
- `limit`

Current phase-1 use:

- search imported students by name, email, or `student_id`
- exclude students who are already active members of the current `SSG`
- when the target unit is `SG`, only return imported students inside that SG department
- when the target unit is `ORG`, only return imported students inside that ORG program
- non-Campus-Admin callers must pass a target child unit they are allowed to manage

### `GET /api/governance/students`

Returns the current actor's accessible imported students using governance scope rules.

Query params:

- `governance_context`
  - optional
  - `SSG`, `SG`, or `ORG`
  - narrows the response to one governance layer when the current user has multiple memberships
- `skip`
  - optional
  - defaults to `0`
  - supports paginated student-directory pages such as `/ssg_students`, `/sg_students`, and `/org_students`
- `limit`
  - optional
  - capped at `250`
  - governance student pages now request `101` rows and render `100` per page so the UI can detect whether a next page exists

Rules:

- `Campus Admin` receives all imported students in the same school
- `SSG`, `SG`, and `ORG` members only receive students when they have:
  - `view_students`
  - `manage_students`
- school-wide units return all school students
- `SG` units return department-scoped students
- `ORG` units return program-scoped students

Frontend use:

- `SSGDashboard` now uses this route for the student total card instead of the Campus Admin-only `/users/` API
- `SsgStudents` now uses this route for the student directory so SSG officers no longer hit user-management permission errors
- `SsgStudents`, `SgStudents`, and `OrgStudents` now page through this route in `100`-row slices instead of loading the full accessible directory at once

### `POST /api/governance/units/{governance_unit_id}/permissions`

Assigns a permission to a governance unit.

Rules:

- `Campus Admin` can bootstrap any unit in the same school
- members with `assign_permissions` on their own unit can grant permissions
- parent-unit creators can bootstrap child permissions right after creating `SG` or `ORG`

Note:

- this route still exists for unit-level rollout work, but the current SSG feature gating uses officer-level `governance_member_permissions`

## Campus Admin Frontend Entry

The current frontend rollout is exposed through a dedicated Campus Admin screen instead of reusing the existing data-governance page.

Frontend entry points:

- route: `/campus_admin_governance_hierarchy`
- page: `Frontend/src/pages/GovernanceHierarchyManagement.tsx`
- navbar link: `Frontend/src/components/NavbarSchoolIT.tsx`
- dashboard card: `Frontend/src/dashboard/SchoolITDashboard.tsx`

The screen is intentionally limited to the campus `SSG` management flow:

- load the fixed campus `SSG` through `GET /api/governance/ssg/setup`
- show the fixed `SSG` info card with abbreviation, name, campus, and description
- rename or edit that `SSG`
- search imported student users by name or `student_id`
- assign students as SSG officers
- set `position_title`
- assign officer-level permissions
- edit or remove officers

This keeps the Campus Admin screen focused on the fixed campus `SSG` while lower-level governance management happens in the `SSG -> Manage SG` and `SG -> Manage ORG` screens.

Additional Campus Admin monitoring routes:

- `/campus_admin_reports`
  - school-scoped event attendance reports
- `/campus_admin_attendance`
  - school-scoped student attendance monitoring
- `/campus_admin_announcements`
  - school-scoped governance announcement monitor for SSG, SG, and ORG units

## SSG Frontend Entry

The current `SSG -> Manage SG` rollout now has its own SSG-facing screen.

Frontend entry points:

- route: `/ssg_manage_sg`
- page: `Frontend/src/pages/ManageSg.tsx`
- navbar link: `Frontend/src/components/NavbarSSG.tsx`
- dashboard card: `Frontend/src/dashboard/SSGDashboard.tsx`

Current `Manage SG` behavior:

- the page is only visible when the signed-in `SSG` officer has at least one of:
  - `create_sg`
  - `manage_members`
  - `assign_permissions`
- the SG unit grid loads from `GET /api/governance/units` and uses `member_count` instead of preloading full details for every SG unit
- full SG member and permission data loads only when the user opens the selected unit's `Members` or `Permissions` tabs
- `create_sg`
  - allows creating one department-wide `SG` per department
  - allows editing SG info
- `manage_members`
  - allows searching imported students inside the selected SG department
  - allows assigning, updating, and removing SG members
- `assign_permissions`
  - allows editing the SG officer permission set
  - does not by itself allow adding or removing SG members

SG member permission groups in the current frontend:

- `Event Management`
  - `manage_events`
  - `manage_announcements`
- `Attendance Management`
  - `manage_attendance`
- `Student Management`
  - `view_students`
  - `manage_students`
- `ORG Management`
  - `create_org`
  - `assign_permissions`
  - `manage_members`

## SG and ORG Frontend Entry

The SG and ORG officer layers now have their own workspace routes and permission-gated sidebars.

Frontend entry points:

- SG routes:
  - `/sg_dashboard`
  - `/sg_announcements`
  - `/sg_students`
  - `/sg_events`
  - `/sg_records`
  - `/sg_manual_attendance`
  - `/sg_manage_org`
  - `/sg_profile`
- ORG routes:
  - `/org_dashboard`
  - `/org_announcements`
  - `/org_students`
  - `/org_events`
  - `/org_records`
  - `/org_manual_attendance`
  - `/org_profile`

Frontend behavior:

- dashboard resolution now prefers:
  - `SSG`
  - then `SG`
  - then `ORG`
  - then normal `student`
- route guards now check permissions inside the required governance unit type instead of using aggregated permissions from another unit
- SG and ORG workspaces now use the same sidebar/card/modal pattern as the SSG workspace
- `Manage ORG` is visible only when the SG officer has:
  - `create_org`
  - `manage_members`
  - or `assign_permissions`
- the ORG unit grid also loads from `GET /api/governance/units` and uses `member_count` instead of preloading full ORG details for every card
- full ORG member and permission data loads only when the user opens the selected unit's `Members` or `Permissions` tabs

## Governance-Scoped Events and Attendance

Governance pages now pass `governance_context` to backend event and attendance routes so scope is enforced server-side.

For event writes, the backend now also protects governance scope when `governance_context` is omitted:

- if the governance writer has one unambiguous `manage_events` scope, the backend infers that scope automatically
- if the governance writer can manage multiple event unit types, the write request must include `governance_context=SSG|SG|ORG`
- out-of-scope event update, delete, and status writes are rejected even when the governance writer omits `governance_context`

Event scope behavior:

- `SSG`
  - school-wide only
  - event writes are forced to no department or program filters
- `SG`
  - department-wide only
  - event writes are forced to the SG department
- `ORG`
  - program-wide only
  - event writes are forced to the ORG department + program scope
  - this is program-level student visibility, not governance-member-only visibility

Attendance scope behavior:

- `SG` attendance operators can only work with:
  - SG-scoped events
  - students inside the SG department
- `ORG` attendance operators can only work with:
  - ORG-scoped events
  - students inside the ORG program

Student visibility behavior without `governance_context`:

- normal student event lists now expose all same-school `upcoming` events
- once an event is no longer `upcoming`, student event lists fall back to the student's own academic scope
- for active or historical events, students can still see:
  - school-wide events
  - department-wide events for their department
  - program-wide events for their program
- out-of-scope ongoing or completed events from the same campus remain hidden
- direct student access to out-of-scope active event detail and verification routes still returns `404`

Affected backend routes now support optional `governance_context`:

- `/events`
- `/events/ongoing`
- `/events/{event_id}`
- `/events/{event_id}/time-status`
- `/events/{event_id}/verify-location`
- `/events/{event_id}/attendees`
- `/events/{event_id}/stats`
- `/events/{event_id}/status`
- `/attendance/events/{event_id}/report`
- `/attendance/students/overview`
- `/attendance/students/{student_id}/report`
- `/attendance/manual`
- `/attendance/bulk`
- `/attendance/events/{event_id}/mark-excused`
- `/attendance/events/{event_id}/attendees`
- `/attendance/{attendance_id}/time-out`
- `/attendance/face-scan-timeout`
- `/attendance/events/{event_id}/attendances`
- `/attendance/events/{event_id}/attendances/{status}`
- `/attendance/events/{event_id}/attendances-with-students`
- `/attendance/mark-absent-no-timeout`

## Campus Admin User Management Lock

Campus Admin user management is now intentionally student-focused.

Current behavior:

- `Manage Users` can still edit basic student account details and academic fields
- `Manage Users` now walks every `/users/` page, so large imports do not disappear after the first 100 default results
- `Manage Users` now keeps the first page lighter by loading department and program option lists only when the edit modal opens
- Campus Admin can no longer promote users to `ssg` or `event-organizer` through `/users`
- Campus Admin can no longer update roles through `/users/{user_id}/roles`
- imported users stay students first
- SSG officer access must be assigned from `Manage SSG`

Backend pagination details:

- `GET /users/` now returns results in ascending `user.id` order before `skip` and `limit` are applied
- `GET /users/by-role/{role_name}` now uses the same stable ordering
- both user list routes now eager-load `roles.role` and `student_profile` before response serialization so `Manage Users` avoids one-query-per-row relation loading
- each request is capped at `500` rows, so frontend callers should continue paging for larger schools

This keeps governance elevation inside one workflow instead of splitting it across `Manage Users`, import logic, and the SSG setup screen.

## Empty SSG Features By Default

The current SSG rollout treats governance permissions as the only source of SSG feature access.

That means:

- a student does not automatically get SSG features just because they exist in the same school
- active SSG membership alone is not enough to unlock feature pages
- Campus Admin must assign governance permissions to the SSG officer membership first
- the frontend hides SSG feature links when the aggregated permission set is empty
- the backend blocks SSG attendance features unless the user has `manage_attendance`
- SSG event-management writes require `manage_events`

Current frontend mapping:

- `manage_events`
  - unlocks the SSG `Events` feature route
- `manage_attendance`
  - unlocks the SSG `Records` feature route
  - unlocks the SSG `Manual Attendance` feature route

## Student Access Rules

The service method `get_accessible_students()` applies these rules:

- `Campus Admin` sees all students in the same school
- governance members only see students when one of their units has `view_students` or `manage_students`
- if the unit is school-wide, the member can see all students in the school
- if the unit has only `department_id`, the student query is filtered to that department-wide scope
- if the unit has both `department_id` and `program_id`, the student query is filtered to that program inside the department

## How To Test

1. Run `alembic upgrade head` inside `Backend/`.
2. Run:
   - `python -m compileall Backend/app`
   - `Backend\.venv\Scripts\python.exe -m pytest -q Backend/app/tests/test_governance_hierarchy_api.py Backend/app/tests/test_auth_session_login_guard.py`
3. Log in as a `campus_admin` user (legacy `school_IT` accounts still work) and open `/campus_admin_governance_hierarchy`.
4. Smoke-test the Campus Admin Manage SSG flow from the frontend or API:
   - confirm the default campus `SSG` is returned even when none existed yet
   - edit the `SSG` name or description
   - search an imported student by `student_id` or name
   - assign that student to the `SSG`
   - set a non-empty `position_title`
   - assign officer permissions such as `manage_events` or `manage_attendance`
   - search again and confirm the same student no longer appears in add-member search
   - remove that officer, assign the same student again, and confirm the membership is reactivated without an internal server error
   - try saving an SSG officer without `position_title` and confirm the backend rejects it
   - try creating a second `SSG` through the generic units route and confirm the backend blocks it
5. Verify Campus Admin user-management lock:
   - open `Manage Users` as `campus_admin`
   - confirm more than 100 imported student accounts still load in the roster for a large school
   - confirm role editing is hidden for Campus Admin
   - confirm officer assignments are described as a `Manage SSG` action instead
   - call `PUT /users/{user_id}/roles` as Campus Admin and confirm it returns `403`
6. Verify empty-feature behavior for SSG:
   - log in as a `student` user who is an active SSG officer but has no officer-level governance permissions
   - confirm SSG feature links are hidden or blocked
   - grant `manage_events` or `manage_attendance` to that officer membership
   - refresh and confirm the matching SSG features appear
7. Verify `Manage SG`:
   - log in as an `ssg` user with `create_sg`, `manage_members`, and `assign_permissions`
   - open `/ssg_manage_sg`
   - confirm the first screen loads from `GET /api/governance/units` without one follow-up detail request per SG card
   - create a department SG and confirm departments already used by another SG cannot be selected again
   - edit the SG name or description
   - search imported students and confirm only students from that department appear
   - assign an SG officer with a non-empty `position_title`
   - confirm the assignment succeeds without creating or attaching a base `sg` role
   - try assigning `create_sg` to an SG member and confirm the backend rejects it
   - remove an SG officer and confirm the record is deactivated cleanly
   - assign the same SG student again and confirm the backend reactivates the officer membership cleanly
8. Verify governance-scoped student access:
   - log in as an `SSG` officer with `view_students` or `manage_students`
   - open `/ssg_dashboard` and confirm the page no longer raises `Requires admin or Campus Admin role`
   - confirm the dashboard loads through `GET /api/governance/units/{governance_unit_id}/dashboard-overview`
   - confirm the dashboard student total appears without fetching the full student list first
   - open `/ssg_students` and confirm the list loads from `/api/governance/students`
   - confirm the returned students match the officer's governance scope
   - import or create more than `100` students and confirm `/ssg_students` shows `Previous` and `Next` pagination controls
   - move to the next page and confirm the page requests the next `100` students instead of reloading the full campus directory
9. Verify SG and ORG workspaces:
   - log in as an SG officer with:
     - `manage_events`
     - `manage_attendance`
     - `manage_announcements`
     - `view_students` or `manage_students`
     - `create_org`, `manage_members`, and `assign_permissions`
    - confirm these routes load:
      - `/sg_dashboard`
      - `/sg_announcements`
      - `/sg_students`
      - `/sg_events`
      - `/sg_records`
      - `/sg_manual_attendance`
      - `/sg_manage_org`
    - confirm `/sg_dashboard` loads from the dashboard overview route and no longer makes one child-unit detail request per ORG card
    - confirm `/sg_manage_org` first loads from `GET /api/governance/units` and does not preload full detail for every ORG card
    - confirm SG event pages only show department-scoped events
   - call `POST /events/` without `governance_context` and confirm the backend still forces the created event to the SG department scope
   - confirm SG attendance pages reject students outside the SG department
   - import or create more than `100` in-scope SG students and confirm `/sg_students` paginates through the directory in `100`-row pages
   - log in as an ORG officer with matching permissions
   - confirm these routes load:
     - `/org_dashboard`
     - `/org_announcements`
     - `/org_students`
     - `/org_events`
     - `/org_records`
     - `/org_manual_attendance`
    - confirm `/org_dashboard` loads from the dashboard overview route and still shows the same officer list and announcement summary behavior
   - confirm ORG event pages only show program-scoped events
   - call `POST /events/` without `governance_context` and confirm the backend still forces the created event to the ORG department + program scope
   - save SG or ORG event defaults from the Events settings panel and confirm the next newly created event uses those values automatically
   - reset the override to inherit school defaults and confirm the next newly created event returns to the school values
   - confirm ORG student pages only show students in the ORG program
   - import or create more than `100` in-scope ORG students and confirm `/org_students` paginates through the directory in `100`-row pages
   - remove and re-add an ORG officer from `Manage ORG` and confirm the reassignment succeeds without a server error
   - try updating an out-of-scope event without `governance_context` and confirm the backend returns `404 Event not found`
10. Verify persisted announcements and notes:
   - create an SSG announcement
   - refresh the browser and confirm it still exists
   - create an SG or ORG announcement
   - log out and log back in with the same officer and confirm it still exists
   - open an SSG, SG, or ORG student detail panel
   - save governance tags and notes
   - refresh and confirm the saved tags and notes still load
11. Verify student event visibility:
   - log in as a normal student with a department and program
   - confirm `/events/` returns all same-school upcoming events, including those outside the student's own department or program
   - confirm out-of-scope ongoing or completed events are still hidden from `/events/`
   - confirm a direct request to another department's active event detail returns `404`
12. Verify SG and ORG deactivation:
   - delete an `SG` or `ORG` from the workspace UI
   - confirm the unit disappears from the active unit list
   - confirm members from that unit lose access through the deleted unit
   - try deleting an `SG` that still has an active child `ORG` and confirm the backend blocks it
13. Verify scope safety:
   - log in as Campus Admin for campus A and confirm `/departments/` and `/programs/` only return campus A data
   - log in as Campus Admin for campus B and confirm campus A academic data stays hidden
   - confirm `/api/governance/units` only returns units from the actor's own school
   - log in as the assigned `SSG` member and create an `SG`
   - try creating a second `SG` in the same department and confirm the backend blocks it
   - confirm the backend rejects an `SG` request that includes `program_id`
   - try creating an `SG` from campus A using a department id from campus B and confirm the backend rejects it
   - grant `create_org` to an `SG`
   - confirm the backend rejects an `ORG` request without `program_id`
   - try creating a second `ORG` for the same program and confirm the backend blocks it
   - confirm an `ORG` cannot be created outside the parent `SG` department scope
   - confirm an `ORG.program_id` must belong to the parent `SG` department
14. Verify schema cleanup after migration:
   - confirm the database no longer contains the `ssg_profiles` table
   - confirm the database no longer contains the `event_ssg_association` table
   - confirm `governance_members` no longer has `role_id`
   - confirm legacy `ssg` and `event-organizer` role rows are removed
15. Verify Campus Admin monitoring:
   - open `/campus_admin_reports` and confirm Campus Admin can load school-scoped event attendance reports
   - open `/campus_admin_attendance` and confirm the attendance overview only shows students from the current campus
   - open `/campus_admin_announcements` and confirm only governance announcements from the current campus appear
   - create or update an announcement in another campus and confirm it does not appear in the first Campus Admin monitor
