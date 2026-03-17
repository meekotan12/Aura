from __future__ import annotations

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.event_defaults import resolve_school_event_default_values
from app.core.security import (
    get_current_admin,
    get_current_application_user,
    get_current_school_it,
    get_role_lookup_names,
    has_any_role,
)
from app.core.dependencies import get_db
from app.models.role import Role
from app.models.school import School, SchoolAuditLog, SchoolSetting
from app.models.user import User, UserRole
from app.schemas.school import (
    AdminSchoolItCreateForm,
    AdminSchoolItCreateResponse,
    SchoolBrandingResponse,
    SchoolCreateForm,
    SchoolITAccountResponse,
    SchoolStatusUpdateForm,
    SchoolSummaryResponse,
    SchoolUpdateForm,
)
from app.services.email_service import EmailDeliveryError, send_welcome_email
from app.services.password_change_policy import (
    must_change_password_for_new_account,
    must_change_password_for_temporary_reset,
    should_prompt_password_change_for_new_account,
    should_prompt_password_change_for_temporary_reset,
)
from app.services.logo_storage_service import delete_managed_school_logo, store_school_logo
from app.utils.passwords import generate_secure_password

router = APIRouter(prefix="/api/school", tags=["school"])


def _normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _write_audit(
    db: Session,
    *,
    school_id: int,
    actor_user_id: Optional[int],
    action: str,
    status_value: str,
    details: dict,
) -> None:
    db.add(
        SchoolAuditLog(
            school_id=school_id,
            actor_user_id=actor_user_id,
            action=action,
            status=status_value,
            details=json.dumps(details, default=str),
        )
    )


def _school_to_response(school: School) -> SchoolBrandingResponse:
    school_settings = getattr(school, "settings", None)
    (
        event_default_early_check_in_minutes,
        event_default_late_threshold_minutes,
        event_default_sign_out_grace_minutes,
    ) = resolve_school_event_default_values(school_settings)
    return SchoolBrandingResponse(
        school_id=school.id,
        school_name=school.school_name or school.name,
        school_code=school.school_code,
        logo_url=school.logo_url,
        primary_color=school.primary_color,
        secondary_color=school.secondary_color,
        event_default_early_check_in_minutes=event_default_early_check_in_minutes,
        event_default_late_threshold_minutes=event_default_late_threshold_minutes,
        event_default_sign_out_grace_minutes=event_default_sign_out_grace_minutes,
        subscription_status=school.subscription_status,
        active_status=school.active_status,
        created_at=school.created_at,
        updated_at=school.updated_at,
    )


def _sync_school_settings(db: Session, school: School, updated_by_user_id: int) -> None:
    settings = db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    if settings is None:
        settings = SchoolSetting(school_id=school.id)
        db.add(settings)

    settings.primary_color = school.primary_color
    settings.secondary_color = school.secondary_color or "#2C5F9E"
    settings.accent_color = school.secondary_color or school.primary_color
    settings.updated_by_user_id = updated_by_user_id
    school.settings = settings


def _ensure_unique_school(
    db: Session,
    *,
    school_name: str,
    school_code: Optional[str],
    exclude_school_id: Optional[int] = None,
) -> None:
    duplicate_name_query = db.query(School).filter(func.lower(School.school_name) == school_name.lower())
    if exclude_school_id is not None:
        duplicate_name_query = duplicate_name_query.filter(School.id != exclude_school_id)
    if duplicate_name_query.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A school with this name already exists.",
        )

    if school_code:
        duplicate_code_query = db.query(School).filter(func.lower(School.school_code) == school_code.lower())
        if exclude_school_id is not None:
            duplicate_code_query = duplicate_code_query.filter(School.id != exclude_school_id)
        if duplicate_code_query.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="School code is already in use.",
            )


