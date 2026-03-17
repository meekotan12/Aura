from __future__ import annotations

from datetime import timedelta
import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    canonicalize_role_name_for_storage,
    create_access_token,
    validate_user_account_state,
)
from app.models.face_recognition import UserFaceRecognitionProfile
from app.models.school import School, SchoolSetting
from app.models.user import User
from app.services.security_service import create_user_session, is_privileged_user

PENDING_FACE_TOKEN_EXPIRE_MINUTES = 15
BASE_AUTH_ROLE_NAMES = {"admin", "campus_admin", "student"}


def get_user_role_names(user: User) -> list[str]:
    role_names = []
    seen = set()
    for role_assignment in getattr(user, "roles", []):
        role = getattr(role_assignment, "role", None)
        role_name = getattr(role, "name", None)
        if not role_name:
            continue
        canonical_name = canonicalize_role_name_for_storage(role_name)
        if canonical_name not in BASE_AUTH_ROLE_NAMES or canonical_name in seen:
            continue
        seen.add(canonical_name)
        role_names.append(canonical_name)
    return role_names


def validate_login_account_state(db: Session, user: User) -> None:
    validate_user_account_state(db, user)


def get_school_context(db: Session, user: User) -> dict[str, object | None]:
    try:
        school_id = getattr(user, "school_id", None)
        if school_id is None:
            return {}

        school = getattr(user, "school", None)
        if school is None:
            school = db.query(School).filter(School.id == school_id).first()
        if school is None:
            return {}

        settings = getattr(school, "settings", None)
        if settings is None:
            settings = (
                db.query(SchoolSetting)
                .filter(SchoolSetting.school_id == school.id)
                .first()
            )

        return {
            "school_id": school.id,
            "school_name": school.school_name or school.name,
            "school_code": school.school_code,
            "logo_url": school.logo_url,
            "primary_color": school.primary_color
            if getattr(school, "primary_color", None)
            else (settings.primary_color if settings else None),
            "secondary_color": school.secondary_color
            if getattr(school, "secondary_color", None)
            else (settings.secondary_color if settings else None),
            "accent_color": settings.accent_color
            if settings
            else (school.secondary_color or school.primary_color),
        }
    except Exception:
        return {}


def has_face_reference_enrolled(db: Session, user_id: int) -> bool:
    return (
        db.query(UserFaceRecognitionProfile.user_id)
        .filter(UserFaceRecognitionProfile.user_id == user_id)
        .first()
        is not None
    )


def should_recommend_password_change(user: User) -> bool:
    return bool(
        getattr(user, "should_prompt_password_change", False)
        and not getattr(user, "must_change_password", False)
    )


def issue_full_access_token_response(
    *,
    db: Session,
    user: User,
    request: Request | None = None,
) -> dict[str, object | None]:
    role_names = get_user_role_names(user)
    school_context = get_school_context(db, user)
    face_reference_enrolled = (
        getattr(user, "face_profile", None) is not None
        or has_face_reference_enrolled(db, user.id)
    )
    session_id = str(uuid.uuid4())
    token_jti = str(uuid.uuid4())

    token_payload = {
        "sub": user.email,
        "roles": role_names,
        "user_id": user.id,
        "is_admin": "admin" in role_names,
        "must_change_password": user.must_change_password,
        "jti": token_jti,
        "sid": session_id,
        "face_pending": False,
    }
    if school_context.get("school_id") is not None:
        token_payload["school_id"] = school_context["school_id"]

    access_token = create_access_token(
        data=token_payload,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    create_user_session(
        db,
        user=user,
        token_jti=token_jti,
        session_id=session_id,
        expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        request=request,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "email": user.email,
        "roles": role_names,
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": "admin" in role_names,
        "must_change_password": user.must_change_password,
        "password_change_recommended": should_recommend_password_change(user),
        "session_id": session_id,
        "face_verification_required": is_privileged_user(user),
        "face_reference_enrolled": face_reference_enrolled,
        "face_verification_pending": False,
        **school_context,
    }


def issue_pending_face_token_response(
    *,
    db: Session,
    user: User,
) -> dict[str, object | None]:
    role_names = get_user_role_names(user)
    school_context = get_school_context(db, user)
    face_reference_enrolled = (
        getattr(user, "face_profile", None) is not None
        or has_face_reference_enrolled(db, user.id)
    )

    token_payload = {
        "sub": user.email,
        "roles": role_names,
        "user_id": user.id,
        "is_admin": "admin" in role_names,
        "must_change_password": user.must_change_password,
        "face_pending": True,
    }
    if school_context.get("school_id") is not None:
        token_payload["school_id"] = school_context["school_id"]

    access_token = create_access_token(
        data=token_payload,
        expires_delta=timedelta(minutes=PENDING_FACE_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": access_token,
        "token_type": "face_pending",
        "email": user.email,
        "roles": role_names,
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_admin": "admin" in role_names,
        "must_change_password": user.must_change_password,
        "password_change_recommended": should_recommend_password_change(user),
        "session_id": None,
        "face_verification_required": True,
        "face_reference_enrolled": face_reference_enrolled,
        "face_verification_pending": True,
        **school_context,
    }


def issue_login_token_response(
    *,
    db: Session,
    user: User,
    request: Request | None = None,
) -> dict[str, object | None]:
    validate_login_account_state(db, user)
    if is_privileged_user(user):
        return issue_pending_face_token_response(db=db, user=user)
    return issue_full_access_token_response(db=db, user=user, request=request)
