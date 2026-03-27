"""Shared helpers for the user router package."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.dependencies import get_db
from app.core.security import (
    canonicalize_role_name_for_storage,
    get_current_admin_or_campus_admin,
    get_current_application_user,
    get_role_lookup_names,
    get_school_id_or_403,
    has_any_role,
    normalize_role_name,
)
from app.models.associations import program_department_association
from app.models.department import Department
from app.models.governance_hierarchy import PermissionCode
from app.models.program import Program
from app.models.role import Role
from app.models.school import School
from app.models.user import StudentProfile, User as UserModel, UserRole
from app.schemas.user import (
    PasswordUpdate,
    StudentAccountCreate,
    StudentProfileBase,
    StudentProfileCreate,
    UserCreate,
    UserCreateResponse,
    UserRoleUpdate,
    UserUpdate,
    UserWithRelations,
)
from app.services import governance_hierarchy_service
from app.services.face_recognition import is_face_scan_bypass_enabled_for_user
from app.services.password_change_policy import (
    must_change_password_for_new_account,
    must_change_password_for_temporary_reset,
    should_prompt_password_change_for_new_account,
    should_prompt_password_change_for_temporary_reset,
)
from app.utils.passwords import generate_secure_password

logger = logging.getLogger(__name__)


def _serialize_user(user: UserModel) -> UserWithRelations:
    return UserWithRelations.model_validate(user, from_attributes=True).model_copy(
        update={"face_scan_bypass_enabled": is_face_scan_bypass_enabled_for_user(user)}
    )


def _serialize_users(users: list[UserModel]) -> list[UserWithRelations]:
    return [_serialize_user(user) for user in users]


def has_required_roles(user: UserModel, required_roles: List[str]) -> bool:
    return has_any_role(user, required_roles)


def _is_admin(user: UserModel) -> bool:
    return has_required_roles(user, ["admin"])


def _is_school_it(user: UserModel) -> bool:
    return has_required_roles(user, ["campus_admin"])


def _can_manage_student_profiles(db: Session, current_user: UserModel) -> bool:
    if has_required_roles(current_user, ["admin", "campus_admin"]):
        return True

    return governance_hierarchy_service.user_has_governance_permission(
        db,
        current_user=current_user,
        permission_code=PermissionCode.MANAGE_STUDENTS,
    )


def _target_has_admin_or_school_it(user: UserModel) -> bool:
    target_roles = {
        normalize_role_name(role.role.name)
        for role in user.roles
        if getattr(role, "role", None) and getattr(role.role, "name", None)
    }
    return "admin" in target_roles or "campus-admin" in target_roles


def _assert_school_it_assignable_roles(current_user: UserModel, role_names: List[str]) -> None:
    if not _is_school_it(current_user) or _is_admin(current_user):
        return

    allowed_roles = {"student"}
    normalized_requested = {normalize_role_name(name) for name in role_names}
    disallowed = sorted(normalized_requested - allowed_roles)
    if disallowed:
        raise HTTPException(
            status_code=403,
            detail=(
                "Campus Admin can only assign the student role from user management. "
                "Use Manage SSG for officer assignments. "
                f"Disallowed roles: {', '.join(disallowed)}"
            ),
        )


def _query_user_in_school(db: Session, user_id: int, school_id: int) -> UserModel | None:
    return (
        _with_user_relations(db.query(UserModel))
        .filter(UserModel.id == user_id, UserModel.school_id == school_id)
        .first()
    )


def _get_role_by_name_or_alias(db: Session, role_name: str) -> Role | None:
    for candidate in get_role_lookup_names(role_name):
        role = db.query(Role).filter(Role.name == candidate).first()
        if role is not None:
            return role
    return None


def _get_or_create_role_by_name(db: Session, role_name: str) -> Role:
    role = _get_role_by_name_or_alias(db, role_name)
    if role is not None:
        return role

    role = Role(name=canonicalize_role_name_for_storage(role_name))
    db.add(role)
    db.flush()
    return role


def _is_platform_admin(user: UserModel) -> bool:
    return _is_admin(user) and getattr(user, "school_id", None) is None


def _actor_school_scope_id(actor: UserModel) -> int | None:
    if _is_platform_admin(actor):
        return None
    return get_school_id_or_403(actor)


def _apply_user_scope(query, actor: UserModel):
    actor_school_id = _actor_school_scope_id(actor)
    if actor_school_id is None:
        return query
    return query.filter(UserModel.school_id == actor_school_id)


def _with_user_relations(query):
    return query.options(
        selectinload(UserModel.roles).joinedload(UserRole.role),
        joinedload(UserModel.student_profile),
    )


def _query_user_for_actor(db: Session, user_id: int, actor: UserModel) -> UserModel | None:
    actor_school_id = _actor_school_scope_id(actor)
    if actor_school_id is None:
        return _with_user_relations(db.query(UserModel)).filter(UserModel.id == user_id).first()
    return _query_user_in_school(db, user_id, actor_school_id)


def _get_department_and_program_for_school_or_400(
    db: Session,
    *,
    school_id: int,
    department_id: int,
    program_id: int,
) -> tuple[Department, Program]:
    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.school_id == school_id,
        )
        .first()
    )
    program = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.school_id == school_id,
        )
        .first()
    )

    if not department or not program:
        raise HTTPException(
            status_code=400,
            detail="Invalid department or program ID for this school",
        )

    association_exists = db.execute(
        select(program_department_association).where(
            (program_department_association.c.department_id == department.id)
            & (program_department_association.c.program_id == program.id)
        )
    ).first()

    if not association_exists:
        raise HTTPException(
            status_code=400,
            detail=f"Program '{program.name}' is not offered by department '{department.name}'",
        )

    return department, program


def _assert_email_available_for_school_or_400(
    db: Session,
    *,
    email: str,
    school_id: int,
) -> None:
    existing_user = db.query(UserModel).filter(UserModel.email == email).first()
    if existing_user is None:
        return

    detail = "Email already registered in this school"
    if existing_user.school_id != school_id:
        detail = "Email already registered in another school"
    raise HTTPException(status_code=400, detail=detail)


def _get_school_system_name(db: Session, school_id: int) -> str | None:
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        return None
    return school.school_name or school.name


__all__ = [name for name in globals() if not name.startswith("__")]
