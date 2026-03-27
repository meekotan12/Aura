"""Use: Handles school settings and branding API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs school settings and branding features.
Role: Router layer. It receives HTTP requests, checks access rules, and returns API responses.
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.event_defaults import resolve_school_event_default_values
from app.core.security import get_current_admin_or_campus_admin
from app.models.school import School, SchoolAuditLog, SchoolSetting
from app.models.user import User as UserModel
from app.schemas.school_settings import (
    SchoolAuditLogResponse,
    SchoolSettingsResponse,
    SchoolSettingsUpdate,
)

router = APIRouter(prefix="/school-settings", tags=["school-settings"])

LEGACY_USER_IMPORT_DEPRECATION_DETAIL = (
    "Legacy school-scoped import routes under /school-settings/me/users/import* are gone. "
    "Use GET /api/admin/import-students/template, "
    "POST /api/admin/import-students/preview, and "
    "POST /api/admin/import-students instead."
)


def _resolve_current_school(db: Session, current_user: UserModel) -> School:
    user_school_id = getattr(current_user, "school_id", None)
    if user_school_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not assigned to a school.",
        )

    school = db.query(School).filter(School.id == user_school_id).first()
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assigned school was not found.",
        )

    return school


def _get_or_create_school_settings(db: Session, school_id: int) -> SchoolSetting:
    settings = db.query(SchoolSetting).filter(SchoolSetting.school_id == school_id).first()
    if settings:
        return settings

    settings = SchoolSetting(school_id=school_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _build_settings_response(school: School, settings: SchoolSetting) -> SchoolSettingsResponse:
    (
        event_default_early_check_in_minutes,
        event_default_late_threshold_minutes,
        event_default_sign_out_grace_minutes,
    ) = resolve_school_event_default_values(settings)
    return SchoolSettingsResponse(
        school_id=school.id,
        school_name=school.school_name or school.name,
        logo_url=school.logo_url,
        primary_color=school.primary_color or settings.primary_color,
        secondary_color=school.secondary_color or settings.secondary_color,
        accent_color=settings.accent_color,
        event_default_early_check_in_minutes=event_default_early_check_in_minutes,
        event_default_late_threshold_minutes=event_default_late_threshold_minutes,
        event_default_sign_out_grace_minutes=event_default_sign_out_grace_minutes,
    )


def _write_audit_log(
    db: Session,
    school_id: int,
    actor_user_id: Optional[int],
    action: str,
    status_value: str,
    details: Optional[dict] = None,
) -> None:
    log_entry = SchoolAuditLog(
        school_id=school_id,
        actor_user_id=actor_user_id,
        action=action,
        status=status_value,
        details=json.dumps(details or {}, default=str),
    )
    db.add(log_entry)


def _raise_legacy_user_import_deprecated() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=LEGACY_USER_IMPORT_DEPRECATION_DETAIL,
    )


@router.get("/me", response_model=SchoolSettingsResponse)
def get_my_school_settings(
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    school = _resolve_current_school(db, current_user)
    settings = _get_or_create_school_settings(db, school.id)
    return _build_settings_response(school, settings)


@router.put("/me", response_model=SchoolSettingsResponse)
def update_my_school_settings(
    payload: SchoolSettingsUpdate,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    school = _resolve_current_school(db, current_user)
    settings = _get_or_create_school_settings(db, school.id)

    changes = {}

    if payload.school_name is not None:
        new_school_name = payload.school_name.strip()
        current_name = school.school_name or school.name
        if new_school_name != current_name:
            changes["school_name"] = {"from": current_name, "to": new_school_name}
        school.name = new_school_name
        school.school_name = new_school_name

    if payload.logo_url is not None:
        new_logo_url = payload.logo_url.strip() or None
        if new_logo_url != school.logo_url:
            changes["logo_url"] = {"from": school.logo_url, "to": new_logo_url}
        school.logo_url = new_logo_url

    if payload.primary_color is not None:
        current_primary = school.primary_color or settings.primary_color
        if payload.primary_color != current_primary:
            changes["primary_color"] = {"from": current_primary, "to": payload.primary_color}
        school.primary_color = payload.primary_color
        settings.primary_color = payload.primary_color
    if payload.secondary_color is not None:
        current_secondary = school.secondary_color or settings.secondary_color
        if payload.secondary_color != current_secondary:
            changes["secondary_color"] = {"from": current_secondary, "to": payload.secondary_color}
        school.secondary_color = payload.secondary_color
        settings.secondary_color = payload.secondary_color
    if payload.accent_color is not None:
        if payload.accent_color != settings.accent_color:
            changes["accent_color"] = {"from": settings.accent_color, "to": payload.accent_color}
        settings.accent_color = payload.accent_color
    if payload.event_default_early_check_in_minutes is not None:
        if payload.event_default_early_check_in_minutes != settings.event_default_early_check_in_minutes:
            changes["event_default_early_check_in_minutes"] = {
                "from": settings.event_default_early_check_in_minutes,
                "to": payload.event_default_early_check_in_minutes,
            }
        settings.event_default_early_check_in_minutes = payload.event_default_early_check_in_minutes
    if payload.event_default_late_threshold_minutes is not None:
        if payload.event_default_late_threshold_minutes != settings.event_default_late_threshold_minutes:
            changes["event_default_late_threshold_minutes"] = {
                "from": settings.event_default_late_threshold_minutes,
                "to": payload.event_default_late_threshold_minutes,
            }
        settings.event_default_late_threshold_minutes = payload.event_default_late_threshold_minutes
    if payload.event_default_sign_out_grace_minutes is not None:
        if payload.event_default_sign_out_grace_minutes != settings.event_default_sign_out_grace_minutes:
            changes["event_default_sign_out_grace_minutes"] = {
                "from": settings.event_default_sign_out_grace_minutes,
                "to": payload.event_default_sign_out_grace_minutes,
            }
        settings.event_default_sign_out_grace_minutes = payload.event_default_sign_out_grace_minutes

    settings.updated_by_user_id = current_user.id

    _write_audit_log(
        db=db,
        school_id=school.id,
        actor_user_id=current_user.id,
        action="branding_update",
        status_value="success",
        details={"changes": changes, "changed": bool(changes)},
    )

    db.commit()
    db.refresh(school)
    db.refresh(settings)

    return _build_settings_response(school, settings)


@router.get("/me/audit-logs", response_model=List[SchoolAuditLogResponse])
def list_school_audit_logs(
    limit: int = 50,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    school = _resolve_current_school(db, current_user)
    logs = (
        db.query(SchoolAuditLog)
        .filter(SchoolAuditLog.school_id == school.id)
        .order_by(SchoolAuditLog.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return logs


@router.get("/me/users/import-template", deprecated=True)
def download_user_import_template(
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
):
    _ = current_user
    _raise_legacy_user_import_deprecated()


@router.post("/me/users/import", deprecated=True)
def import_users_from_excel(
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
):
    _ = current_user
    _raise_legacy_user_import_deprecated()

