"""Use: Handles attendance check-in, check-out, and reports API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs attendance check-in, check-out, and reports features.
Role: Router package. It groups attendance routes by domain while preserving the public router import path.
"""

from fastapi import APIRouter

from .check_in_out import router as check_in_out_router
from .overrides import router as overrides_router
from .records import router as records_router
from .reports import router as reports_router

router = APIRouter(prefix="/attendance", tags=["attendance"])
router.include_router(reports_router)
router.include_router(check_in_out_router)
router.include_router(overrides_router)
router.include_router(records_router)

__all__ = ["router"]
