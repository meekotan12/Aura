# 2026-03 Refactor Quarantine

This archive holds legacy modules that were removed from the active runtime during Phase 1 cleanup.

Rules:

- nothing in this folder is part of the supported runtime path
- files stay here only long enough to support rollback or reference checks
- if a quarantined file is needed again, restore it deliberately instead of importing from `archive/`
- once telemetry and smoke checks are clean, delete the archived files in a later cleanup phase

Initial quarantine contents:

- legacy notification-center backend router, schema, model, and service
- unused frontend notification bell and notification API wrapper
- experimental tenant-database module
- inactive `event_attendance` model
- legacy worker attendance task file
