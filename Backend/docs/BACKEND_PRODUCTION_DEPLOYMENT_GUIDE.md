# Backend Production Deployment Guide

## Purpose

This guide documents the single Docker Compose release path for the repo. The stack now uses only `docker-compose.yml` so local and cloud-style deployment share the same service definitions.

## Main Files

- `docker-compose.yml`
- `Backend/Dockerfile.prod`
- `Backend/scripts/run-service.sh`
- `Backend/.dockerignore`
- `Frontend/Dockerfile.prod`
- `Frontend/nginx.prod.conf`
- `Frontend/.dockerignore`
- `tools/load_test.py`
- `Backend/docs/BACKEND_GOOGLE_EMAIL_DELIVERY_GUIDE.md`

## What Changed

- consolidated the old split compose setup into one `docker-compose.yml`
- kept the production backend image that runs `uvicorn` without `--reload`
- kept separate worker and beat runtime support through the same production backend image
- added `SERVICE_MODE` support in the backend image so the same container can run:
  - the FastAPI web service
  - the Celery worker
  - the Celery beat scheduler
  - a one-shot Alembic migration job
- kept the frontend production image that builds Vite assets and serves them through `nginx`
- kept the `nginx` proxy rules so the frontend still forwards:
  - `/api/*`
  - `/api/docs`
  - `/api/redoc`
  - `/token`
  - `/openapi.json`
  - `/docs`
  - `/redoc`
  - `/media/school-logos/*`
- added a one-shot `migrate` service so Alembic runs before backend, worker, and beat start
- corrected the Compose build contexts to use the real `Backend/` and `Frontend/` directory casing so Linux deployments do not fail on case-sensitive filesystems
- changed direct Postgres, Redis, Mailpit, pgAdmin, and backend port mappings to loopback by default for safer VM and cloud deployment
- kept the reusable concurrent load-test script for health, login, events, and mixed authenticated traffic

## Release Startup

1. prepare `.env` with real deployment values
2. build and start the release stack:

`docker compose up -d --build`

3. open the frontend at:

`http://localhost:${FRONTEND_PORT:-5173}`

4. open the backend docs through the frontend proxy at:

`http://localhost:${FRONTEND_PORT:-5173}/api/docs`

5. optional local admin tools:

`docker compose --profile tools up -d pgadmin`

## Runtime Notes

- the frontend is the intended public entrypoint
- the backend is also bound to loopback by default at `127.0.0.1:${BACKEND_PORT:-8000}` for direct smoke checks from the host
- PostgreSQL and Redis are bound to loopback only by default
- backend media and import storage remain on named volumes
- frontend reverse proxies must preserve the `/api` prefix for backend private routes; only the proxied docs paths such as `/api/docs` should rewrite to backend docs endpoints
- the backend startup script now creates the configured import and logo storage directories before `uvicorn` starts so Railway-mounted `/data/*` paths are writable on first boot
- Celery worker and beat still require Redis and the same backend environment variables
- the default local SMTP target is `mailpit`; set the Google mail variables in `Backend/.env.example` for real email delivery
- local backend runs now check both `Backend/.env` and the repo-root `.env`, while real exported environment variables still win over dotenv values
- the backend now validates outbound email config during startup when `EMAIL_TRANSPORT=smtp` or `EMAIL_TRANSPORT=gmail_api`
- set `EMAIL_VERIFY_CONNECTION_ON_STARTUP=true` temporarily if you want the backend to fail fast on a broken Google mail login during rollout
- face endpoints now lazy-load the optional `face_recognition` dependency so the backend can still boot for auth, import, attendance, and governance flows when that runtime is missing
- when the optional face runtime is missing, face routes return an explicit `503` dependency error instead of crashing module import during startup
- student attendance now supports a configurable test-account bypass via `FACE_SCAN_BYPASS_EMAILS`; Railway deployments should set this explicitly instead of hardcoding a bypass email in source
- the `b8e4c1d2f7a9` sign-out delay migration now checks whether `events.sign_out_open_delay_minutes` already exists before altering the table, which avoids duplicate-column failures during Railway redeploys or partially reconciled environments

## Railway Mapping

Use the same backend image for each Railway service and only change `SERVICE_MODE`.

- API service:
  - `SERVICE_MODE=web`
- Worker service:
  - `SERVICE_MODE=worker`
- Beat service:
  - `SERVICE_MODE=beat`
- Optional one-shot migration service:
  - `SERVICE_MODE=migrate`

For the API service, Railway injects `PORT` automatically and the backend now binds to that value.

