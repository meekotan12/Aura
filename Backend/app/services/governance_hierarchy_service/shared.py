"""Use: Contains the shared backend rules for governance unit hierarchy and membership rules.
Where to use: Use this from the governance service package when governance hierarchy logic is needed.
Role: Shared service layer. It preserves the existing implementation while public modules split by domain.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.event_defaults import resolve_governance_event_default_values
from app.core.security import get_school_id_or_403, has_any_role
from app.models.associations import program_department_association
from app.models.department import Department
from app.models.governance_hierarchy import (
    GovernanceAnnouncement,
    GovernanceAnnouncementStatus,
    GovernanceMember,
    GovernanceMemberPermission,
    GovernancePermission,
    GovernanceStudentNote,
    GovernanceUnit,
    GovernanceUnitPermission,
    GovernanceUnitType,
    PERMISSION_DEFINITIONS,
    PermissionCode,
)
from app.models.program import Program
from app.models.school import SchoolSetting
from app.models.user import StudentProfile, User
from app.schemas.governance_hierarchy import (
    GovernanceAccessResponse,
    GovernanceAccessUnitResponse,
    GovernanceAnnouncementCreate,
    GovernanceDashboardAnnouncementSummaryResponse,
    GovernanceDashboardChildUnitSummaryResponse,
    GovernanceDashboardOverviewResponse,
    GovernanceAnnouncementMonitorResponse,
    GovernanceAnnouncementResponse,
    GovernanceAnnouncementUpdate,
    GovernanceEventDefaultsResponse,
    GovernanceEventDefaultsUpdate,
    GovernanceMemberAssign,
    GovernanceMemberUpdate,
    GovernanceSsgSetupResponse,
    GovernanceStudentNoteResponse,
    GovernanceStudentNoteUpdate,
    GovernanceStudentCandidateResponse,
    GovernanceUnitCreate,
    GovernanceUnitPermissionAssign,
    GovernanceUnitSummaryResponse,
    GovernanceUnitUpdate,
)


CHILD_CREATE_PERMISSION_MAP: dict[GovernanceUnitType, PermissionCode] = {
    GovernanceUnitType.SG: PermissionCode.CREATE_SG,
    GovernanceUnitType.ORG: PermissionCode.CREATE_ORG,
}

CHILD_VIEW_PERMISSION_MAP: dict[GovernanceUnitType, set[PermissionCode]] = {
    GovernanceUnitType.SG: {
        PermissionCode.CREATE_SG,
        PermissionCode.MANAGE_MEMBERS,
        PermissionCode.ASSIGN_PERMISSIONS,
    },
    GovernanceUnitType.ORG: {
        PermissionCode.CREATE_ORG,
        PermissionCode.MANAGE_MEMBERS,
        PermissionCode.ASSIGN_PERMISSIONS,
    },
}

CHILD_DASHBOARD_UNIT_TYPE_MAP: dict[GovernanceUnitType, GovernanceUnitType] = {
    GovernanceUnitType.SSG: GovernanceUnitType.SG,
    GovernanceUnitType.SG: GovernanceUnitType.ORG,
}

UNIT_MEMBER_PERMISSION_WHITELIST: dict[GovernanceUnitType, set[PermissionCode]] = {
    GovernanceUnitType.SSG: {
        PermissionCode.CREATE_SG,
        PermissionCode.MANAGE_STUDENTS,
        PermissionCode.VIEW_STUDENTS,
        PermissionCode.MANAGE_MEMBERS,
        PermissionCode.MANAGE_EVENTS,
        PermissionCode.MANAGE_ATTENDANCE,
        PermissionCode.MANAGE_ANNOUNCEMENTS,
        PermissionCode.ASSIGN_PERMISSIONS,
    },
    GovernanceUnitType.SG: {
        PermissionCode.CREATE_ORG,
        PermissionCode.MANAGE_STUDENTS,
        PermissionCode.VIEW_STUDENTS,
        PermissionCode.MANAGE_MEMBERS,
        PermissionCode.MANAGE_EVENTS,
        PermissionCode.MANAGE_ATTENDANCE,
        PermissionCode.MANAGE_ANNOUNCEMENTS,
        PermissionCode.ASSIGN_PERMISSIONS,
    },
    GovernanceUnitType.ORG: {
        PermissionCode.MANAGE_STUDENTS,
        PermissionCode.VIEW_STUDENTS,
        PermissionCode.MANAGE_MEMBERS,
        PermissionCode.MANAGE_EVENTS,
        PermissionCode.MANAGE_ATTENDANCE,
        PermissionCode.MANAGE_ANNOUNCEMENTS,
        PermissionCode.ASSIGN_PERMISSIONS,
    },
}

DEFAULT_SSG_UNIT_CODE = "SSG"
DEFAULT_SSG_UNIT_NAME = "Supreme Students Government"
DEFAULT_SSG_DESCRIPTION = "Fixed campus-wide student government unit for the school."


def _governance_unit_query(db: Session):
    return db.query(GovernanceUnit).options(
        selectinload(GovernanceUnit.parent_unit),
        selectinload(GovernanceUnit.members)
        .selectinload(GovernanceMember.user)
        .selectinload(User.student_profile),
        selectinload(GovernanceUnit.members)
        .selectinload(GovernanceMember.member_permissions)
        .selectinload(GovernanceMemberPermission.permission),
        selectinload(GovernanceUnit.unit_permissions).selectinload(GovernanceUnitPermission.permission),
    )


def _governance_member_query(db: Session):
    return db.query(GovernanceMember).options(
        selectinload(GovernanceMember.governance_unit),
        selectinload(GovernanceMember.user).selectinload(User.student_profile),
        selectinload(GovernanceMember.member_permissions).selectinload(GovernanceMemberPermission.permission),
    )


def _student_candidate_query(db: Session):
    return db.query(StudentProfile).options(selectinload(StudentProfile.user))


def _is_school_it(current_user: User) -> bool:
    return has_any_role(current_user, ["campus_admin"]) and getattr(current_user, "school_id", None) is not None


def _normalize_unit_code(unit_code: str) -> str:
    normalized = (unit_code or "").strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="unit_code is required")
    return normalized


def _normalize_unit_name(unit_name: str) -> str:
    normalized = (unit_name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="unit_name is required")
    return normalized


def _normalize_unit_description(description: str | None) -> str | None:
    normalized = (description or "").strip()
    return normalized or None


def _normalize_position_title(position_title: str | None) -> str | None:
    normalized = (position_title or "").strip()
    return normalized or None


def _get_payload_fields_set(payload) -> set[str]:
    model_fields_set = getattr(payload, "model_fields_set", None)
    if model_fields_set is not None:
        return set(model_fields_set)
    return set(payload.__fields_set__)


def _prepare_governance_member(governance_member: GovernanceMember) -> GovernanceMember:
    set_committed_value(
        governance_member,
        "member_permissions",
        sorted(
            governance_member.member_permissions,
            key=lambda item: item.permission.permission_code.value,
        ),
    )
    return governance_member


def _prepare_governance_unit(governance_unit: GovernanceUnit) -> GovernanceUnit:
    set_committed_value(
        governance_unit,
        "members",
        sorted(
            [
                _prepare_governance_member(member)
                for member in governance_unit.members
                if member.is_active
            ],
            key=lambda member: (
                (member.position_title or "").lower(),
                (member.user.last_name or "").lower(),
                (member.user.first_name or "").lower(),
                member.id,
            ),
        ),
    )
    set_committed_value(
        governance_unit,
        "unit_permissions",
        sorted(
            governance_unit.unit_permissions,
            key=lambda item: item.permission.permission_code.value,
        ),
    )
    return governance_unit


def _get_active_ssg_unit(db: Session, *, school_id: int) -> GovernanceUnit | None:
    governance_unit = (
        _governance_unit_query(db)
        .filter(
            GovernanceUnit.school_id == school_id,
            GovernanceUnit.unit_type == GovernanceUnitType.SSG,
            GovernanceUnit.is_active.is_(True),
        )
        .first()
    )
    if governance_unit is None:
        return None
    return _prepare_governance_unit(governance_unit)


def _count_imported_students(db: Session, *, school_id: int) -> int:
    return (
        db.query(func.count(StudentProfile.id))
        .filter(StudentProfile.school_id == school_id)
        .scalar()
        or 0
    )


def _get_unit_in_school_or_404(db: Session, *, school_id: int, governance_unit_id: int) -> GovernanceUnit:
    governance_unit = (
        _governance_unit_query(db)
        .filter(
            GovernanceUnit.id == governance_unit_id,
            GovernanceUnit.school_id == school_id,
        )
        .first()
    )
    if governance_unit is None:
        raise HTTPException(status_code=404, detail="Governance unit not found")
    return _prepare_governance_unit(governance_unit)


def _get_school_settings_in_school(db: Session, *, school_id: int) -> SchoolSetting | None:
    return db.query(SchoolSetting).filter(SchoolSetting.school_id == school_id).first()


def _get_member_in_school_or_404(db: Session, *, school_id: int, governance_member_id: int) -> GovernanceMember:
    governance_member = (
        _governance_member_query(db)
        .join(GovernanceUnit, GovernanceMember.governance_unit_id == GovernanceUnit.id)
        .filter(
            GovernanceMember.id == governance_member_id,
            GovernanceUnit.school_id == school_id,
        )
        .first()
    )
    if governance_member is None:
        raise HTTPException(status_code=404, detail="Governance member not found")
    return _prepare_governance_member(governance_member)


def _find_active_member(
    db: Session,
    *,
    governance_unit_id: int,
    user_id: int,
) -> GovernanceMember | None:
    return (
        _governance_member_query(db)
        .filter(
            GovernanceMember.governance_unit_id == governance_unit_id,
            GovernanceMember.user_id == user_id,
            GovernanceMember.is_active.is_(True),
        )
        .first()
    )


def _membership_has_permission(governance_member: GovernanceMember | None, permission_code: PermissionCode) -> bool:
    if governance_member is None or not governance_member.is_active:
        return False
    return any(
        member_permission.permission.permission_code == permission_code
        for member_permission in governance_member.member_permissions
    )


def _membership_has_any_permission(
    governance_member: GovernanceMember | None,
    permission_codes: Iterable[PermissionCode],
) -> bool:
    return any(
        _membership_has_permission(governance_member, permission_code)
        for permission_code in permission_codes
    )


def _unit_matches_student_scope(
    governance_unit: GovernanceUnit,
    *,
    department_id: int | None,
    program_id: int | None,
) -> bool:
    if governance_unit.department_id is not None and governance_unit.department_id != department_id:
        return False
    if governance_unit.program_id is not None and governance_unit.program_id != program_id:
        return False
    return True


def _get_active_governance_memberships(
    db: Session,
    *,
    school_id: int,
    user_id: int,
) -> list[GovernanceMember]:
    memberships = (
        _governance_member_query(db)
        .join(GovernanceUnit, GovernanceMember.governance_unit_id == GovernanceUnit.id)
        .filter(
            GovernanceMember.user_id == user_id,
            GovernanceMember.is_active.is_(True),
            GovernanceUnit.school_id == school_id,
            GovernanceUnit.is_active.is_(True),
        )
        .order_by(GovernanceUnit.unit_type.asc(), GovernanceUnit.unit_name.asc())
        .all()
    )
    return [_prepare_governance_member(membership) for membership in memberships]


def _get_membership_for_unit(
    memberships: Iterable[GovernanceMember],
    *,
    governance_unit_id: int,
) -> GovernanceMember | None:
    for membership in memberships:
        if membership.governance_unit_id == governance_unit_id:
            return membership
    return None


def _get_membership_permission_codes(
    membership: GovernanceMember | None,
) -> set[PermissionCode]:
    if membership is None:
        return set()
    return {
        member_permission.permission.permission_code
        for member_permission in membership.member_permissions
    }


def _get_parent_membership(
    db: Session,
    *,
    current_user: User,
    governance_unit: GovernanceUnit,
) -> GovernanceMember | None:
    if governance_unit.parent_unit_id is None:
        return None

    return _find_active_member(
        db,
        governance_unit_id=governance_unit.parent_unit_id,
        user_id=current_user.id,
    )


def _actor_has_parent_permissions(
    db: Session,
    *,
    current_user: User,
    governance_unit: GovernanceUnit,
    permission_codes: Iterable[PermissionCode],
) -> bool:
    parent_membership = _get_parent_membership(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    )
    if parent_membership is None:
        return False

    return _membership_has_any_permission(parent_membership, permission_codes)


def _can_edit_governance_unit(db: Session, *, current_user: User, governance_unit: GovernanceUnit) -> bool:
    if _is_school_it(current_user):
        return True

    if governance_unit.unit_type == GovernanceUnitType.SSG:
        return False

    required_permission = CHILD_CREATE_PERMISSION_MAP.get(governance_unit.unit_type)
    if required_permission is None:
        return False

    return _actor_has_parent_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={required_permission},
    )


def _can_view_governance_unit(db: Session, *, current_user: User, governance_unit: GovernanceUnit) -> bool:
    if _is_school_it(current_user):
        return True

    if _find_active_member(db, user_id=current_user.id, governance_unit_id=governance_unit.id):
        return True

    return _actor_has_parent_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes=CHILD_VIEW_PERMISSION_MAP.get(governance_unit.unit_type, set()),
    )


def _can_manage_members(db: Session, *, current_user: User, governance_unit: GovernanceUnit) -> bool:
    if _is_school_it(current_user):
        return True

    if governance_unit.unit_type == GovernanceUnitType.SSG:
        return False

    return _actor_has_parent_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.MANAGE_MEMBERS},
    )


def _can_assign_permissions(db: Session, *, current_user: User, governance_unit: GovernanceUnit) -> bool:
    if _is_school_it(current_user):
        return True

    if governance_unit.unit_type == GovernanceUnitType.SSG:
        return False

    return _actor_has_parent_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.ASSIGN_PERMISSIONS},
    )


def _can_manage_event_defaults(
    db: Session,
    *,
    current_user: User,
    governance_unit: GovernanceUnit,
) -> bool:
    if _is_school_it(current_user):
        return True

    membership = _find_active_member(
        db,
        governance_unit_id=governance_unit.id,
        user_id=current_user.id,
    )
    return _membership_has_permission(membership, PermissionCode.MANAGE_EVENTS)


def _build_governance_event_defaults_response(
    *,
    governance_unit: GovernanceUnit,
    school_settings: SchoolSetting | None,
) -> GovernanceEventDefaultsResponse:
    (
        effective_early_check_in_minutes,
        effective_late_threshold_minutes,
        effective_sign_out_grace_minutes,
    ) = resolve_governance_event_default_values(
        school_settings=school_settings,
        governance_unit=governance_unit,
    )
    return GovernanceEventDefaultsResponse(
        governance_unit_id=governance_unit.id,
        school_id=governance_unit.school_id,
        unit_type=governance_unit.unit_type,
        inherits_school_defaults=(
            governance_unit.event_default_early_check_in_minutes is None
            and governance_unit.event_default_late_threshold_minutes is None
            and governance_unit.event_default_sign_out_grace_minutes is None
        ),
        override_early_check_in_minutes=governance_unit.event_default_early_check_in_minutes,
        override_late_threshold_minutes=governance_unit.event_default_late_threshold_minutes,
        override_sign_out_grace_minutes=governance_unit.event_default_sign_out_grace_minutes,
        effective_early_check_in_minutes=effective_early_check_in_minutes,
        effective_late_threshold_minutes=effective_late_threshold_minutes,
        effective_sign_out_grace_minutes=effective_sign_out_grace_minutes,
    )


def _require_unit_membership_permission(
    db: Session,
    *,
    current_user: User,
    governance_unit: GovernanceUnit,
    permission_codes: Iterable[PermissionCode],
    detail: str,
) -> GovernanceMember | None:
    if _is_school_it(current_user):
        return None

    membership = _find_active_member(
        db,
        governance_unit_id=governance_unit.id,
        user_id=current_user.id,
    )
    if membership is None or not _membership_has_any_permission(membership, permission_codes):
        raise HTTPException(status_code=403, detail=detail)
    return membership


def _announcement_query(db: Session):
    return db.query(GovernanceAnnouncement).options(
        selectinload(GovernanceAnnouncement.governance_unit),
        selectinload(GovernanceAnnouncement.created_by_user),
        selectinload(GovernanceAnnouncement.updated_by_user),
    )


def _student_note_query(db: Session):
    return db.query(GovernanceStudentNote).options(
        selectinload(GovernanceStudentNote.governance_unit),
        selectinload(GovernanceStudentNote.student_profile)
        .selectinload(StudentProfile.user),
        selectinload(GovernanceStudentNote.updated_by_user),
    )


def _normalize_announcement_title(title: str) -> str:
    normalized = (title or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Announcement title is required")
    return normalized


def _normalize_announcement_body(body: str) -> str:
    normalized = (body or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Announcement body is required")
    return normalized


def _normalize_governance_tags(tags: Iterable[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen_tags: set[str] = set()
    for raw_tag in tags:
        normalized = (raw_tag or "").strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen_tags:
            continue
        seen_tags.add(lowered)
        normalized_tags.append(normalized[:50])
        if len(normalized_tags) >= 20:
            break
    return normalized_tags


def _get_announcement_in_school_or_404(
    db: Session,
    *,
    school_id: int,
    announcement_id: int,
) -> GovernanceAnnouncement:
    announcement = (
        _announcement_query(db)
        .filter(
            GovernanceAnnouncement.id == announcement_id,
            GovernanceAnnouncement.school_id == school_id,
        )
        .first()
    )
    if announcement is None:
        raise HTTPException(status_code=404, detail="Governance announcement not found")
    return announcement


def _get_note_in_school(
    db: Session,
    *,
    school_id: int,
    governance_unit_id: int,
    student_profile_id: int,
) -> GovernanceStudentNote | None:
    return (
        _student_note_query(db)
        .filter(
            GovernanceStudentNote.school_id == school_id,
            GovernanceStudentNote.governance_unit_id == governance_unit_id,
            GovernanceStudentNote.student_profile_id == student_profile_id,
        )
        .first()
    )


def _get_student_profile_in_unit_scope_or_404(
    db: Session,
    *,
    school_id: int,
    governance_unit: GovernanceUnit,
    student_profile_id: int,
) -> StudentProfile:
    query = (
        db.query(StudentProfile)
        .options(
            selectinload(StudentProfile.user),
            selectinload(StudentProfile.department),
            selectinload(StudentProfile.program),
        )
        .filter(
            StudentProfile.id == student_profile_id,
            StudentProfile.school_id == school_id,
        )
    )
    query = _filter_student_query_to_governance_scope(query, governance_unit=governance_unit)
    student_profile = query.first()
    if student_profile is None:
        raise HTTPException(status_code=404, detail="Student not found in this governance scope")
    return student_profile




def _validate_student_governance_candidate(
    db: Session,
    *,
    school_id: int,
    user_id: int,
    governance_unit: GovernanceUnit | None = None,
) -> User:
    target_user = (
        db.query(User)
        .options(selectinload(User.student_profile))
        .filter(
            User.id == user_id,
            User.school_id == school_id,
            User.is_active.is_(True),
        )
        .first()
    )
    if target_user is None:
        raise HTTPException(status_code=404, detail="Target user not found")
    if target_user.student_profile is None:
        raise HTTPException(
            status_code=400,
            detail="Only imported student users with an existing student profile can be assigned to governance",
        )

    if governance_unit is not None:
        if (
            governance_unit.department_id is not None
            and target_user.student_profile.department_id != governance_unit.department_id
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Only imported students within the {governance_unit.unit_type.value} department scope can be assigned to this unit",
            )
        if (
            governance_unit.program_id is not None
            and target_user.student_profile.program_id != governance_unit.program_id
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Only imported students within the {governance_unit.unit_type.value} program scope can be assigned to this unit",
            )

    return target_user


def _filter_student_query_to_governance_scope(query, *, governance_unit: GovernanceUnit):
    if governance_unit.department_id is not None:
        query = query.filter(StudentProfile.department_id == governance_unit.department_id)
    if governance_unit.program_id is not None:
        query = query.filter(StudentProfile.program_id == governance_unit.program_id)
    return query


def _get_permission_map(
    db: Session,
    *,
    permission_codes: Iterable[PermissionCode],
) -> dict[PermissionCode, GovernancePermission]:
    unique_codes = {permission_code for permission_code in permission_codes}
    if not unique_codes:
        return {}

    permissions = (
        db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code.in_(list(unique_codes)))
        .all()
    )
    permission_map = {permission.permission_code: permission for permission in permissions}
    missing_codes = sorted(code.value for code in unique_codes if code not in permission_map)
    if missing_codes:
        raise HTTPException(
            status_code=404,
            detail=f"Governance permission not found: {', '.join(missing_codes)}",
    )
    return permission_map


def _ensure_permission_codes_allowed_for_unit(
    *,
    unit_type: GovernanceUnitType,
    permission_codes: Iterable[PermissionCode],
    target_label: str,
) -> None:
    requested_codes = {permission_code for permission_code in permission_codes}
    if not requested_codes:
        return

    allowed_codes = UNIT_MEMBER_PERMISSION_WHITELIST.get(unit_type, set())
    invalid_codes = sorted(
        permission_code.value
        for permission_code in requested_codes
        if permission_code not in allowed_codes
    )
    if invalid_codes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Permissions not allowed for {unit_type.value} {target_label}: "
                f"{', '.join(invalid_codes)}"
            ),
        )


def _sync_member_permissions(
    db: Session,
    *,
    governance_member: GovernanceMember,
    permission_codes: Iterable[PermissionCode],
    granted_by_user_id: int,
) -> None:
    ensure_permission_catalog(db)
    requested_codes = {permission_code for permission_code in permission_codes}
    permission_map = _get_permission_map(db, permission_codes=requested_codes)
    existing_by_code = {
        member_permission.permission.permission_code: member_permission
        for member_permission in governance_member.member_permissions
    }

    for permission_code, member_permission in list(existing_by_code.items()):
        if permission_code not in requested_codes:
            db.delete(member_permission)

    for permission_code in requested_codes:
        if permission_code in existing_by_code:
            continue
        db.add(
            GovernanceMemberPermission(
                governance_member_id=governance_member.id,
                permission_id=permission_map[permission_code].id,
                granted_by_user_id=granted_by_user_id,
            )
        )

    db.flush()


def ensure_permission_catalog(db: Session) -> None:
    existing_codes = {
        row.permission_code
        for row in db.query(GovernancePermission).all()
    }

    for permission_code, payload in PERMISSION_DEFINITIONS.items():
        if permission_code in existing_codes:
            continue
        db.add(
            GovernancePermission(
                permission_code=permission_code,
                permission_name=payload["permission_name"],
                description=payload["description"],
            )
        )

    db.flush()


def _assert_program_belongs_to_department(
    db: Session,
    *,
    department_id: int,
    program_id: int,
    detail: str,
) -> None:
    program_department_exists = db.execute(
        program_department_association.select().where(
            (program_department_association.c.department_id == department_id)
            & (program_department_association.c.program_id == program_id)
        )
    ).first()
    if program_department_exists is None:
        raise HTTPException(status_code=400, detail=detail)


def _get_department_in_school_or_400(
    db: Session,
    *,
    school_id: int,
    department_id: int,
) -> Department:
    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.school_id == school_id,
        )
        .first()
    )
    if department is None:
        raise HTTPException(status_code=400, detail="Invalid department_id for this school")
    return department


def _get_program_in_school_or_400(
    db: Session,
    *,
    school_id: int,
    program_id: int,
) -> Program:
    program = (
        db.query(Program)
        .filter(
            Program.id == program_id,
            Program.school_id == school_id,
        )
        .first()
    )
    if program is None:
        raise HTTPException(status_code=400, detail="Invalid program_id for this school")
    return program


def validate_governance_scope(
    db: Session,
    *,
    school_id: int,
    unit_type: GovernanceUnitType,
    parent_unit: GovernanceUnit | None,
    department_id: int | None,
    program_id: int | None,
) -> tuple[int | None, int | None]:
    if department_id is not None:
        _get_department_in_school_or_400(
            db,
            school_id=school_id,
            department_id=department_id,
        )

    if program_id is not None:
        _get_program_in_school_or_400(
            db,
            school_id=school_id,
            program_id=program_id,
        )

    if department_id is not None and program_id is not None:
        _assert_program_belongs_to_department(
            db,
            department_id=department_id,
            program_id=program_id,
            detail="program_id is not linked to department_id",
        )

    if unit_type == GovernanceUnitType.SSG:
        if parent_unit is not None:
            raise HTTPException(status_code=400, detail="SSG units cannot have a parent_unit_id")
        if department_id is not None or program_id is not None:
            raise HTTPException(
                status_code=400,
                detail="SSG units must stay school-wide and cannot be scoped to department_id or program_id",
            )
        return None, None

    if unit_type == GovernanceUnitType.SG:
        if parent_unit is None or parent_unit.unit_type != GovernanceUnitType.SSG:
            raise HTTPException(status_code=400, detail="SG units must belong to an SSG parent unit")
        if department_id is None:
            raise HTTPException(
                status_code=400,
                detail="SG units must include department_id in the current backend structure",
            )
        if program_id is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "SG units must stay department-wide and cannot be scoped to program_id. "
                    "Use program_id for ORG units instead."
                ),
            )
        return department_id, None

    if unit_type == GovernanceUnitType.ORG:
        if parent_unit is None or parent_unit.unit_type != GovernanceUnitType.SG:
            raise HTTPException(status_code=400, detail="ORG units must belong to an SG parent unit")

        normalized_department_id = parent_unit.department_id if parent_unit.department_id is not None else department_id

        if normalized_department_id is None:
            raise HTTPException(
                status_code=400,
                detail="ORG units need a parent SG with a valid department scope",
            )
        if program_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "ORG units must include program_id in the current backend structure. "
                    "ORG represents a program under the SG's department scope."
                ),
            )
        if department_id is not None and parent_unit.department_id is not None and department_id != parent_unit.department_id:
            raise HTTPException(
                status_code=400,
                detail="ORG units must stay within the same department scope as their SG parent",
            )
        if parent_unit.department_id is not None and normalized_department_id != parent_unit.department_id:
            raise HTTPException(
                status_code=400,
                detail="ORG units must stay within the same department scope as their SG parent",
            )

        _assert_program_belongs_to_department(
            db,
            department_id=normalized_department_id,
            program_id=program_id,
            detail="program_id is not linked to the parent SG department scope",
        )

        return normalized_department_id, program_id

    raise HTTPException(status_code=400, detail="Unsupported governance unit type")


def _ensure_can_create_child_unit(
    db: Session,
    *,
    current_user: User,
    unit_type: GovernanceUnitType,
    parent_unit: GovernanceUnit | None,
) -> None:
    if unit_type == GovernanceUnitType.SSG:
        if not _is_school_it(current_user):
            raise HTTPException(status_code=403, detail="Only Campus Admin can create SSG units")
        return

    if parent_unit is None:
        raise HTTPException(status_code=400, detail="parent_unit_id is required for non-SSG units")

    membership = _find_active_member(
        db,
        user_id=current_user.id,
        governance_unit_id=parent_unit.id,
    )

    if unit_type == GovernanceUnitType.SG:
        if parent_unit.unit_type != GovernanceUnitType.SSG:
            raise HTTPException(status_code=400, detail="Only SSG units can create SG child units")
        if not _membership_has_permission(membership, PermissionCode.CREATE_SG):
            raise HTTPException(
                status_code=403,
                detail="Only active SSG members with create_sg can create SG units",
            )
        return

    if unit_type == GovernanceUnitType.ORG:
        if parent_unit.unit_type != GovernanceUnitType.SG:
            raise HTTPException(status_code=400, detail="Only SG units can create ORG child units")
        if not _membership_has_permission(membership, PermissionCode.CREATE_ORG):
            raise HTTPException(
                status_code=403,
                detail="Only active SG members with create_org can create ORG units",
            )
        return

    raise HTTPException(status_code=400, detail="Unsupported governance unit type")


def get_user_governance_permission_codes(
    db: Session,
    *,
    current_user: User,
) -> set[PermissionCode]:
    school_id = get_school_id_or_403(current_user)
    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )

    permission_codes: set[PermissionCode] = set()
    for membership in memberships:
        for member_permission in membership.member_permissions:
            permission_codes.add(member_permission.permission.permission_code)

    return permission_codes


def get_user_governance_unit_types(
    db: Session,
    *,
    current_user: User,
) -> set[GovernanceUnitType]:
    school_id = get_school_id_or_403(current_user)
    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )
    return {membership.governance_unit.unit_type for membership in memberships}


def get_governance_units_with_permission(
    db: Session,
    *,
    current_user: User,
    permission_code: PermissionCode,
    unit_type: GovernanceUnitType | None = None,
) -> list[GovernanceUnit]:
    school_id = get_school_id_or_403(current_user)
    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )

    permitted_units: list[GovernanceUnit] = []
    seen_unit_ids: set[int] = set()
    for membership in memberships:
        governance_unit = membership.governance_unit
        if unit_type is not None and governance_unit.unit_type != unit_type:
            continue
        if not _membership_has_permission(membership, permission_code):
            continue
        if governance_unit.id in seen_unit_ids:
            continue
        seen_unit_ids.add(governance_unit.id)
        permitted_units.append(governance_unit)

    return permitted_units


def governance_unit_matches_event_scope(
    governance_unit: GovernanceUnit,
    *,
    department_ids: Iterable[int] | None,
    program_ids: Iterable[int] | None,
) -> bool:
    department_scope = {department_id for department_id in department_ids or []}
    program_scope = {program_id for program_id in program_ids or []}

    if governance_unit.unit_type == GovernanceUnitType.SSG:
        return not department_scope and not program_scope

    if governance_unit.unit_type == GovernanceUnitType.SG:
        if governance_unit.department_id is None:
            return False
        return department_scope == {governance_unit.department_id} and not program_scope

    if governance_unit.unit_type == GovernanceUnitType.ORG:
        if governance_unit.program_id is None:
            return False
        if program_scope != {governance_unit.program_id}:
            return False
        if not department_scope:
            return True
        return governance_unit.department_id is not None and department_scope == {governance_unit.department_id}

    return False


def governance_units_match_student_scope(
    governance_units: Iterable[GovernanceUnit],
    *,
    department_id: int | None,
    program_id: int | None,
) -> bool:
    return any(
        _unit_matches_student_scope(
            governance_unit,
            department_id=department_id,
            program_id=program_id,
        )
        for governance_unit in governance_units
    )


def user_has_governance_permission(
    db: Session,
    *,
    current_user: User,
    permission_code: PermissionCode,
) -> bool:
    return permission_code in get_user_governance_permission_codes(
        db,
        current_user=current_user,
    )


def ensure_governance_permission(
    db: Session,
    *,
    current_user: User,
    permission_code: PermissionCode,
    detail: str | None = None,
) -> None:
    if user_has_governance_permission(
        db,
        current_user=current_user,
        permission_code=permission_code,
    ):
        return

    raise HTTPException(
        status_code=403,
        detail=detail or f"Missing governance permission: {permission_code.value}",
    )


def get_current_governance_access(
    db: Session,
    *,
    current_user: User,
) -> GovernanceAccessResponse:
    school_id = get_school_id_or_403(current_user)
    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )

    aggregated_permission_codes = sorted(
        {
            member_permission.permission.permission_code
            for membership in memberships
            for member_permission in membership.member_permissions
        },
        key=lambda code: code.value,
    )

    units = [
        GovernanceAccessUnitResponse(
            governance_unit_id=membership.governance_unit.id,
            unit_code=membership.governance_unit.unit_code,
            unit_name=membership.governance_unit.unit_name,
            unit_type=membership.governance_unit.unit_type,
            permission_codes=sorted(
                {
                    member_permission.permission.permission_code
                    for member_permission in membership.member_permissions
                },
                key=lambda code: code.value,
            ),
        )
        for membership in memberships
    ]

    return GovernanceAccessResponse(
        user_id=current_user.id,
        school_id=school_id,
        permission_codes=aggregated_permission_codes,
        units=units,
    )


def get_or_create_campus_ssg_setup(
    db: Session,
    *,
    current_user: User,
) -> GovernanceSsgSetupResponse:
    school_id = get_school_id_or_403(current_user)
    if not _is_school_it(current_user):
        raise HTTPException(status_code=403, detail="Only Campus Admin can manage the campus SSG")

    ensure_permission_catalog(db)

    governance_unit = _get_active_ssg_unit(db, school_id=school_id)
    if governance_unit is None:
        governance_unit = GovernanceUnit(
            unit_code=DEFAULT_SSG_UNIT_CODE,
            unit_name=DEFAULT_SSG_UNIT_NAME,
            description=DEFAULT_SSG_DESCRIPTION,
            unit_type=GovernanceUnitType.SSG,
            school_id=school_id,
            created_by_user_id=current_user.id,
            is_active=True,
        )
        db.add(governance_unit)
        db.commit()
        governance_unit = _get_unit_in_school_or_404(
            db,
            school_id=school_id,
            governance_unit_id=governance_unit.id,
        )

    return GovernanceSsgSetupResponse(
        unit=governance_unit,
        total_imported_students=_count_imported_students(db, school_id=school_id),
    )


def list_governance_units(
    db: Session,
    *,
    current_user: User,
    unit_type: GovernanceUnitType | None = None,
    parent_unit_id: int | None = None,
    include_inactive: bool = False,
) -> list[GovernanceUnitSummaryResponse]:
    school_id = get_school_id_or_403(current_user)
    ensure_permission_catalog(db)

    query = (
        db.query(
            GovernanceUnit.id,
            GovernanceUnit.unit_code,
            GovernanceUnit.unit_name,
            GovernanceUnit.description,
            GovernanceUnit.unit_type,
            GovernanceUnit.parent_unit_id,
            GovernanceUnit.school_id,
            GovernanceUnit.department_id,
            GovernanceUnit.program_id,
            GovernanceUnit.created_by_user_id,
            GovernanceUnit.is_active,
            GovernanceUnit.created_at,
            GovernanceUnit.updated_at,
            func.count(GovernanceMember.id).label("member_count"),
        )
        .outerjoin(
            GovernanceMember,
            and_(
                GovernanceMember.governance_unit_id == GovernanceUnit.id,
                GovernanceMember.is_active.is_(True),
            ),
        )
        .filter(GovernanceUnit.school_id == school_id)
    )
    if unit_type is not None:
        query = query.filter(GovernanceUnit.unit_type == unit_type)
    if parent_unit_id is not None:
        query = query.filter(GovernanceUnit.parent_unit_id == parent_unit_id)
    if not include_inactive:
        query = query.filter(GovernanceUnit.is_active.is_(True))

    governance_units = [
        GovernanceUnitSummaryResponse(
            id=governance_unit.id,
            unit_code=governance_unit.unit_code,
            unit_name=governance_unit.unit_name,
            description=governance_unit.description,
            unit_type=governance_unit.unit_type,
            parent_unit_id=governance_unit.parent_unit_id,
            school_id=governance_unit.school_id,
            department_id=governance_unit.department_id,
            program_id=governance_unit.program_id,
            created_by_user_id=governance_unit.created_by_user_id,
            is_active=governance_unit.is_active,
            created_at=governance_unit.created_at,
            updated_at=governance_unit.updated_at,
            member_count=governance_unit.member_count or 0,
        )
        for governance_unit in query.group_by(
            GovernanceUnit.id,
            GovernanceUnit.unit_code,
            GovernanceUnit.unit_name,
            GovernanceUnit.description,
            GovernanceUnit.unit_type,
            GovernanceUnit.parent_unit_id,
            GovernanceUnit.school_id,
            GovernanceUnit.department_id,
            GovernanceUnit.program_id,
            GovernanceUnit.created_by_user_id,
            GovernanceUnit.is_active,
            GovernanceUnit.created_at,
            GovernanceUnit.updated_at,
        ).order_by(
            GovernanceUnit.unit_type.asc(),
            GovernanceUnit.unit_name.asc(),
        ).all()
    ]

    if _is_school_it(current_user):
        return governance_units

    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )
    membership_permission_codes_by_unit_id = {
        membership.governance_unit_id: _get_membership_permission_codes(membership)
        for membership in memberships
    }

    return [
        governance_unit
        for governance_unit in governance_units
        if governance_unit.id in membership_permission_codes_by_unit_id
        or (
            governance_unit.parent_unit_id is not None
            and bool(
                membership_permission_codes_by_unit_id.get(governance_unit.parent_unit_id, set())
                & CHILD_VIEW_PERMISSION_MAP.get(governance_unit.unit_type, set())
            )
        )
    ]


def get_governance_unit_details(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
) -> GovernanceUnit:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not _can_view_governance_unit(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=404, detail="Governance unit not found")

    return governance_unit


def get_governance_event_defaults(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
) -> GovernanceEventDefaultsResponse:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not _can_view_governance_unit(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=404, detail="Governance unit not found")

    school_settings = _get_school_settings_in_school(db, school_id=school_id)
    return _build_governance_event_defaults_response(
        governance_unit=governance_unit,
        school_settings=school_settings,
    )


def update_governance_event_defaults(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    payload: GovernanceEventDefaultsUpdate,
) -> GovernanceEventDefaultsResponse:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )
    payload_fields_set = _get_payload_fields_set(payload)

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot update defaults for an inactive governance unit")
    if governance_unit.unit_type == GovernanceUnitType.SSG:
        raise HTTPException(
            status_code=400,
            detail="SSG uses the school event defaults. Update the school settings instead.",
        )
    if governance_unit.unit_type not in {GovernanceUnitType.SG, GovernanceUnitType.ORG}:
        raise HTTPException(status_code=400, detail="Only SG and ORG units can override event defaults")
    if not _can_manage_event_defaults(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to manage event defaults for this governance unit",
        )

    if "early_check_in_minutes" in payload_fields_set:
        governance_unit.event_default_early_check_in_minutes = payload.early_check_in_minutes
    if "late_threshold_minutes" in payload_fields_set:
        governance_unit.event_default_late_threshold_minutes = payload.late_threshold_minutes
    if "sign_out_grace_minutes" in payload_fields_set:
        governance_unit.event_default_sign_out_grace_minutes = payload.sign_out_grace_minutes

    db.commit()

    school_settings = _get_school_settings_in_school(db, school_id=school_id)
    return _build_governance_event_defaults_response(
        governance_unit=_get_unit_in_school_or_404(
            db,
            school_id=school_id,
            governance_unit_id=governance_unit.id,
        ),
        school_settings=school_settings,
    )


def create_governance_unit(
    db: Session,
    *,
    current_user: User,
    payload: GovernanceUnitCreate,
) -> GovernanceUnit:
    school_id = get_school_id_or_403(current_user)
    ensure_permission_catalog(db)

    unit_code = _normalize_unit_code(payload.unit_code)
    unit_name = _normalize_unit_name(payload.unit_name)
    description = _normalize_unit_description(payload.description)
    parent_unit = None
    if payload.parent_unit_id is not None:
        parent_unit = _get_unit_in_school_or_404(
            db,
            school_id=school_id,
            governance_unit_id=payload.parent_unit_id,
        )
        if not parent_unit.is_active:
            raise HTTPException(status_code=400, detail="Cannot create a child unit under an inactive parent")

    _ensure_can_create_child_unit(
        db,
        current_user=current_user,
        unit_type=payload.unit_type,
        parent_unit=parent_unit,
    )

    if payload.unit_type == GovernanceUnitType.SSG:
        existing_ssg = (
            db.query(GovernanceUnit.id)
            .filter(
                GovernanceUnit.school_id == school_id,
                GovernanceUnit.unit_type == GovernanceUnitType.SSG,
            )
            .first()
        )
        if existing_ssg is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one SSG unit is allowed per school. Edit the existing SSG instead.",
            )

    department_id, program_id = validate_governance_scope(
        db,
        school_id=school_id,
        unit_type=payload.unit_type,
        parent_unit=parent_unit,
        department_id=payload.department_id,
        program_id=payload.program_id,
    )

    if payload.unit_type == GovernanceUnitType.SG:
        existing_sg = (
            db.query(GovernanceUnit.id)
            .filter(
                GovernanceUnit.school_id == school_id,
                GovernanceUnit.unit_type == GovernanceUnitType.SG,
                GovernanceUnit.department_id == department_id,
                GovernanceUnit.is_active.is_(True),
            )
            .first()
        )
        if existing_sg is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one SG unit is allowed per department. Edit the existing SG instead.",
            )

    if payload.unit_type == GovernanceUnitType.ORG:
        existing_org = (
            db.query(GovernanceUnit.id)
            .filter(
                GovernanceUnit.school_id == school_id,
                GovernanceUnit.unit_type == GovernanceUnitType.ORG,
                GovernanceUnit.program_id == program_id,
                GovernanceUnit.is_active.is_(True),
            )
            .first()
        )
        if existing_org is not None:
            raise HTTPException(
                status_code=400,
                detail="Only one ORG unit is allowed per program. Edit the existing ORG instead.",
            )

    existing_unit = (
        db.query(GovernanceUnit.id)
        .filter(
            GovernanceUnit.school_id == school_id,
            func.lower(GovernanceUnit.unit_code) == unit_code.lower(),
        )
        .first()
    )
    if existing_unit is not None:
        raise HTTPException(status_code=400, detail=f"Governance unit code '{unit_code}' already exists")

    governance_unit = GovernanceUnit(
        unit_code=unit_code,
        unit_name=unit_name,
        description=description,
        unit_type=payload.unit_type,
        parent_unit_id=parent_unit.id if parent_unit is not None else None,
        school_id=school_id,
        department_id=department_id,
        program_id=program_id,
        created_by_user_id=current_user.id,
        is_active=True,
    )
    db.add(governance_unit)
    db.commit()

    return get_governance_unit_details(
        db,
        current_user=current_user,
        governance_unit_id=governance_unit.id,
    )


def update_governance_unit(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    payload: GovernanceUnitUpdate,
) -> GovernanceUnit:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )
    payload_fields_set = _get_payload_fields_set(payload)

    if governance_unit.unit_type == GovernanceUnitType.SSG and not _is_school_it(current_user):
        raise HTTPException(status_code=403, detail="Only Campus Admin can edit the SSG unit")
    if governance_unit.unit_type != GovernanceUnitType.SSG and not _can_edit_governance_unit(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only authorized "
                f"{governance_unit.parent_unit.unit_type.value if governance_unit.parent_unit is not None else 'parent'} "
                f"officers can edit this {governance_unit.unit_type.value} unit"
            ),
        )

    if "unit_code" in payload_fields_set and payload.unit_code is not None:
        normalized_unit_code = _normalize_unit_code(payload.unit_code)
        existing_unit = (
            db.query(GovernanceUnit.id)
            .filter(
                GovernanceUnit.school_id == school_id,
                GovernanceUnit.id != governance_unit.id,
                func.lower(GovernanceUnit.unit_code) == normalized_unit_code.lower(),
            )
            .first()
        )
        if existing_unit is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Governance unit code '{normalized_unit_code}' already exists",
            )
        governance_unit.unit_code = normalized_unit_code

    if "unit_name" in payload_fields_set and payload.unit_name is not None:
        governance_unit.unit_name = _normalize_unit_name(payload.unit_name)

    if "description" in payload_fields_set:
        governance_unit.description = _normalize_unit_description(payload.description)

    db.commit()

    return get_governance_unit_details(
        db,
        current_user=current_user,
        governance_unit_id=governance_unit.id,
    )


def search_governance_student_candidates(
    db: Session,
    *,
    current_user: User,
    search_term: str | None = None,
    governance_unit_id: int | None = None,
    limit: int = 20,
) -> list[GovernanceStudentCandidateResponse]:
    school_id = get_school_id_or_403(current_user)
    governance_unit = None

    active_membership_user_ids: set[int] = set()
    if governance_unit_id is not None:
        governance_unit = _get_unit_in_school_or_404(
            db,
            school_id=school_id,
            governance_unit_id=governance_unit_id,
        )
        if governance_unit.unit_type == GovernanceUnitType.SSG:
            if not _is_school_it(current_user):
                raise HTTPException(status_code=403, detail="Only Campus Admin can search SSG candidates")
        elif not _can_manage_members(db, current_user=current_user, governance_unit=governance_unit):
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to search governance member candidates",
            )
        active_membership_user_ids = {member.user_id for member in governance_unit.members if member.is_active}
    elif not _is_school_it(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only Campus Admin can search governance students without a target unit",
        )

    query = _student_candidate_query(db).filter(StudentProfile.school_id == school_id)
    if governance_unit is not None:
        query = _filter_student_query_to_governance_scope(query, governance_unit=governance_unit)

    normalized_search_term = (search_term or "").strip()
    if normalized_search_term:
        like_value = f"%{normalized_search_term}%"
        query = query.join(User, StudentProfile.user_id == User.id).filter(
            or_(
                StudentProfile.student_id.ilike(like_value),
                User.first_name.ilike(like_value),
                User.middle_name.ilike(like_value),
                User.last_name.ilike(like_value),
                User.email.ilike(like_value),
            )
        )
    else:
        query = query.join(User, StudentProfile.user_id == User.id)

    if active_membership_user_ids:
        query = query.filter(~StudentProfile.user_id.in_(list(active_membership_user_ids)))

    student_profiles = (
        query.filter(User.is_active.is_(True))
        .order_by(
            StudentProfile.student_id.asc(),
            User.last_name.asc(),
            User.first_name.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        GovernanceStudentCandidateResponse(
            user=student_profile.user,
            student_profile=student_profile,
            is_current_governance_member=student_profile.user_id in active_membership_user_ids,
        )
        for student_profile in student_profiles
    ]


def assign_governance_member(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    payload: GovernanceMemberAssign,
) -> GovernanceMember:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot assign members to an inactive governance unit")

    if not _can_manage_members(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=403, detail="You do not have permission to assign governance members")
    if payload.permission_codes and not _can_assign_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    ):
        raise HTTPException(status_code=403, detail="You do not have permission to assign governance permissions")

    _ensure_permission_codes_allowed_for_unit(
        unit_type=governance_unit.unit_type,
        permission_codes=payload.permission_codes,
        target_label="members",
    )

    target_user = _validate_student_governance_candidate(
        db,
        school_id=school_id,
        user_id=payload.user_id,
        governance_unit=governance_unit,
    )

    normalized_position_title = _normalize_position_title(payload.position_title)
    if normalized_position_title is None:
        raise HTTPException(
            status_code=400,
            detail=f"position_title is required for {governance_unit.unit_type.value} members",
        )

    governance_member = (
        _governance_member_query(db)
        .filter(
            GovernanceMember.governance_unit_id == governance_unit_id,
            GovernanceMember.user_id == payload.user_id,
        )
        .first()
    )

    if governance_member is None:
        governance_member = GovernanceMember(
            governance_unit_id=governance_unit_id,
            user_id=payload.user_id,
        )
        db.add(governance_member)
        db.flush()

    governance_member.position_title = normalized_position_title
    governance_member.assigned_by_user_id = current_user.id
    governance_member.is_active = True
    db.flush()

    _sync_member_permissions(
        db,
        governance_member=governance_member,
        permission_codes=payload.permission_codes,
        granted_by_user_id=current_user.id,
    )

    db.commit()

    return _get_member_in_school_or_404(
        db,
        school_id=school_id,
        governance_member_id=governance_member.id,
    )


def update_governance_member(
    db: Session,
    *,
    current_user: User,
    governance_member_id: int,
    payload: GovernanceMemberUpdate,
) -> GovernanceMember:
    school_id = get_school_id_or_403(current_user)
    governance_member = _get_member_in_school_or_404(
        db,
        school_id=school_id,
        governance_member_id=governance_member_id,
    )
    governance_unit = governance_member.governance_unit
    payload_fields_set = _get_payload_fields_set(payload)

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot edit members under an inactive governance unit")

    member_fields_requested = any(field in payload_fields_set for field in {"user_id", "position_title"})
    permission_fields_requested = "permission_codes" in payload_fields_set

    if member_fields_requested and not _can_manage_members(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    ):
        raise HTTPException(status_code=403, detail="You do not have permission to edit governance members")
    if permission_fields_requested and not _can_assign_permissions(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update governance member permissions",
        )
    if permission_fields_requested:
        _ensure_permission_codes_allowed_for_unit(
            unit_type=governance_unit.unit_type,
            permission_codes=payload.permission_codes,
            target_label="members",
        )

    previous_user_id = governance_member.user_id

    if "user_id" in payload_fields_set and payload.user_id is not None and payload.user_id != governance_member.user_id:
        duplicate_member = (
            db.query(GovernanceMember.id)
            .filter(
                GovernanceMember.governance_unit_id == governance_unit.id,
                GovernanceMember.user_id == payload.user_id,
                GovernanceMember.id != governance_member.id,
            )
            .first()
        )
        if duplicate_member is not None:
            raise HTTPException(status_code=400, detail="That student already has a membership record in this governance unit")

        target_user = _validate_student_governance_candidate(
            db,
            school_id=school_id,
            user_id=payload.user_id,
            governance_unit=governance_unit,
        )
        governance_member.user_id = target_user.id

    if "position_title" in payload_fields_set:
        normalized_position_title = _normalize_position_title(payload.position_title)
        if normalized_position_title is None:
            raise HTTPException(
                status_code=400,
                detail=f"position_title is required for {governance_unit.unit_type.value} members",
            )
        governance_member.position_title = normalized_position_title

    governance_member.assigned_by_user_id = current_user.id
    governance_member.is_active = True
    db.flush()

    if "permission_codes" in payload_fields_set:
        _sync_member_permissions(
            db,
            governance_member=governance_member,
            permission_codes=payload.permission_codes,
            granted_by_user_id=current_user.id,
        )

    db.commit()

    return _get_member_in_school_or_404(
        db,
        school_id=school_id,
        governance_member_id=governance_member.id,
    )


def delete_governance_member(
    db: Session,
    *,
    current_user: User,
    governance_member_id: int,
) -> None:
    school_id = get_school_id_or_403(current_user)
    governance_member = _get_member_in_school_or_404(
        db,
        school_id=school_id,
        governance_member_id=governance_member_id,
    )
    governance_unit = governance_member.governance_unit

    if not _can_manage_members(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=403, detail="You do not have permission to remove governance members")

    for member_permission in list(governance_member.member_permissions):
        db.delete(member_permission)

    governance_member.is_active = False
    governance_member.assigned_by_user_id = current_user.id
    db.flush()

    db.commit()


def assign_unit_permission(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    payload: GovernanceUnitPermissionAssign,
) -> GovernanceUnitPermission:
    school_id = get_school_id_or_403(current_user)
    ensure_permission_catalog(db)

    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot assign permissions to an inactive governance unit")

    if not _can_assign_permissions(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=403, detail="You do not have permission to assign governance permissions")

    _ensure_permission_codes_allowed_for_unit(
        unit_type=governance_unit.unit_type,
        permission_codes=[payload.permission_code],
        target_label="units",
    )

    permission = (
        db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == payload.permission_code)
        .first()
    )
    if permission is None:
        raise HTTPException(status_code=404, detail="Governance permission not found")

    governance_unit_permission = (
        db.query(GovernanceUnitPermission)
        .options(selectinload(GovernanceUnitPermission.permission))
        .filter(
            GovernanceUnitPermission.governance_unit_id == governance_unit_id,
            GovernanceUnitPermission.permission_id == permission.id,
        )
        .first()
    )

    if governance_unit_permission is None:
        governance_unit_permission = GovernanceUnitPermission(
            governance_unit_id=governance_unit_id,
            permission_id=permission.id,
        )
        db.add(governance_unit_permission)

    governance_unit_permission.granted_by_user_id = current_user.id
    db.commit()
    db.refresh(governance_unit_permission)

    return (
        db.query(GovernanceUnitPermission)
        .options(selectinload(GovernanceUnitPermission.permission))
        .filter(GovernanceUnitPermission.id == governance_unit_permission.id)
        .first()
    )


def _count_accessible_students(
    db: Session,
    *,
    current_user: User,
    memberships: list[GovernanceMember] | None = None,
    permission_codes: Iterable[PermissionCode] | None = None,
    unit_type: GovernanceUnitType | None = None,
) -> int:
    school_id = get_school_id_or_403(current_user)
    query = db.query(func.count(StudentProfile.id)).filter(StudentProfile.school_id == school_id)

    if _is_school_it(current_user):
        return query.scalar() or 0

    active_memberships = memberships or _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )
    required_permission_codes = set(
        permission_codes or {PermissionCode.VIEW_STUDENTS, PermissionCode.MANAGE_STUDENTS}
    )

    permitted_units = [
        membership.governance_unit
        for membership in active_memberships
        if (unit_type is None or membership.governance_unit.unit_type == unit_type)
        and _membership_has_any_permission(membership, required_permission_codes)
    ]

    if not permitted_units:
        return 0

    if any(unit.department_id is None and unit.program_id is None for unit in permitted_units):
        return query.scalar() or 0

    filters = []
    for governance_unit in permitted_units:
        condition_parts = []
        if governance_unit.department_id is not None:
            condition_parts.append(StudentProfile.department_id == governance_unit.department_id)
        if governance_unit.program_id is not None:
            condition_parts.append(StudentProfile.program_id == governance_unit.program_id)
        if condition_parts:
            filters.append(and_(*condition_parts))

    if not filters:
        return 0

    return query.filter(or_(*filters)).scalar() or 0


def _list_dashboard_child_units(
    db: Session,
    *,
    current_user: User,
    governance_unit: GovernanceUnit,
    memberships: list[GovernanceMember],
) -> list[GovernanceDashboardChildUnitSummaryResponse]:
    child_unit_type = CHILD_DASHBOARD_UNIT_TYPE_MAP.get(governance_unit.unit_type)
    if child_unit_type is None:
        return []

    query = db.query(
        GovernanceUnit.id,
        GovernanceUnit.unit_code,
        GovernanceUnit.unit_name,
        GovernanceUnit.description,
        GovernanceUnit.unit_type,
    ).filter(
        GovernanceUnit.school_id == governance_unit.school_id,
        GovernanceUnit.parent_unit_id == governance_unit.id,
        GovernanceUnit.unit_type == child_unit_type,
        GovernanceUnit.is_active.is_(True),
    )

    if not _is_school_it(current_user):
        direct_membership_unit_ids = {
            membership.governance_unit_id
            for membership in memberships
            if membership.governance_unit.parent_unit_id == governance_unit.id
            and membership.governance_unit.unit_type == child_unit_type
        }
        current_unit_membership = _get_membership_for_unit(
            memberships,
            governance_unit_id=governance_unit.id,
        )
        can_view_all_children = (
            current_unit_membership is not None
            and _membership_has_any_permission(
                current_unit_membership,
                CHILD_VIEW_PERMISSION_MAP.get(child_unit_type, set()),
            )
        )

        if not can_view_all_children:
            if not direct_membership_unit_ids:
                return []
            query = query.filter(GovernanceUnit.id.in_(direct_membership_unit_ids))

    child_units = query.order_by(GovernanceUnit.unit_name.asc(), GovernanceUnit.id.asc()).all()
    if not child_units:
        return []

    child_unit_ids = [child_unit.id for child_unit in child_units]
    member_count_rows = (
        db.query(
            GovernanceMember.governance_unit_id,
            func.count(GovernanceMember.id),
        )
        .filter(
            GovernanceMember.governance_unit_id.in_(child_unit_ids),
            GovernanceMember.is_active.is_(True),
        )
        .group_by(GovernanceMember.governance_unit_id)
        .all()
    )
    member_count_map = {
        governance_unit_id: member_count
        for governance_unit_id, member_count in member_count_rows
    }

    return [
        GovernanceDashboardChildUnitSummaryResponse(
            id=child_unit.id,
            unit_code=child_unit.unit_code,
            unit_name=child_unit.unit_name,
            description=child_unit.description,
            unit_type=child_unit.unit_type,
            member_count=member_count_map.get(child_unit.id, 0),
        )
        for child_unit in child_units
    ]


def get_governance_dashboard_overview(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
) -> GovernanceDashboardOverviewResponse:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not _can_view_governance_unit(db, current_user=current_user, governance_unit=governance_unit):
        raise HTTPException(status_code=404, detail="Governance unit not found")

    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )
    current_unit_membership = _get_membership_for_unit(
        memberships,
        governance_unit_id=governance_unit.id,
    )
    can_manage_announcements = _is_school_it(current_user) or (
        current_unit_membership is not None
        and _membership_has_permission(current_unit_membership, PermissionCode.MANAGE_ANNOUNCEMENTS)
    )
    can_view_students = _is_school_it(current_user) or (
        current_unit_membership is not None
        and _membership_has_any_permission(
            current_unit_membership,
            {PermissionCode.VIEW_STUDENTS, PermissionCode.MANAGE_STUDENTS},
        )
    )

    recent_announcements: list[GovernanceDashboardAnnouncementSummaryResponse] = []
    published_announcement_count = 0
    if can_manage_announcements:
        recent_announcements = [
            GovernanceDashboardAnnouncementSummaryResponse(
                id=announcement.id,
                title=announcement.title,
                status=announcement.status,
                author_name=announcement.author_name,
                updated_at=announcement.updated_at,
            )
            for announcement in (
                db.query(GovernanceAnnouncement)
                .filter(
                    GovernanceAnnouncement.school_id == school_id,
                    GovernanceAnnouncement.governance_unit_id == governance_unit.id,
                )
                .order_by(GovernanceAnnouncement.updated_at.desc(), GovernanceAnnouncement.id.desc())
                .limit(5)
                .all()
            )
        ]
        published_announcement_count = (
            db.query(func.count(GovernanceAnnouncement.id))
            .filter(
                GovernanceAnnouncement.school_id == school_id,
                GovernanceAnnouncement.governance_unit_id == governance_unit.id,
                GovernanceAnnouncement.status == GovernanceAnnouncementStatus.PUBLISHED,
            )
            .scalar()
            or 0
        )

    total_students = 0
    if can_view_students:
        student_scope_unit_type = None if governance_unit.unit_type == GovernanceUnitType.SSG else governance_unit.unit_type
        total_students = _count_accessible_students(
            db,
            current_user=current_user,
            memberships=memberships,
            unit_type=student_scope_unit_type,
        )

    return GovernanceDashboardOverviewResponse(
        governance_unit_id=governance_unit.id,
        unit_type=governance_unit.unit_type,
        published_announcement_count=published_announcement_count,
        total_students=total_students,
        recent_announcements=recent_announcements,
        child_units=_list_dashboard_child_units(
            db,
            current_user=current_user,
            governance_unit=governance_unit,
            memberships=memberships,
        ),
    )


def get_accessible_students(
    db: Session,
    *,
    current_user: User,
    permission_codes: Iterable[PermissionCode] | None = None,
    unit_type: GovernanceUnitType | None = None,
    skip: int = 0,
    limit: int | None = None,
) -> list[StudentProfile]:
    school_id = get_school_id_or_403(current_user)
    query = (
        db.query(StudentProfile)
        .options(
            selectinload(StudentProfile.user),
            selectinload(StudentProfile.department),
            selectinload(StudentProfile.program),
        )
        .filter(StudentProfile.school_id == school_id)
    )
    safe_skip = max(skip, 0)
    safe_limit = None if limit is None else max(1, min(limit, 250))

    def _finalize(student_query):
        student_query = student_query.order_by(StudentProfile.id.asc()).offset(safe_skip)
        if safe_limit is not None:
            student_query = student_query.limit(safe_limit)
        return student_query.all()

    if _is_school_it(current_user):
        return _finalize(query)

    memberships = _get_active_governance_memberships(
        db,
        school_id=school_id,
        user_id=current_user.id,
    )

    required_permission_codes = set(permission_codes or {PermissionCode.VIEW_STUDENTS, PermissionCode.MANAGE_STUDENTS})

    permitted_units = [
        membership.governance_unit
        for membership in memberships
        if (unit_type is None or membership.governance_unit.unit_type == unit_type)
        and _membership_has_any_permission(membership, required_permission_codes)
    ]

    if not permitted_units:
        return []

    if any(unit.department_id is None and unit.program_id is None for unit in permitted_units):
        return _finalize(query)

    filters = []
    for governance_unit in permitted_units:
        condition_parts = []
        if governance_unit.department_id is not None:
            condition_parts.append(StudentProfile.department_id == governance_unit.department_id)
        if governance_unit.program_id is not None:
            condition_parts.append(StudentProfile.program_id == governance_unit.program_id)
        if condition_parts:
            filters.append(and_(*condition_parts))

    if not filters:
        return []

    return _finalize(query.filter(or_(*filters)))


def list_governance_announcements(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
) -> list[GovernanceAnnouncement]:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not governance_unit.is_active:
        raise HTTPException(status_code=404, detail="Governance unit not found")

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.MANAGE_ANNOUNCEMENTS},
        detail="You do not have permission to view governance announcements for this unit",
    )

    return (
        _announcement_query(db)
        .filter(
            GovernanceAnnouncement.school_id == school_id,
            GovernanceAnnouncement.governance_unit_id == governance_unit.id,
        )
        .order_by(GovernanceAnnouncement.updated_at.desc(), GovernanceAnnouncement.id.desc())
        .all()
    )


def list_school_governance_announcements(
    db: Session,
    *,
    current_user: User,
    status: GovernanceAnnouncementStatus | None = None,
    unit_type: GovernanceUnitType | None = None,
    search_term: str | None = None,
    limit: int = 100,
) -> list[GovernanceAnnouncementMonitorResponse]:
    if not has_any_role(current_user, ["admin", "campus_admin"]):
        raise HTTPException(status_code=403, detail="Only admin or Campus Admin can monitor campus announcements")

    school_id = get_school_id_or_403(current_user)
    normalized_search_term = (search_term or "").strip()

    query = (
        _announcement_query(db)
        .join(GovernanceUnit, GovernanceAnnouncement.governance_unit_id == GovernanceUnit.id)
        .filter(
            GovernanceAnnouncement.school_id == school_id,
            GovernanceUnit.school_id == school_id,
            GovernanceUnit.is_active.is_(True),
        )
    )
    if status is not None:
        query = query.filter(GovernanceAnnouncement.status == status)
    if unit_type is not None:
        query = query.filter(GovernanceUnit.unit_type == unit_type)
    if normalized_search_term:
        like_term = f"%{normalized_search_term}%"
        query = query.filter(
            or_(
                GovernanceAnnouncement.title.ilike(like_term),
                GovernanceAnnouncement.body.ilike(like_term),
                GovernanceUnit.unit_code.ilike(like_term),
                GovernanceUnit.unit_name.ilike(like_term),
            )
        )

    announcements = (
        query.order_by(GovernanceAnnouncement.updated_at.desc(), GovernanceAnnouncement.id.desc())
        .limit(limit)
        .all()
    )
    return [
        GovernanceAnnouncementMonitorResponse(
            id=announcement.id,
            governance_unit_id=announcement.governance_unit_id,
            school_id=announcement.school_id,
            title=announcement.title,
            body=announcement.body,
            status=announcement.status,
            created_by_user_id=announcement.created_by_user_id,
            updated_by_user_id=announcement.updated_by_user_id,
            author_name=announcement.author_name,
            created_at=announcement.created_at,
            updated_at=announcement.updated_at,
            governance_unit_code=announcement.governance_unit.unit_code,
            governance_unit_name=announcement.governance_unit.unit_name,
            governance_unit_type=announcement.governance_unit.unit_type,
            governance_unit_description=announcement.governance_unit.description,
        )
        for announcement in announcements
    ]


def create_governance_announcement(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    payload: GovernanceAnnouncementCreate,
) -> GovernanceAnnouncement:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )
    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot add announcements to an inactive governance unit")

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.MANAGE_ANNOUNCEMENTS},
        detail="You do not have permission to manage governance announcements for this unit",
    )

    announcement = GovernanceAnnouncement(
        governance_unit_id=governance_unit.id,
        school_id=school_id,
        title=_normalize_announcement_title(payload.title),
        body=_normalize_announcement_body(payload.body),
        status=payload.status,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(announcement)
    db.commit()

    return _get_announcement_in_school_or_404(
        db,
        school_id=school_id,
        announcement_id=announcement.id,
    )


def update_governance_announcement(
    db: Session,
    *,
    current_user: User,
    announcement_id: int,
    payload: GovernanceAnnouncementUpdate,
) -> GovernanceAnnouncement:
    school_id = get_school_id_or_403(current_user)
    announcement = _get_announcement_in_school_or_404(
        db,
        school_id=school_id,
        announcement_id=announcement_id,
    )
    governance_unit = announcement.governance_unit

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot edit announcements under an inactive governance unit")

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.MANAGE_ANNOUNCEMENTS},
        detail="You do not have permission to manage governance announcements for this unit",
    )

    payload_fields_set = _get_payload_fields_set(payload)
    if "title" in payload_fields_set and payload.title is not None:
        announcement.title = _normalize_announcement_title(payload.title)
    if "body" in payload_fields_set and payload.body is not None:
        announcement.body = _normalize_announcement_body(payload.body)
    if "status" in payload_fields_set and payload.status is not None:
        announcement.status = payload.status

    announcement.updated_by_user_id = current_user.id
    db.commit()

    return _get_announcement_in_school_or_404(
        db,
        school_id=school_id,
        announcement_id=announcement.id,
    )


def delete_governance_announcement(
    db: Session,
    *,
    current_user: User,
    announcement_id: int,
) -> None:
    school_id = get_school_id_or_403(current_user)
    announcement = _get_announcement_in_school_or_404(
        db,
        school_id=school_id,
        announcement_id=announcement_id,
    )

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=announcement.governance_unit,
        permission_codes={PermissionCode.MANAGE_ANNOUNCEMENTS},
        detail="You do not have permission to manage governance announcements for this unit",
    )

    db.delete(announcement)
    db.commit()


def get_governance_student_note(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    student_profile_id: int,
) -> GovernanceStudentNote | GovernanceStudentNoteResponse:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not governance_unit.is_active:
        raise HTTPException(status_code=404, detail="Governance unit not found")

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.VIEW_STUDENTS, PermissionCode.MANAGE_STUDENTS},
        detail="You do not have permission to view governance student notes for this unit",
    )

    student_profile = _get_student_profile_in_unit_scope_or_404(
        db,
        school_id=school_id,
        governance_unit=governance_unit,
        student_profile_id=student_profile_id,
    )
    note = _get_note_in_school(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit.id,
        student_profile_id=student_profile.id,
    )
    if note is not None:
        return note

    return GovernanceStudentNoteResponse(
        id=0,
        governance_unit_id=governance_unit.id,
        student_profile_id=student_profile.id,
        school_id=school_id,
        tags=[],
        notes="",
        created_by_user_id=None,
        updated_by_user_id=None,
        created_at=student_profile.user.created_at,
        updated_at=student_profile.user.created_at,
    )


def upsert_governance_student_note(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
    student_profile_id: int,
    payload: GovernanceStudentNoteUpdate,
) -> GovernanceStudentNote:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if not governance_unit.is_active:
        raise HTTPException(status_code=400, detail="Cannot manage notes under an inactive governance unit")

    _require_unit_membership_permission(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
        permission_codes={PermissionCode.MANAGE_STUDENTS},
        detail="You do not have permission to manage governance student notes for this unit",
    )

    student_profile = _get_student_profile_in_unit_scope_or_404(
        db,
        school_id=school_id,
        governance_unit=governance_unit,
        student_profile_id=student_profile_id,
    )
    note = _get_note_in_school(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit.id,
        student_profile_id=student_profile.id,
    )

    normalized_notes = (payload.notes or "").strip()
    normalized_tags = _normalize_governance_tags(payload.tags)
    if note is None:
        note = GovernanceStudentNote(
            governance_unit_id=governance_unit.id,
            student_profile_id=student_profile.id,
            school_id=school_id,
            created_by_user_id=current_user.id,
        )
        db.add(note)
        db.flush()

    note.tags = normalized_tags
    note.notes = normalized_notes
    note.updated_by_user_id = current_user.id
    db.commit()

    refreshed_note = _get_note_in_school(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit.id,
        student_profile_id=student_profile.id,
    )
    if refreshed_note is None:
        raise HTTPException(status_code=500, detail="Failed to save governance student note")
    return refreshed_note


def delete_governance_unit(
    db: Session,
    *,
    current_user: User,
    governance_unit_id: int,
) -> None:
    school_id = get_school_id_or_403(current_user)
    governance_unit = _get_unit_in_school_or_404(
        db,
        school_id=school_id,
        governance_unit_id=governance_unit_id,
    )

    if governance_unit.unit_type == GovernanceUnitType.SSG:
        raise HTTPException(status_code=400, detail="The campus SSG is fixed and cannot be deleted")

    if not _can_edit_governance_unit(
        db,
        current_user=current_user,
        governance_unit=governance_unit,
    ):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this governance unit")

    active_child_unit = (
        db.query(GovernanceUnit.id)
        .filter(
            GovernanceUnit.parent_unit_id == governance_unit.id,
            GovernanceUnit.is_active.is_(True),
        )
        .first()
    )
    if active_child_unit is not None:
        raise HTTPException(
            status_code=400,
            detail="Deactivate child governance units first before deleting this unit",
        )

    governance_unit.is_active = False
    for member in governance_unit.members:
        member.is_active = False

    db.commit()
