# sas-v1

Valid8 Attendance Recognition System (Dockerized full stack).

## Stack
- Backend: FastAPI, SQLAlchemy, Alembic, Celery, Celery Beat, Redis
- Frontend: React + TypeScript + Vite
- Database: PostgreSQL
- Tools: Docker Compose, pgAdmin

## Project Structure
- `Backend/` - FastAPI backend and workers
- `Frontend/` - React frontend
- `Databse/` - project database-related assets
- `docker-compose.yml` - local multi-service orchestration

## Backend Documentation
- Main backend merge guide: `Backend/docs/BACKEND_FACE_GEO_MERGE_GUIDE.md`
- Backend change log: `Backend/docs/BACKEND_CHANGELOG.md`
- Attendance status guide: `Backend/docs/BACKEND_ATTENDANCE_STATUS_GUIDE.md`
- Event time status guide: `Backend/docs/BACKEND_EVENT_TIME_STATUS_GUIDE.md`
- Event auto status guide: `Backend/docs/BACKEND_EVENT_AUTO_STATUS_GUIDE.md`
- Google email delivery guide: `Backend/docs/BACKEND_GOOGLE_EMAIL_DELIVERY_GUIDE.md`

## Quick Start
1. Install Docker Desktop.
2. From project root, run:

```bash
docker compose up --build
```

3. Open:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- pgAdmin: `http://localhost:5050`

## Environment Notes
- Backend mail example values are in `Backend/.env.example`.
- Frontend API URL is configured in `Frontend/.env` (`VITE_API_URL`).
- Compose defaults backend DB/Celery settings for local Docker networking.
- Event auto-status scheduler can be configured with `EVENT_STATUS_SYNC_ENABLED` and `EVENT_STATUS_SYNC_INTERVAL_SECONDS`.