## Required Environment Review

Set these before a real cloud deployment:

- `SECRET_KEY`
- `LOGIN_URL`
- `CORS_ALLOWED_ORIGINS`
- `POSTGRES_PASSWORD`
- `DATABASE_ADMIN_URL` if tenant provisioning should connect through a separate admin database URL
- `TENANT_DATABASE_PREFIX` if tenant database names and keys should use a prefix other than `school`
- `EMAIL_TRANSPORT=smtp` if forgot-password, MFA, onboarding, or notification emails must leave the host
- use `EMAIL_TRANSPORT=gmail_api` on Railway if SMTP still times out or your plan does not allow outbound SMTP
- `EMAIL_REQUIRED_ON_STARTUP=true`
- `FACE_SCAN_BYPASS_EMAILS` if you want specific student accounts such as `jrmsu@university.edu` to skip biometric verification in test or staging environments
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_TIMEOUT_SECONDS`, `SMTP_FROM_NAME`, `SMTP_FROM_EMAIL`, `SMTP_REPLY_TO`, `SMTP_USE_TLS`, `SMTP_USE_SSL`
- `SMTP_AUTH_MODE`
- `SMTP_USERNAME` and `SMTP_PASSWORD` for App Password or SMTP AUTH flows
- `SMTP_GOOGLE_ACCOUNT_TYPE` and `SMTP_GOOGLE_ALLOW_CUSTOM_FROM` if you want a Workspace `no-reply@domain` sender
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`, `GOOGLE_OAUTH_AUTH_URL`, and `GOOGLE_OAUTH_TOKEN_URL` for `EMAIL_TRANSPORT=gmail_api` or `SMTP_AUTH_MODE=xoauth2`
- `GOOGLE_OAUTH_SCOPES` and `GOOGLE_GMAIL_API_BASE_URL` for `EMAIL_TRANSPORT=gmail_api`
- use exactly one SMTP transport mode:
  - `SMTP_USE_TLS=true` and `SMTP_USE_SSL=false` for STARTTLS, commonly port `587`
  - `SMTP_USE_TLS=false` and `SMTP_USE_SSL=true` for implicit SSL, commonly port `465`
- see `Backend/docs/BACKEND_GOOGLE_EMAIL_DELIVERY_GUIDE.md` for the exact Google Workspace mailbox, Gmail App Password, SMTP relay, and XOAUTH2 setup steps

## Load Testing

### Health-only smoke load

`python tools/load_test.py --base-url http://127.0.0.1:${FRONTEND_PORT:-5173} --scenario health --requests 50 --concurrency 10`

### Direct backend login load

`python tools/load_test.py --base-url http://127.0.0.1:${BACKEND_PORT:-8000} --scenario login --email your-user@example.com --password your-password --requests 100 --concurrency 20`

### Frontend-proxied mixed traffic

`python tools/load_test.py --base-url http://127.0.0.1:${FRONTEND_PORT:-5173} --api-prefix /api --scenario mixed --email your-user@example.com --password your-password --requests 100 --concurrency 20 --include-governance`

## Testing

- validate config:
  - `docker compose config -q`
- validate both compose manifests explicitly if you keep separate local and production files:
  - `docker compose -f docker-compose.yml config -q`
  - `docker compose -f docker-compose.prod.yml config -q`
- validate the Alembic graph before a fresh cloud deploy:
  - `cd Backend && alembic heads`
- validate the live schema can accept the current head revision without duplicate-column failures:
  - `cd Backend && alembic upgrade head`
- verify frontend build still passes:
  - `npm run build`
- verify backend tests still pass:
  - `Backend\\.venv\\Scripts\\python.exe -m pytest -q Backend/app/tests`
- verify SMTP config and transport mode:
  - `cd Backend && python -c "from app.services.email_service import get_email_delivery_summary; print(get_email_delivery_summary())"`
- verify the configured mail transport and sender acceptance without sending a message:
  - `cd Backend && python scripts/send_test_email.py --recipient your-address@example.com --check-only`
- send a real production-style smoke test:
  - `cd Backend && python scripts/send_test_email.py --recipient your-address@example.com`
- generate a Gmail API refresh token when switching away from SMTP:
  - `cd Backend && python scripts/generate_google_oauth_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET`
- verify the load-test tool help output:
  - `python tools/load_test.py --help`
- optional smoke checks after startup:
  - `GET /`
  - `GET /api/docs`
  - `GET /openapi.json`
  - `GET /health`
  - run `tools/load_test.py` in `health` mode first, then in `login` or `mixed` mode with a real account