def _get_school_it_role_or_500(db: Session) -> Role:
    for role_name in get_role_lookup_names("campus_admin"):
        role = db.query(Role).filter(Role.name == role_name).first()
        if role is not None:
            return role
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Role configuration error: campus_admin role not found.",
    )


def _get_school_it_users_for_school(db: Session, school_id: int) -> list[User]:
    return (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.school_id == school_id,
            Role.name.in_(get_role_lookup_names("campus_admin")),
        )
        .distinct()
        .order_by(User.id.asc())
        .all()
    )


def _sync_school_it_users_for_school(
    db: Session,
    *,
    school_id: int,
    is_active: bool,
) -> list[User]:
    school_it_users = _get_school_it_users_for_school(db, school_id)
    for school_it_user in school_it_users:
        school_it_user.is_active = is_active
    return school_it_users


def _serialize_school_it_users(school_it_users: list[User]) -> list[dict[str, object]]:
    return [
        {
            "user_id": school_it_user.id,
            "email": school_it_user.email,
            "is_active": school_it_user.is_active,
        }
        for school_it_user in school_it_users
    ]


def _get_school_for_current_user_or_404(db: Session, current_user: User) -> School:
    school_id = getattr(current_user, "school_id", None)
    if school_id is None:
        raise HTTPException(status_code=404, detail="No school assigned to user.")

    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")
    return school


