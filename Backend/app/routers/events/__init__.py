"""Use: Handles event management and event timing actions API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs event management and event timing actions features.
Role: Router package. It groups event routes by domain while preserving the public router import path.
"""

from fastapi import APIRouter

from .attendance_queries import router as attendance_router
from .crud import router as crud_router
from .queries import router as query_router
from .workflow import router as workflow_router

router = APIRouter(prefix="/events", tags=["events"])
router.include_router(crud_router)
router.include_router(query_router)
router.include_router(workflow_router)
router.include_router(attendance_router)

__all__ = ["router"]
