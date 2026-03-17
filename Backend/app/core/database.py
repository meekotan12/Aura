from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import get_settings
from app.models.base import Base

settings = get_settings()
SQL_ECHO = os.getenv("SQL_ECHO", "false").strip().lower() in {"1", "true", "yes", "on"}

if SQL_ECHO:
    logging.basicConfig()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
else:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

engine = create_engine(
    settings.database_url,
    echo=SQL_ECHO,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_use_lifo=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


def get_database_pool_snapshot() -> dict[str, int | str | float | None]:
    pool = engine.pool
    snapshot: dict[str, int | str | float | None] = {
        "pool_class": type(pool).__name__,
    }

    if isinstance(pool, QueuePool):
        checked_out = pool.checkedout()
        configured_pool_size = pool.size()
        overflow_connections = max(pool.overflow(), 0)
        total_capacity = configured_pool_size + settings.db_max_overflow
        available_slots = max(total_capacity - checked_out, 0)
        utilization_ratio = (
            round(checked_out / total_capacity, 3) if total_capacity > 0 else 0.0
        )
        snapshot.update(
            {
                "configured_pool_size": configured_pool_size,
                "max_overflow": settings.db_max_overflow,
                "checked_in_connections": pool.checkedin(),
                "checked_out_connections": checked_out,
                "overflow_connections": overflow_connections,
                "total_capacity": total_capacity,
                "available_slots": available_slots,
                "pool_timeout_seconds": settings.db_pool_timeout_seconds,
                "pool_recycle_seconds": settings.db_pool_recycle_seconds,
                "utilization_ratio": utilization_ratio,
            }
        )
        return snapshot

    snapshot["status"] = "Pool diagnostics are only available for QueuePool-based engines."
    return snapshot

__all__ = ["Base", "SessionLocal", "engine", "get_database_pool_snapshot"]
