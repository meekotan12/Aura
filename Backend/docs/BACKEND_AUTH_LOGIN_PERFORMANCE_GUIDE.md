# Backend Auth Login Performance Guide

## Purpose

This guide explains how login-side effects were moved off the main request path so normal frontend login feels faster without changing the login API contract.

For frontend integration details for the new onboarding flow, see `Backend/docs/BACKEND_FRONTEND_AUTH_ONBOARDING_GUIDE.md`.

## Main Files

- `Backend/app/routers/auth.py`
- `Backend/app/services/auth_task_dispatcher.py`
- `Backend/app/services/email_service.py`
- `Backend/app/services/notification_center_service.py`
- `Backend/app/workers/tasks.py`
- `Backend/app/core/database.py`
- `Backend/app/core/dependencies.py`
- `Backend/app/core/security.py`
- `Backend/app/routers/health.py`
- `Backend/app/tests/test_auth_task_dispatcher.py`

## What Changed

- normal `/login` no longer waits for account-security email delivery before returning the auth response
- MFA login no longer blocks on the full SMTP send path when async dispatch is available
- Celery is used first for login-side email and notification work
- if Celery publish fails, the backend falls back to FastAPI background tasks so the HTTP response can still finish quickly
- obvious SMTP configuration errors are still validated before scheduling MFA delivery
- forced SQL query logging was removed unless `SQL_ECHO=true`
- the canonical async task package now lives in `Backend/app/workers/`, while `Backend/app/worker/` remains only as a compatibility wrapper
- newly created onboarding accounts now keep `must_change_password=false`, so they can continue past login with the issued temporary password
- temporary passwords issued by reset flows still keep `must_change_password=true`
- `/auth/change-password` now validates `current_password` with the same password verifier used by `/login`
- login responses now include `password_change_recommended` for one-time onboarding suggestions
- new users can dismiss that suggestion through `POST /auth/password-change-prompt/dismiss` and continue to face onboarding
- `/users/` creation responses now include `generated_temporary_password` when the backend generated the password, while still honoring a caller-supplied password when present
- database pooling is now configurable with `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, and `DB_POOL_RECYCLE_SECONDS`
- auth handlers and auth dependencies now run as sync callables so synchronous SQLAlchemy and bcrypt work execute in FastAPI's threadpool instead of blocking the event loop
- login eager-loads roles, school settings, and face profile in one query to reduce pool pressure
- `GET /health` now reports database reachability plus current SQLAlchemy pool usage

## Request Flow

### `/login`

1. validate credentials
2. validate account and school state
3. issue token payload
4. record login history
5. queue account-security notification asynchronously
6. commit and return response

### `/login` with MFA

1. validate credentials
2. create MFA challenge
3. validate SMTP configuration
4. queue MFA email asynchronously
5. commit and return MFA challenge response

### `/auth/mfa/verify`

1. verify challenge code
2. issue token payload
3. record login history
4. queue MFA-completed security notification asynchronously
5. commit and return response

### Password prompt during onboarding

1. new onboarding accounts log in with `must_change_password=false`
2. the backend returns `password_change_recommended=true` when `users.should_prompt_password_change=true`
3. the frontend can either call `/auth/change-password` immediately or skip with `POST /auth/password-change-prompt/dismiss`
4. privileged users can still continue to `/auth/security/face-*` while holding a `face_pending` token
5. forced reset flows still use `must_change_password=true` and bypass the optional prompt path entirely

## Notes

- added `POST /auth/password-change-prompt/dismiss`
- login responses can now include `password_change_recommended`
- `/users/` create responses can now include `generated_temporary_password`
- login still records DB session and login-history data synchronously
- email and notification side effects are the parts that moved off the request path
- current Celery startup path is `app.workers.celery_app.celery_app`
- the backend password stack is expected to use a `passlib`-compatible `bcrypt` release so login logs stay clean during password verification
- current default pool capacity per process is `10 + 10 overflow`
- `pool_recycle` defaults to `1800` seconds so stale Railway connections get refreshed before idle disconnects become request failures
- `pool_use_lifo=True` helps burst traffic reuse hot connections instead of spreading churn evenly across the whole pool

## Recommended Production Pooling

Environment variables:

- `DB_POOL_SIZE=10`
- `DB_MAX_OVERFLOW=10`
- `DB_POOL_TIMEOUT_SECONDS=15`
- `DB_POOL_RECYCLE_SECONDS=1800`

Use this capacity formula:

- total potential DB connections = `worker_count * (DB_POOL_SIZE + DB_MAX_OVERFLOW)`

Keep that total comfortably below your Railway Postgres connection limit, with headroom for migrations, admin sessions, and background jobs.

## Railway Worker And Pool Balance

These are safe starting points for login-heavy traffic. Adjust only after checking `GET /health`.

| Railway shape | API workers | DB pool size | Max overflow | Max potential DB conns |
| --- | ---: | ---: | ---: | ---: |
| Small / shared CPU | 1 | 8 | 4 | 12 |
| Medium | 2 | 8 | 4 | 24 |
| Medium with heavier bursts | 2 | 10 | 5 | 30 |
| Large | 3 | 10 | 5 | 45 |
| Large dedicated | 4 | 10 | 5 | 60 |

Guidelines:

- if bcrypt CPU is the bottleneck, add workers before pushing pool sizes much higher
- if the pool saturates but CPU stays low, increase pool size carefully
- never raise workers and pool capacity at the same time without recalculating the total connection budget

## Health Check

`GET /health`

Returns:

- database reachability using `SELECT 1`
- pool class
- configured pool size
- checked-in and checked-out connections
- overflow connections
- total connection capacity
- utilization ratio

Example response:

```json
{
  "status": "ok",
  "database": {
    "ok": true,
    "detail": null
  },
  "pool": {
    "pool_class": "QueuePool",
    "configured_pool_size": 10,
    "max_overflow": 10,
    "checked_in_connections": 7,
    "checked_out_connections": 3,
    "overflow_connections": 0,
    "total_capacity": 20,
    "available_slots": 17,
    "pool_timeout_seconds": 15,
    "pool_recycle_seconds": 1800,
    "utilization_ratio": 0.15
  }
}
```

## Temporary Password Policy

- onboarding-created accounts from user creation, school creation, and import flows are no longer forced through `/auth/change-password`
- reset-issued temporary passwords still require `/auth/change-password` after login
- onboarding-created accounts now use a separate `should_prompt_password_change` flag, surfaced as `password_change_recommended` in login responses
- the prompt can be dismissed through `POST /auth/password-change-prompt/dismiss` without affecting the reset-password enforcement flow
- forced password change now checks the current password through the same hash-verification path used by login, so emailed temporary passwords stay valid there too
- `POST /api/school/admin/create-school-it` and `POST /users/` now give the caller a reliable first-login password path by either honoring the supplied password or returning `generated_temporary_password`

## Testing

Run:

`python -m pytest -q`

Recommended manual checks:

1. Log in as a normal student account and confirm the response returns quickly.
2. Log in as an admin or School IT account and confirm MFA challenge creation still works.
3. Complete `/auth/mfa/verify` and confirm the login still succeeds.
4. If Celery is running, confirm login email/notification tasks appear in the worker.
5. If Celery is unavailable, confirm login still returns and background-task fallback keeps the flow working.
6. Confirm backend logs do not show a `bcrypt` compatibility traceback during login or password checks.
7. Create a new onboarding account and confirm login returns `password_change_recommended=true` instead of forcing `/auth/change-password`.
8. Call `POST /auth/password-change-prompt/dismiss` with that account and confirm the next login no longer recommends a password change.
9. For a privileged account, confirm `face_pending` onboarding still allows both `/auth/change-password` and `POST /auth/password-change-prompt/dismiss`.
10. Approve a password reset and confirm the temporary reset password is still forced through `/auth/change-password`.
11. On the forced password-change screen, submit the same temporary password used at login as `current_password` and confirm the change succeeds.
12. Call `GET /health` and confirm the pool snapshot matches your configured `DB_POOL_*` values.
13. Run a login-heavy load test and confirm `checked_out_connections` stays below total capacity most of the time.
