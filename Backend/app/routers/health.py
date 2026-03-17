from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine, get_database_pool_snapshot

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    database_ok = True
    database_detail: str | None = None

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        database_ok = False
        database_detail = str(exc)

    payload = {
        "status": "ok" if database_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "ok": database_ok,
            "detail": database_detail,
        },
        "pool": get_database_pool_snapshot(),
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK if database_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )
