"""Use: Handles authentication, tokens, and role checks.
Where to use: Use this in routers and services when the backend must verify identity or permissions.
Role: Core security layer. It protects access to backend features.
"""

from datetime import datetime, timedelta
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.models.school import School
from app.models.user import User, UserRole
from app.schemas.auth import TokenData
from app.services.security_service import assert_session_valid
from app.utils.passwords import verify_password_bcrypt

settings = get_settings()
SECRET_KEY = settings.secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "read": "Read access",
        "write": "Write access",
    },
)

PASSWORD_CHANGE_ENDPOINT = "/auth/change-password"
PASSWORD_CHANGE_PROMPT_DISMISS_ENDPOINT = "/auth/password-change-prompt/dismiss"
CAMPUS_ADMIN_DB_ROLE_NAME = "campus_admin"
LEGACY_CAMPUS_ADMIN_DB_ROLE_NAME = "school_IT"
EXEMPT_PATH_PREFIXES = {
    PASSWORD_CHANGE_ENDPOINT,
    "/login",
    "/token",
    "/docs",
    "/redoc",
    "/openapi.json",
}
FACE_VERIFICATION_EXEMPT_PATH_PREFIXES = {
    PASSWORD_CHANGE_ENDPOINT,
    PASSWORD_CHANGE_PROMPT_DISMISS_ENDPOINT,
    "/auth/security/face-status",
    "/auth/security/face-liveness",
    "/auth/security/face-reference",
    "/auth/security/face-verify",
}


def normalize_role_name(role_name: str) -> str:
    """Normalize role spellings to a single comparison format."""
    normalized = (role_name or "").strip().lower().replace(" ", "-").replace("_", "-")
    if normalized in {"school-it", "campus-admin"}:
        return "campus-admin"
    return normalized


def canonicalize_role_name_for_storage(role_name: str) -> str:
    """Map accepted role spellings to the canonical database role name."""
    normalized = normalize_role_name(role_name)
    if normalized == "campus-admin":
        return CAMPUS_ADMIN_DB_ROLE_NAME
    return normalized


def get_role_lookup_names(role_name: str) -> tuple[str, ...]:
    """Return database role names that should be treated as equivalent."""
    canonical_name = canonicalize_role_name_for_storage(role_name)
    if canonical_name == CAMPUS_ADMIN_DB_ROLE_NAME:
        return (CAMPUS_ADMIN_DB_ROLE_NAME, LEGACY_CAMPUS_ADMIN_DB_ROLE_NAME)
    return (canonical_name,)


def get_normalized_user_roles(user: User) -> set[str]:
    return {
        normalize_role_name(role.role.name)
        for role in getattr(user, "roles", [])
        if getattr(role, "role", None) and getattr(role.role, "name", None)
    }


def has_any_role(user: User, required_roles: List[str]) -> bool:
    user_roles = get_normalized_user_roles(user)
    required = {normalize_role_name(role_name) for role_name in required_roles}
    return bool(user_roles & required)


def ensure_user_has_any_role(
    user: User,
    required_roles: List[str],
    *,
    detail: str,
) -> User:
    if not has_any_role(user, required_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def validate_user_account_state(db: Session, user: User) -> None:
    if not getattr(user, "is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive. Contact your administrator.",
        )

    role_names = get_normalized_user_roles(user)
    if not role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no assigned role. Contact your administrator.",
        )

    school_id = getattr(user, "school_id", None)
    is_platform_admin = "admin" in role_names and school_id is None
    if is_platform_admin:
        return

    if school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not assigned to a school.",
        )

    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is assigned to a school that does not exist.",
        )

    if not getattr(school, "active_status", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account's school is inactive.",
        )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return verify_password_bcrypt(plain_password, hashed_password)


def _normalize_login_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def _auth_user_query(db: Session, email: str):
    return (
        db.query(User)
        .options(
            joinedload(User.roles).joinedload(UserRole.role),
            joinedload(User.school).joinedload(School.settings),
            joinedload(User.face_profile),
        )
        .filter(User.email == _normalize_login_identifier(email))
    )


