"""Use: Handles user and account management API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs user and account management features.
Role: Router package. It groups user routes by domain while preserving the public router import path.
"""

from fastapi import APIRouter

from app.schemas.user import UserCreateResponse, UserWithRelations
from app.services.email_service import EmailDeliveryError, send_welcome_email
from app.utils.passwords import generate_secure_password

from .accounts import create_user, get_all_users, router as account_router
from .passwords import router as password_router
from .roles import router as role_router
from .students import router as student_router

router = APIRouter(prefix="/users", tags=["users"])
router.post("", response_model=UserCreateResponse, include_in_schema=False)(create_user)
router.get("", response_model=list[UserWithRelations], include_in_schema=False)(get_all_users)
router.include_router(account_router)
router.include_router(student_router)
router.include_router(role_router)
router.include_router(password_router)

__all__ = [
    "EmailDeliveryError",
    "generate_secure_password",
    "router",
    "send_welcome_email",
]