@router.post("/create", response_model=SchoolBrandingResponse)
async def create_school(
    school_name: str = Form(...),
    primary_color: str = Form(...),
    secondary_color: Optional[str] = Form(default=None),
    school_code: Optional[str] = Form(default=None),
    logo: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    payload = SchoolCreateForm(
        school_name=school_name,
        primary_color=primary_color,
        secondary_color=_normalize_optional(secondary_color),
        school_code=_normalize_optional(school_code),
    )
    _ensure_unique_school(db, school_name=payload.school_name, school_code=payload.school_code)

    logo_url = None
    if logo is not None:
        logo_url = await store_school_logo(logo)

    school = School(
        name=payload.school_name,
        school_name=payload.school_name,
        school_code=payload.school_code,
        address=f"{payload.school_name} Address",
        logo_url=logo_url,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color,
        subscription_status="trial",
        active_status=True,
        subscription_plan="free",
        subscription_start=date.today(),
    )
    db.add(school)
    db.flush()

    _sync_school_settings(db, school, current_user.id)
    _write_audit(
        db,
        school_id=school.id,
        actor_user_id=current_user.id,
        action="school_create",
        status_value="success",
        details={"school_name": payload.school_name, "school_code": payload.school_code},
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if logo_url:
            delete_managed_school_logo(logo_url)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="School code is already in use.",
        ) from exc

    db.refresh(school)
    return _school_to_response(school)


@router.post("/admin/create-school-it", response_model=AdminSchoolItCreateResponse)
async def admin_create_school_with_school_it(
    school_name: str = Form(...),
    primary_color: str = Form(...),
    secondary_color: Optional[str] = Form(default=None),
    school_code: Optional[str] = Form(default=None),
    school_it_email: str = Form(...),
    school_it_first_name: str = Form(...),
    school_it_middle_name: Optional[str] = Form(default=None),
    school_it_last_name: str = Form(...),
    school_it_password: Optional[str] = Form(default=None),
    logo: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    payload = AdminSchoolItCreateForm(
        school_name=school_name,
        primary_color=primary_color,
        secondary_color=_normalize_optional(secondary_color),
        school_code=_normalize_optional(school_code),
        school_it_email=school_it_email.strip().lower(),
        school_it_first_name=school_it_first_name,
        school_it_middle_name=_normalize_optional(school_it_middle_name),
        school_it_last_name=school_it_last_name,
        school_it_password=_normalize_optional(school_it_password),
    )

    _ensure_unique_school(db, school_name=payload.school_name, school_code=payload.school_code)

    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == payload.school_it_email.lower())
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campus Admin email is already registered.",
        )

    school_it_role = _get_school_it_role_or_500(db)
    generated_temporary_password = None
    issued_password = payload.school_it_password
    if issued_password is None:
        generated_temporary_password = generate_secure_password(min_length=10, max_length=14)
        issued_password = generated_temporary_password

    logo_url = None
    if logo is not None:
        logo_url = await store_school_logo(logo)

    school = School(
        name=payload.school_name,
        school_name=payload.school_name,
        school_code=payload.school_code,
        address=f"{payload.school_name} Address",
        logo_url=logo_url,
        primary_color=payload.primary_color,
        secondary_color=payload.secondary_color,
        subscription_status="trial",
        active_status=True,
        subscription_plan="free",
        subscription_start=date.today(),
    )
    db.add(school)
    db.flush()

    school_it_user = User(
        email=payload.school_it_email,
        school_id=school.id,
        first_name=payload.school_it_first_name,
        middle_name=payload.school_it_middle_name,
        last_name=payload.school_it_last_name,
        is_active=True,
        must_change_password=must_change_password_for_new_account(),
        should_prompt_password_change=should_prompt_password_change_for_new_account(),
    )
    school_it_user.set_password(issued_password)
    db.add(school_it_user)
    db.flush()
    db.add(UserRole(user_id=school_it_user.id, role_id=school_it_role.id))

    _sync_school_settings(db, school, current_user.id)
    _write_audit(
        db,
        school_id=school.id,
        actor_user_id=current_user.id,
        action="school_create_with_school_it",
        status_value="success",
        details={
            "school_name": payload.school_name,
            "school_code": payload.school_code,
            "school_it_user_id": school_it_user.id,
            "school_it_email": school_it_user.email,
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if logo_url:
            delete_managed_school_logo(logo_url)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to create school and Campus Admin due to uniqueness conflict.",
        ) from exc

    try:
        send_welcome_email(
            recipient_email=school_it_user.email,
            temporary_password=issued_password,
            first_name=school_it_user.first_name,
            system_name=school.school_name or school.name,
            password_is_temporary=generated_temporary_password is not None,
        )
    except EmailDeliveryError:
        _write_audit(
            db,
            school_id=school.id,
            actor_user_id=current_user.id,
            action="school_it_welcome_email",
            status_value="failed",
            details={
                "school_it_user_id": school_it_user.id,
                "school_it_email": school_it_user.email,
            },
        )
        db.commit()

    db.refresh(school)
    return AdminSchoolItCreateResponse(
        school=_school_to_response(school),
        school_it_user_id=school_it_user.id,
        school_it_email=school_it_user.email,
        generated_temporary_password=generated_temporary_password,
    )


@router.get("/admin/list", response_model=list[SchoolSummaryResponse])
def admin_list_schools(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    schools = db.query(School).order_by(School.created_at.desc()).all()
    return [
        SchoolSummaryResponse(
            school_id=school.id,
            school_name=school.school_name or school.name,
            school_code=school.school_code,
            subscription_status=school.subscription_status,
            active_status=school.active_status,
            created_at=school.created_at,
            updated_at=school.updated_at,
        )
        for school in schools
    ]


@router.patch("/admin/{school_id}/status", response_model=SchoolBrandingResponse)
def admin_update_school_status(
    school_id: int,
    payload: SchoolStatusUpdateForm,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(status_code=404, detail="School not found.")

    synced_school_it_users: list[User] = []
    if payload.active_status is not None:
        school.active_status = payload.active_status
        synced_school_it_users = _sync_school_it_users_for_school(
            db,
            school_id=school.id,
            is_active=payload.active_status,
        )
    if payload.subscription_status is not None:
        school.subscription_status = payload.subscription_status.strip()

    audit_details = {
        "active_status": school.active_status,
        "subscription_status": school.subscription_status,
    }
    if payload.active_status is not None:
        audit_details["synced_school_it_accounts"] = _serialize_school_it_users(
            synced_school_it_users
        )

    _write_audit(
        db,
        school_id=school.id,
        actor_user_id=current_user.id,
        action="school_status_update",
        status_value="success",
        details=audit_details,
    )
    db.commit()
    db.refresh(school)
    return _school_to_response(school)


@router.get("/admin/school-it-accounts", response_model=list[SchoolITAccountResponse])
def admin_list_school_it_accounts(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    school_it_users = (
        db.query(User, School)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(School, School.id == User.school_id, isouter=True)
        .filter(Role.name.in_(get_role_lookup_names("campus_admin")))
        .order_by(User.created_at.desc())
        .all()
    )

    return [
        SchoolITAccountResponse(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            school_id=user.school_id,
            school_name=(school.school_name if school else None),
            is_active=user.is_active,
        )
        for user, school in school_it_users
    ]


@router.patch("/admin/school-it-accounts/{user_id}/status", response_model=SchoolITAccountResponse)
def admin_update_school_it_status(
    user_id: int,
    is_active: bool = Body(..., embed=True),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    school_it_user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.id == user_id, Role.name.in_(get_role_lookup_names("campus_admin")))
        .first()
    )
    if school_it_user is None:
        raise HTTPException(status_code=404, detail="Campus Admin account not found.")

    school = None
    synced_school_it_users = [school_it_user]
    if school_it_user.school_id is not None:
        school = db.query(School).filter(School.id == school_it_user.school_id).first()
        if school is not None:
            school.active_status = is_active
            synced_school_it_users = _sync_school_it_users_for_school(
                db,
                school_id=school.id,
                is_active=is_active,
            )
        else:
            school_it_user.is_active = is_active
    else:
        school_it_user.is_active = is_active

    if school is not None:
        _write_audit(
            db,
            school_id=school.id,
            actor_user_id=current_user.id,
            action="school_it_status_update",
            status_value="success",
            details={
                "school_it_user_id": school_it_user.id,
                "school_it_email": school_it_user.email,
                "is_active": is_active,
                "school_active_status": school.active_status,
                "synced_school_it_accounts": _serialize_school_it_users(
                    synced_school_it_users
                ),
            },
        )

    db.commit()
    db.refresh(school_it_user)

    return SchoolITAccountResponse(
        user_id=school_it_user.id,
        email=school_it_user.email,
        first_name=school_it_user.first_name,
        last_name=school_it_user.last_name,
        school_id=school_it_user.school_id,
        school_name=(school.school_name if school else None),
        is_active=school_it_user.is_active,
    )


@router.post("/admin/school-it-accounts/{user_id}/reset-password")
def admin_reset_school_it_password(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    school_it_user = (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(User.id == user_id, Role.name.in_(get_role_lookup_names("campus_admin")))
        .first()
    )
    if school_it_user is None:
        raise HTTPException(status_code=404, detail="Campus Admin account not found.")

    temporary_password = generate_secure_password()
    school_it_user.set_password(temporary_password)
    school_it_user.must_change_password = must_change_password_for_temporary_reset()
    school_it_user.should_prompt_password_change = should_prompt_password_change_for_temporary_reset()

    school = None
    if school_it_user.school_id is not None:
        school = db.query(School).filter(School.id == school_it_user.school_id).first()
    if school:
        _write_audit(
            db,
            school_id=school.id,
            actor_user_id=current_user.id,
            action="school_it_password_reset",
            status_value="success",
            details={
                "school_it_user_id": school_it_user.id,
                "school_it_email": school_it_user.email,
            },
        )

    db.commit()
    return {
        "user_id": school_it_user.id,
        "email": school_it_user.email,
        "temporary_password": temporary_password,
        "must_change_password": must_change_password_for_temporary_reset(),
    }


@router.put("/update", response_model=SchoolBrandingResponse)
async def update_school(
    school_name: Optional[str] = Form(default=None),
    primary_color: Optional[str] = Form(default=None),
    secondary_color: Optional[str] = Form(default=None),
    school_code: Optional[str] = Form(default=None),
    event_default_early_check_in_minutes: Optional[int] = Form(default=None),
    event_default_late_threshold_minutes: Optional[int] = Form(default=None),
    event_default_sign_out_grace_minutes: Optional[int] = Form(default=None),
    logo: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_school_it),
    db: Session = Depends(get_db),
):
    school = _get_school_for_current_user_or_404(db, current_user)
    payload = SchoolUpdateForm(
        school_name=_normalize_optional(school_name),
        primary_color=_normalize_optional(primary_color),
        secondary_color=_normalize_optional(secondary_color),
        school_code=_normalize_optional(school_code),
        event_default_early_check_in_minutes=event_default_early_check_in_minutes,
        event_default_late_threshold_minutes=event_default_late_threshold_minutes,
        event_default_sign_out_grace_minutes=event_default_sign_out_grace_minutes,
    )

    proposed_school_name = payload.school_name if payload.school_name is not None else (school.school_name or school.name)
    proposed_school_code = payload.school_code if school_code is not None else school.school_code
    _ensure_unique_school(
        db,
        school_name=proposed_school_name,
        school_code=proposed_school_code,
        exclude_school_id=school.id,
    )

    old_logo_url = school.logo_url
    new_logo_url = old_logo_url
    if logo is not None:
        new_logo_url = await store_school_logo(logo)

    if payload.school_name is not None:
        school.school_name = payload.school_name
        school.name = payload.school_name
    if payload.primary_color is not None:
        school.primary_color = payload.primary_color
    if secondary_color is not None:
        school.secondary_color = payload.secondary_color
    if school_code is not None:
        school.school_code = payload.school_code

    school.logo_url = new_logo_url
    _sync_school_settings(db, school, current_user.id)
    settings = school.settings
    if settings is None:
        settings = db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    if settings is not None:
        if payload.event_default_early_check_in_minutes is not None:
            settings.event_default_early_check_in_minutes = payload.event_default_early_check_in_minutes
        if payload.event_default_late_threshold_minutes is not None:
            settings.event_default_late_threshold_minutes = payload.event_default_late_threshold_minutes
        if payload.event_default_sign_out_grace_minutes is not None:
            settings.event_default_sign_out_grace_minutes = payload.event_default_sign_out_grace_minutes
        school.settings = settings
    _write_audit(
        db,
        school_id=school.id,
        actor_user_id=current_user.id,
        action="school_update",
        status_value="success",
        details={
            "school_name": school.school_name,
            "school_code": school.school_code,
            "logo_updated": bool(logo is not None),
            "event_default_early_check_in_minutes": (
                payload.event_default_early_check_in_minutes
                if payload.event_default_early_check_in_minutes is not None
                else resolve_school_event_default_values(settings)[0] if settings is not None else None
            ),
            "event_default_late_threshold_minutes": (
                payload.event_default_late_threshold_minutes
                if payload.event_default_late_threshold_minutes is not None
                else resolve_school_event_default_values(settings)[1] if settings is not None else None
            ),
            "event_default_sign_out_grace_minutes": (
                payload.event_default_sign_out_grace_minutes
                if payload.event_default_sign_out_grace_minutes is not None
                else resolve_school_event_default_values(settings)[2] if settings is not None else None
            ),
        },
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if logo is not None and new_logo_url != old_logo_url:
            delete_managed_school_logo(new_logo_url)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="School code is already in use.",
        ) from exc

    if logo is not None and old_logo_url and old_logo_url != new_logo_url:
        delete_managed_school_logo(old_logo_url)

    db.refresh(school)
    return _school_to_response(school)


@router.get("/me", response_model=SchoolBrandingResponse)
def get_my_school_branding(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    school = _get_school_for_current_user_or_404(db, current_user)
    if school.settings is None:
        school.settings = db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    return _school_to_response(school)