def get_user_for_login(db: Session, email: str) -> Optional[User]:
    return _auth_user_query(db, email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_for_login(db, email)

    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token_to_token_data(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
        return TokenData(
            email=email,
            school_id=payload.get("school_id"),
            roles=payload.get("roles"),
            must_change_password=payload.get("must_change_password"),
            jti=payload.get("jti"),
            face_pending=payload.get("face_pending"),
        )
    except JWTError as exc:
        raise credentials_exception from exc


def _raise_password_change_required() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "password_change_required",
            "message": "Password change is required before accessing protected resources.",
            "change_password_endpoint": PASSWORD_CHANGE_ENDPOINT,
        },
    )


def _raise_face_verification_required() -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "face_verification_required",
            "message": "Face verification is required before accessing protected resources.",
            "verify_endpoint": "/auth/security/face-verify",
        },
    )


def _enforce_face_verification_gate(token_data: TokenData, request: Request) -> None:
    if not token_data.face_pending:
        return

    path = request.url.path
    if any(path.startswith(prefix) for prefix in FACE_VERIFICATION_EXEMPT_PATH_PREFIXES):
        return

    _raise_face_verification_required()


def _enforce_password_change_gate(user: User, request: Request) -> None:
    if not user.must_change_password:
        return

    path = request.url.path
    if any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
        return

    _raise_password_change_required()


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token_data = decode_token_to_token_data(token)

    user = (
        db.query(User)
        .options(
            joinedload(User.roles).joinedload(UserRole.role),
            joinedload(User.school),
        )
        .filter(User.email == token_data.email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    validate_user_account_state(db, user)
    if not token_data.face_pending:
        assert_session_valid(db, token_jti=token_data.jti)
    _enforce_face_verification_gate(token_data, request)
    _enforce_password_change_gate(user, request)
    return user


def get_current_user_with_roles(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token_data = decode_token_to_token_data(token)

    user = (
        db.query(User)
        .options(
            joinedload(User.roles).joinedload(UserRole.role),
            joinedload(User.student_profile),
            joinedload(User.school),
        )
        .filter(User.email == token_data.email)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    validate_user_account_state(db, user)
    if not token_data.face_pending:
        assert_session_valid(db, token_jti=token_data.jti)
    _enforce_face_verification_gate(token_data, request)
    _enforce_password_change_gate(user, request)
    return user


def require_current_user_with_roles(
    required_roles: List[str],
    *,
    detail: str,
) -> Callable[..., User]:
    def dependency(
        current_user: User = Depends(get_current_user_with_roles),
    ) -> User:
        return ensure_user_has_any_role(
            current_user,
            required_roles,
            detail=detail,
        )

    dependency.__name__ = (
        "require_"
        + "_or_".join(normalize_role_name(role_name).replace("-", "_") for role_name in required_roles)
    )
    return dependency


def get_school_id_or_403(user: User) -> int:
    school_id = getattr(user, "school_id", None)
    if school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a school",
        )
    return school_id


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    return ensure_user_has_any_role(
        current_user,
        ["admin"],
        detail="Admin privileges required",
    )


def get_current_school_it(current_user: User = Depends(get_current_user_with_roles)) -> User:
    return ensure_user_has_any_role(
        current_user,
        ["campus_admin", "school_IT", "school-it", "school_it"],
        detail="Campus Admin privileges required",
    )


get_current_admin_or_campus_admin = require_current_user_with_roles(
    ["admin", "campus_admin"],
    detail="Insufficient permissions. Requires admin or Campus Admin role",
)

get_current_application_user = require_current_user_with_roles(
    ["admin", "campus_admin", "student", "ssg", "sg", "org"],
    detail=(
        "A valid admin, Campus Admin, student, or governance role is "
        "required for this resource"
    ),
)

get_current_student_user = require_current_user_with_roles(
    ["student"],
    detail="Student role required",
)
