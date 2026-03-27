"""Use: Tests governance hierarchy API behavior.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.security import create_access_token
from app.models import Department, Program, Role, School, SchoolSetting, StudentProfile, User, UserRole
from app.models.attendance import Attendance as AttendanceModel
from app.models.event import Event as EventModel, EventStatus as ModelEventStatus
from sqlalchemy.orm import joinedload
from app.models.governance_hierarchy import (
    GovernanceAnnouncement,
    GovernanceAnnouncementStatus,
    GovernanceMember,
    GovernanceMemberPermission,
    GovernancePermission,
    GovernanceUnit,
    GovernanceUnitPermission,
    GovernanceUnitType,
    PermissionCode,
)
from app.schemas.governance_hierarchy import GovernanceUnitCreate
from app.services import governance_hierarchy_service


def _create_school(test_db, *, code: str) -> School:
    school = School(
        name=f"Governance School {code}",
        school_name=f"Governance School {code}",
        school_code=code,
        address="Governance Address",
    )
    test_db.add(school)
    test_db.commit()
    return school


def _create_role(test_db, *, name: str) -> Role:
    role = Role(name=name)
    test_db.add(role)
    test_db.commit()
    return role


def _create_user(
    test_db,
    *,
    email: str,
    school_id: int,
    role_ids: list[int] | None = None,
) -> User:
    user = User(
        email=email,
        school_id=school_id,
        first_name="Test",
        last_name="User",
        must_change_password=False,
    )
    user.set_password("Password123!")
    test_db.add(user)
    test_db.commit()

    for role_id in role_ids or []:
        test_db.add(UserRole(user_id=user.id, role_id=role_id))
    test_db.commit()
    return user


def _create_academic_scope(
    test_db,
    *,
    department_name: str,
    program_name: str,
    school_id: int | None = None,
) -> tuple[Department, Program]:
    resolved_school_id = school_id
    if resolved_school_id is None:
        resolved_school_id = test_db.query(School.id).order_by(School.id.asc()).scalar()
    department = Department(name=department_name, school_id=resolved_school_id)
    program = Program(name=program_name, school_id=resolved_school_id)
    program.departments.append(department)
    test_db.add_all([department, program])
    test_db.commit()
    return department, program


def _create_student_profile(
    test_db,
    *,
    user_id: int,
    school_id: int,
    student_id: str,
    department_id: int,
    program_id: int,
) -> StudentProfile:
    profile = StudentProfile(
        user_id=user_id,
        school_id=school_id,
        student_id=student_id,
        department_id=department_id,
        program_id=program_id,
        year_level=1,
    )
    test_db.add(profile)
    test_db.commit()
    return profile


def _create_governance_member(
    test_db,
    *,
    governance_unit_id: int,
    user_id: int,
    assigned_by_user_id: int,
) -> GovernanceMember:
    member = GovernanceMember(
        governance_unit_id=governance_unit_id,
        user_id=user_id,
        assigned_by_user_id=assigned_by_user_id,
    )
    test_db.add(member)
    test_db.commit()
    return member


def _create_event(
    test_db,
    *,
    school_id: int,
    name: str,
    department_ids: list[int] | None = None,
    program_ids: list[int] | None = None,
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    early_check_in_minutes: int = 0,
    late_threshold_minutes: int = 0,
    sign_out_grace_minutes: int = 0,
    sign_out_override_until: datetime | None = None,
) -> EventModel:
    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None)
    resolved_start_datetime = start_datetime or (manila_now - timedelta(minutes=5))
    resolved_end_datetime = end_datetime or (manila_now + timedelta(hours=2))
    event = EventModel(
        school_id=school_id,
        name=name,
        location="Campus Hall",
        start_datetime=resolved_start_datetime,
        end_datetime=resolved_end_datetime,
        status=ModelEventStatus.UPCOMING,
        early_check_in_minutes=early_check_in_minutes,
        late_threshold_minutes=late_threshold_minutes,
        sign_out_grace_minutes=sign_out_grace_minutes,
        sign_out_override_until=sign_out_override_until,
    )
    if department_ids:
        event.departments = (
            test_db.query(Department)
            .filter(Department.id.in_(department_ids))
            .all()
        )
    if program_ids:
        event.programs = (
            test_db.query(Program)
            .filter(Program.id.in_(program_ids))
            .all()
        )
    test_db.add(event)
    test_db.commit()
    return event


def _grant_member_permission(
    test_db,
    *,
    governance_member_id: int,
    permission_id: int,
    granted_by_user_id: int,
) -> GovernanceMemberPermission:
    member_permission = GovernanceMemberPermission(
        governance_member_id=governance_member_id,
        permission_id=permission_id,
        granted_by_user_id=granted_by_user_id,
    )
    test_db.add(member_permission)
    test_db.commit()
    return member_permission


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.email})
    return {"Authorization": f"Bearer {token}"}


def _seed_permission_catalog(test_db) -> None:
    governance_hierarchy_service.ensure_permission_catalog(test_db)
    test_db.commit()


def test_school_it_can_create_ssg_unit_and_assign_member_and_permission(client, test_db):
    school = _create_school(test_db, code="PHASE1-SSG")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")
    department, program = _create_academic_scope(
        test_db,
        department_name="Phase 1 Department",
        program_name="Phase 1 Program",
    )

    school_it_user = _create_user(
        test_db,
        email="school.it@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    student_user = _create_user(
        test_db,
        email="ssg.member@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=student_user.id,
        school_id=school.id,
        student_id="PHASE1-001",
        department_id=department.id,
        program_id=program.id,
    )

    create_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "ssg-central",
            "unit_name": "Central SSG",
            "unit_type": "SSG",
        },
    )

    assert create_response.status_code == 201
    created_unit = create_response.json()
    assert created_unit["unit_code"] == "SSG-CENTRAL"
    assert created_unit["unit_type"] == "SSG"
    assert created_unit["school_id"] == school.id
    assert created_unit["parent_unit_id"] is None

    governance_unit_id = created_unit["id"]

    member_response = client.post(
        f"/api/governance/units/{governance_unit_id}/members",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": student_user.id,
            "position_title": "President",
            "permission_codes": ["manage_events", "manage_attendance"],
        },
    )

    assert member_response.status_code == 201
    member_payload = member_response.json()
    assert member_payload["user_id"] == student_user.id
    assert member_payload["position_title"] == "President"
    assert sorted(
        item["permission"]["permission_code"] for item in member_payload["member_permissions"]
    ) == ["manage_attendance", "manage_events"]

    assigned_roles = {
        row.role.name
        for row in (
            test_db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == student_user.id)
            .all()
        )
    }
    assert assigned_roles == {"student"}

    permission_response = client.post(
        f"/api/governance/units/{governance_unit_id}/permissions",
        headers=_auth_headers(school_it_user),
        json={"permission_code": "create_sg"},
    )

    assert permission_response.status_code == 201
    permission_payload = permission_response.json()
    assert permission_payload["permission"]["permission_code"] == "create_sg"

    list_response = client.get(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
    )

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["id"] == governance_unit_id

    detail_response = client.get(
        f"/api/governance/units/{governance_unit_id}",
        headers=_auth_headers(school_it_user),
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert len(detail_payload["members"]) == 1
    assert len(detail_payload["members"][0]["member_permissions"]) == 2
    assert len(detail_payload["unit_permissions"]) == 1


def test_non_school_it_cannot_create_ssg_unit(client, test_db):
    school = _create_school(test_db, code="NO-SSG")
    admin_role = _create_role(test_db, name="admin")
    admin_user = _create_user(
        test_db,
        email="school.admin@example.com",
        school_id=school.id,
        role_ids=[admin_role.id],
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(admin_user),
        json={
            "unit_code": "SSG-BLOCKED",
            "unit_name": "Blocked SSG",
            "unit_type": "SSG",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only Campus Admin can create SSG units"


def test_only_one_ssg_unit_is_allowed_per_school(client, test_db):
    school = _create_school(test_db, code="ONE-SSG")
    school_it_role = _create_role(test_db, name="school_IT")
    school_it_user = _create_user(
        test_db,
        email="single.ssg@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    first_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "SSG-ROOT",
            "unit_name": "Root SSG",
            "unit_type": "SSG",
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "SSG-OTHER",
            "unit_name": "Other SSG",
            "unit_type": "SSG",
        },
    )

    assert second_response.status_code == 400
    assert "Only one SSG unit is allowed per school" in second_response.json()["detail"]


def test_campus_ssg_setup_endpoint_bootstraps_default_ssg(client, test_db):
    school = _create_school(test_db, code="SSG-SETUP")
    school_it_role = _create_role(test_db, name="school_IT")
    school_it_user = _create_user(
        test_db,
        email="default.ssg.setup@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    response = client.get(
        "/api/governance/ssg/setup",
        headers=_auth_headers(school_it_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_imported_students"] == 0
    assert payload["unit"]["unit_code"] == "SSG"
    assert payload["unit"]["unit_name"] == "Supreme Students Government"
    assert payload["unit"]["description"] == "Fixed campus-wide student government unit for the school."
    assert payload["unit"]["unit_type"] == "SSG"

    stored_ssg_units = (
        test_db.query(GovernanceUnit)
        .filter(
            GovernanceUnit.school_id == school.id,
            GovernanceUnit.unit_type == GovernanceUnitType.SSG,
        )
        .all()
    )
    assert len(stored_ssg_units) == 1


def test_campus_admin_can_search_update_and_remove_ssg_members(client, test_db):
    school = _create_school(test_db, code="SSG-MEMBER-CRUD")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    _create_role(test_db, name="ssg")
    department, program = _create_academic_scope(
        test_db,
        department_name="Member CRUD Department",
        program_name="Member CRUD Program",
    )

    school_it_user = _create_user(
        test_db,
        email="member.crud.admin@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    first_student = _create_user(
        test_db,
        email="member.one@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    second_student = _create_user(
        test_db,
        email="member.two@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=first_student.id,
        school_id=school.id,
        student_id="CRUD-001",
        department_id=department.id,
        program_id=program.id,
    )
    _create_student_profile(
        test_db,
        user_id=second_student.id,
        school_id=school.id,
        student_id="CRUD-002",
        department_id=department.id,
        program_id=program.id,
    )

    create_unit_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "SSG-CRUD",
            "unit_name": "CRUD SSG",
            "unit_type": "SSG",
        },
    )
    assert create_unit_response.status_code == 201
    governance_unit_id = create_unit_response.json()["id"]

    search_response = client.get(
        f"/api/governance/students/search?q=CRUD-00&governance_unit_id={governance_unit_id}",
        headers=_auth_headers(school_it_user),
    )
    assert search_response.status_code == 200
    assert [item["student_profile"]["student_id"] for item in search_response.json()] == [
        "CRUD-001",
        "CRUD-002",
    ]

    create_member_response = client.post(
        f"/api/governance/units/{governance_unit_id}/members",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": first_student.id,
            "position_title": "President",
            "permission_codes": ["manage_events"],
        },
    )
    assert create_member_response.status_code == 201
    governance_member_id = create_member_response.json()["id"]

    filtered_search_response = client.get(
        f"/api/governance/students/search?q=CRUD-00&governance_unit_id={governance_unit_id}",
        headers=_auth_headers(school_it_user),
    )
    assert filtered_search_response.status_code == 200
    assert [item["student_profile"]["student_id"] for item in filtered_search_response.json()] == [
        "CRUD-002",
    ]

    update_member_response = client.patch(
        f"/api/governance/members/{governance_member_id}",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": second_student.id,
            "position_title": "Secretary",
            "permission_codes": ["manage_attendance", "view_students"],
        },
    )
    assert update_member_response.status_code == 200
    updated_payload = update_member_response.json()
    assert updated_payload["user_id"] == second_student.id
    assert updated_payload["position_title"] == "Secretary"
    assert sorted(
        item["permission"]["permission_code"] for item in updated_payload["member_permissions"]
    ) == ["manage_attendance", "view_students"]

    first_student_roles = {
        row.role.name
        for row in (
            test_db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == first_student.id)
            .all()
        )
    }
    second_student_roles = {
        row.role.name
        for row in (
            test_db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == second_student.id)
            .all()
        )
    }
    assert first_student_roles == {"student"}
    assert second_student_roles == {"student"}
    test_db.expire_all()
    first_student_after_reassign = test_db.query(User).filter(User.id == first_student.id).first()
    second_student_after_reassign = test_db.query(User).filter(User.id == second_student.id).first()
    assert first_student_after_reassign is not None
    assert second_student_after_reassign is not None

    delete_response = client.delete(
        f"/api/governance/members/{governance_member_id}",
        headers=_auth_headers(school_it_user),
    )
    assert delete_response.status_code == 204

    second_student_roles_after_delete = {
        row.role.name
        for row in (
            test_db.query(UserRole)
            .join(Role, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == second_student.id)
            .all()
        )
    }
    assert second_student_roles_after_delete == {"student"}
    test_db.expire_all()
    second_student_after_delete = test_db.query(User).filter(User.id == second_student.id).first()
    assert second_student_after_delete is not None


def test_campus_admin_must_set_position_title_for_ssg_members(client, test_db):
    school = _create_school(test_db, code="SSG-POSITION-REQ")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    _create_role(test_db, name="ssg")
    department, program = _create_academic_scope(
        test_db,
        department_name="Position Required Department",
        program_name="Position Required Program",
    )

    school_it_user = _create_user(
        test_db,
        email="position.required.admin@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    student_user = _create_user(
        test_db,
        email="position.required.student@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=student_user.id,
        school_id=school.id,
        student_id="POS-001",
        department_id=department.id,
        program_id=program.id,
    )

    create_unit_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "SSG-POSITION",
            "unit_name": "Position Required SSG",
            "unit_type": "SSG",
        },
    )
    assert create_unit_response.status_code == 201
    governance_unit_id = create_unit_response.json()["id"]

    create_member_response = client.post(
        f"/api/governance/units/{governance_unit_id}/members",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": student_user.id,
            "permission_codes": ["manage_events"],
        },
    )

    assert create_member_response.status_code == 400
    assert create_member_response.json()["detail"] == "position_title is required for SSG members"


def test_readding_deleted_governance_member_reactivates_existing_membership(client, test_db):
    school = _create_school(test_db, code="SSG-REACTIVATE")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    _create_role(test_db, name="ssg")
    department, program = _create_academic_scope(
        test_db,
        department_name="Reactivation Department",
        program_name="Reactivation Program",
        school_id=school.id,
    )

    school_it_user = _create_user(
        test_db,
        email="reactivate.school.it@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    student_user = _create_user(
        test_db,
        email="reactivate.student@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=student_user.id,
        school_id=school.id,
        student_id="REACT-001",
        department_id=department.id,
        program_id=program.id,
    )

    create_unit_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(school_it_user),
        json={
            "unit_code": "SSG-REACT",
            "unit_name": "Reactivation SSG",
            "unit_type": "SSG",
        },
    )
    assert create_unit_response.status_code == 201
    governance_unit_id = create_unit_response.json()["id"]

    assign_response = client.post(
        f"/api/governance/units/{governance_unit_id}/members",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": student_user.id,
            "position_title": "President",
            "permission_codes": ["manage_events"],
        },
    )
    assert assign_response.status_code == 201
    governance_member_id = assign_response.json()["id"]

    delete_response = client.delete(
        f"/api/governance/members/{governance_member_id}",
        headers=_auth_headers(school_it_user),
    )
    assert delete_response.status_code == 204

    reassign_response = client.post(
        f"/api/governance/units/{governance_unit_id}/members",
        headers=_auth_headers(school_it_user),
        json={
            "user_id": student_user.id,
            "position_title": "President",
            "permission_codes": ["manage_events"],
        },
    )
    assert reassign_response.status_code == 201
    reassign_payload = reassign_response.json()
    assert reassign_payload["id"] == governance_member_id
    assert reassign_payload["user_id"] == student_user.id
    assert reassign_payload["is_active"] is True
    assert [item["permission"]["permission_code"] for item in reassign_payload["member_permissions"]] == [
        "manage_events"
    ]

    test_db.expire_all()
    memberships = (
        test_db.query(GovernanceMember)
        .filter(GovernanceMember.governance_unit_id == governance_unit_id)
        .all()
    )
    assert len(memberships) == 1
    assert memberships[0].id == governance_member_id
    assert memberships[0].is_active is True

    member_permissions = (
        test_db.query(GovernanceMemberPermission)
        .filter(GovernanceMemberPermission.governance_member_id == governance_member_id)
        .all()
    )
    assert len(member_permissions) == 1

    detail_response = client.get(
        f"/api/governance/units/{governance_unit_id}",
        headers=_auth_headers(school_it_user),
    )
    assert detail_response.status_code == 200
    assert [member["id"] for member in detail_response.json()["members"]] == [governance_member_id]


def test_ssg_member_with_create_sg_permission_can_create_sg_unit(client, test_db):
    school = _create_school(test_db, code="SG-CREATE")
    school_it_role = _create_role(test_db, name="school_IT")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.sg@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.creator@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    department = Department(name="Engineering", school_id=school.id)
    test_db.add(department)
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ROOT",
        unit_name="Root SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_user),
        json={
            "unit_code": "SG-ENG",
            "unit_name": "Engineering SG",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit.id,
            "department_id": department.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["unit_type"] == "SG"
    assert payload["parent_unit_id"] == ssg_unit.id
    assert payload["department_id"] == department.id


def test_sg_cannot_be_created_with_program_scope(client, test_db):
    school = _create_school(test_db, code="SG-PROGRAM-BLOCK")
    school_it_role = _create_role(test_db, name="school_IT")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.sg.program@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.program.block@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    engineering = Department(name="Engineering Program Block", school_id=school.id)
    computer_engineering = Program(name="BS Computer Engineering", school_id=school.id)
    computer_engineering.departments.append(engineering)
    test_db.add_all([engineering, computer_engineering])
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-PROGRAM-BLOCK",
        unit_name="Root SSG Program Block",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_user),
        json={
            "unit_code": "SG-ENG-PROGRAM",
            "unit_name": "Engineering Program SG",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit.id,
            "department_id": engineering.id,
            "program_id": computer_engineering.id,
        },
    )

    assert response.status_code == 400
    assert "department-wide" in response.json()["detail"]


def test_only_one_sg_unit_is_allowed_per_department(client, test_db):
    school = _create_school(test_db, code="ONE-SG-PER-DEPT")
    school_it_role = _create_role(test_db, name="school_IT")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.one.sg@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.one.sg@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    department = Department(name="Single SG Department", school_id=school.id)
    test_db.add(department)
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SINGLE-SG",
        unit_name="SSG Single SG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    first_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_user),
        json={
            "unit_code": "SG-SINGLE-FIRST",
            "unit_name": "Single SG First",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit.id,
            "department_id": department.id,
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_user),
        json={
            "unit_code": "SG-SINGLE-SECOND",
            "unit_name": "Single SG Second",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit.id,
            "department_id": department.id,
        },
    )

    assert second_response.status_code == 400
    assert "Only one SG unit is allowed per department" in second_response.json()["detail"]


def test_ssg_member_can_edit_sg_unit_with_create_sg_permission(client, test_db):
    school = _create_school(test_db, code="SG-EDIT")
    school_it_role = _create_role(test_db, name="school_IT")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.sg.edit@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.editor@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    department = Department(name="Editable SG Department", school_id=school.id)
    test_db.add(department)
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-EDIT-ROOT",
        unit_name="Editable SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-EDITABLE",
            unit_name="Editable SG",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=department.id,
            program_id=None,
        ),
    )

    response = client.patch(
        f"/api/governance/units/{sg_unit.id}",
        headers=_auth_headers(ssg_user),
        json={
            "unit_name": "Edited Engineering SG",
            "description": "Updated by the parent SSG officer.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["unit_name"] == "Edited Engineering SG"
    assert payload["description"] == "Updated by the parent SSG officer."


def test_sg_cannot_create_org_outside_parent_department_scope(client, test_db):
    school = _create_school(test_db, code="ORG-SCOPE")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.org@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.org@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.member@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    engineering = Department(name="Engineering Scope", school_id=school.id)
    arts = Department(name="Arts Scope", school_id=school.id)
    arts_program = Program(name="BA Arts Scope", school_id=school.id)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, arts_program])
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ORG",
        unit_name="SSG ORG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-ROOT",
            unit_name="SG Root",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=engineering.id,
            program_id=None,
        ),
    )

    sg_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_membership.id,
        permission_id=create_org_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(sg_user),
        json={
            "unit_code": "ORG-ARTS",
            "unit_name": "Arts ORG",
            "unit_type": "ORG",
            "parent_unit_id": sg_unit.id,
            "department_id": arts.id,
            "program_id": arts_program.id,
        },
    )

    assert response.status_code == 400
    assert "same department scope" in response.json()["detail"]


def test_only_one_org_unit_is_allowed_per_program(client, test_db):
    school = _create_school(test_db, code="ONE-ORG-PER-PROGRAM")
    school_it_role = _create_role(test_db, name="school_IT")
    ssg_role = _create_role(test_db, name="ssg")
    sg_role = _create_role(test_db, name="sg")

    school_it_user = _create_user(
        test_db,
        email="school.it.one.org@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.one.org@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.one.org@example.com",
        school_id=school.id,
        role_ids=[sg_role.id],
    )

    department = Department(name="Program ORG Department", school_id=school.id)
    program = Program(name="BS Program ORG", school_id=school.id)
    program.departments.append(department)
    test_db.add_all([department, program])
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ONE-ORG",
        unit_name="SSG One ORG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-ONE-ORG",
            unit_name="SG One ORG",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=department.id,
            program_id=None,
        ),
    )

    sg_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_membership.id,
        permission_id=create_org_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    first_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(sg_user),
        json={
            "unit_code": "ORG-FIRST",
            "unit_name": "First ORG",
            "unit_type": "ORG",
            "parent_unit_id": sg_unit.id,
            "program_id": program.id,
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(sg_user),
        json={
            "unit_code": "ORG-SECOND",
            "unit_name": "Second ORG",
            "unit_type": "ORG",
            "parent_unit_id": sg_unit.id,
            "program_id": program.id,
        },
    )

    assert second_response.status_code == 400
    assert "Only one ORG unit is allowed per program" in second_response.json()["detail"]


def test_sg_cannot_create_org_with_program_outside_effective_department_scope(client, test_db):
    school = _create_school(test_db, code="ORG-PROGRAM")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.program@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.program@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.program@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    engineering = Department(name="Engineering Program Scope", school_id=school.id)
    arts = Department(name="Arts Program Scope", school_id=school.id)
    arts_program = Program(name="BA Program Scope", school_id=school.id)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, arts_program])
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-PROGRAM",
        unit_name="SSG Program",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-PROGRAM",
            unit_name="SG Program",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=engineering.id,
            program_id=None,
        ),
    )

    sg_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_membership.id,
        permission_id=create_org_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(sg_user),
        json={
            "unit_code": "ORG-PROGRAM",
            "unit_name": "ORG Program",
            "unit_type": "ORG",
            "parent_unit_id": sg_unit.id,
            "program_id": arts_program.id,
        },
    )

    assert response.status_code == 400
    assert "parent SG department scope" in response.json()["detail"]


def test_org_must_include_program_scope(client, test_db):
    school = _create_school(test_db, code="ORG-REQUIRES-PROGRAM")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.org.required@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.org.required@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.org.required@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    engineering = Department(name="Engineering ORG Required", school_id=school.id)
    test_db.add(engineering)
    test_db.commit()

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ORG-REQ",
        unit_name="SSG ORG Required",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-ORG-REQ",
            unit_name="SG ORG Required",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=engineering.id,
            program_id=None,
        ),
    )

    sg_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_membership.id,
        permission_id=create_org_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    response = client.post(
        "/api/governance/units",
        headers=_auth_headers(sg_user),
        json={
            "unit_code": "ORG-NO-PROGRAM",
            "unit_name": "ORG Without Program",
            "unit_type": "ORG",
            "parent_unit_id": sg_unit.id,
        },
    )

    assert response.status_code == 400
    assert "must include program_id" in response.json()["detail"]


def test_ssg_member_can_search_and_assign_sg_members_with_department_scope(client, test_db):
    school = _create_school(test_db, code="SG-MEMBER-SCOPE")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")
    sg_role = _create_role(test_db, name="sg")

    school_it_user = _create_user(
        test_db,
        email="school.it.sg.members@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.member.manager@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    engineering_student = _create_user(
        test_db,
        email="engineering.student@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    arts_student = _create_user(
        test_db,
        email="arts.student.scope@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    engineering = Department(name="Engineering Member Scope", school_id=school.id)
    arts = Department(name="Arts Member Scope", school_id=school.id)
    engineering_program = Program(name="BS Computer Engineering Member Scope", school_id=school.id)
    arts_program = Program(name="BA Arts Member Scope", school_id=school.id)
    engineering_program.departments.append(engineering)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, engineering_program, arts_program])
    test_db.commit()

    _create_student_profile(
        test_db,
        user_id=engineering_student.id,
        school_id=school.id,
        student_id="ENG-SCOPE-001",
        department_id=engineering.id,
        program_id=engineering_program.id,
    )
    _create_student_profile(
        test_db,
        user_id=arts_student.id,
        school_id=school.id,
        student_id="ART-SCOPE-001",
        department_id=arts.id,
        program_id=arts_program.id,
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-MEMBERS",
        unit_name="SSG SG Members",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    manage_members_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_MEMBERS)
        .first()
    )
    assign_permissions_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.ASSIGN_PERMISSIONS)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    for permission in (create_sg_permission, manage_members_permission, assign_permissions_permission):
        _grant_member_permission(
            test_db,
            governance_member_id=ssg_membership.id,
            permission_id=permission.id,
            granted_by_user_id=school_it_user.id,
        )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-MEMBER-SCOPE",
            unit_name="SG Member Scope",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=engineering.id,
            program_id=None,
        ),
    )

    search_response = client.get(
        f"/api/governance/students/search?q=SCOPE-00&governance_unit_id={sg_unit.id}",
        headers=_auth_headers(ssg_user),
    )
    assert search_response.status_code == 200
    assert [item["student_profile"]["student_id"] for item in search_response.json()] == ["ENG-SCOPE-001"]

    blocked_assignment_response = client.post(
        f"/api/governance/units/{sg_unit.id}/members",
        headers=_auth_headers(ssg_user),
        json={
            "user_id": arts_student.id,
            "position_title": "Secretary",
            "permission_codes": ["create_org"],
        },
    )
    assert blocked_assignment_response.status_code == 400
    assert "department scope" in blocked_assignment_response.json()["detail"]

    missing_position_response = client.post(
        f"/api/governance/units/{sg_unit.id}/members",
        headers=_auth_headers(ssg_user),
        json={
            "user_id": engineering_student.id,
            "permission_codes": ["create_org"],
        },
    )
    assert missing_position_response.status_code == 400
    assert missing_position_response.json()["detail"] == "position_title is required for SG members"

    assigned_member_response = client.post(
        f"/api/governance/units/{sg_unit.id}/members",
        headers=_auth_headers(ssg_user),
        json={
            "user_id": engineering_student.id,
            "position_title": "President",
            "permission_codes": ["create_org"],
        },
    )
    assert assigned_member_response.status_code == 201
    assigned_payload = assigned_member_response.json()
    assert assigned_payload["position_title"] == "President"
    assert [
        item["permission"]["permission_code"]
        for item in assigned_payload["member_permissions"]
    ] == [create_org_permission.permission_code.value]

    invalid_permission_response = client.post(
        f"/api/governance/units/{sg_unit.id}/members",
        headers=_auth_headers(ssg_user),
        json={
            "user_id": engineering_student.id,
            "position_title": "Vice President",
            "permission_codes": ["create_sg"],
        },
    )
    assert invalid_permission_response.status_code == 400
    assert "Permissions not allowed for SG members" in invalid_permission_response.json()["detail"]


def test_assigning_sg_member_keeps_governance_only_access_without_base_sg_role(client, test_db):
    school = _create_school(test_db, code="SG-ROLE-AUTO")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")
    ssg_role = _create_role(test_db, name="ssg")

    school_it_user = _create_user(
        test_db,
        email="school.it.sg.role@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="ssg.sg.role@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )
    engineering_student = _create_user(
        test_db,
        email="engineering.sg.role@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    engineering, engineering_program = _create_academic_scope(
        test_db,
        department_name="Engineering SG Role",
        program_name="BS Computer Engineering SG Role",
    )
    _create_student_profile(
        test_db,
        user_id=engineering_student.id,
        school_id=school.id,
        student_id="SG-ROLE-001",
        department_id=engineering.id,
        program_id=engineering_program.id,
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-ROLE",
        unit_name="SSG SG Role",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )
    manage_members_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_MEMBERS)
        .first()
    )
    assign_permissions_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.ASSIGN_PERMISSIONS)
        .first()
    )
    create_org_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_ORG)
        .first()
    )

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=school_it_user.id,
    )
    for permission in (create_sg_permission, manage_members_permission, assign_permissions_permission):
        _grant_member_permission(
            test_db,
            governance_member_id=ssg_membership.id,
            permission_id=permission.id,
            granted_by_user_id=school_it_user.id,
        )

    sg_unit = governance_hierarchy_service.create_governance_unit(
        test_db,
        current_user=ssg_user,
        payload=GovernanceUnitCreate(
            unit_code="SG-ROLE-AUTO",
            unit_name="SG Role Auto",
            unit_type=GovernanceUnitType.SG,
            parent_unit_id=ssg_unit.id,
            department_id=engineering.id,
            program_id=None,
        ),
    )

    assigned_member_response = client.post(
        f"/api/governance/units/{sg_unit.id}/members",
        headers=_auth_headers(ssg_user),
        json={
            "user_id": engineering_student.id,
            "position_title": "President",
            "permission_codes": ["create_org"],
        },
    )

    assert assigned_member_response.status_code == 201
    assigned_payload = assigned_member_response.json()

    updated_student = (
        test_db.query(User)
        .options(joinedload(User.roles).joinedload(UserRole.role))
        .filter(User.id == engineering_student.id)
        .first()
    )
    assert updated_student is not None
    assert {
        role_assignment.role.name
        for role_assignment in updated_student.roles
        if getattr(role_assignment, "role", None) is not None
    } == {"student"}
    assert [
        item["permission"]["permission_code"]
        for item in assigned_payload["member_permissions"]
    ] == [create_org_permission.permission_code.value]


def test_get_accessible_students_filters_by_governance_scope(test_db):
    school = _create_school(test_db, code="STUDENT-SCOPE")
    school_it_role = _create_role(test_db, name="school_IT")

    viewer = _create_user(
        test_db,
        email="scope.viewer@example.com",
        school_id=school.id,
    )
    school_it_user = _create_user(
        test_db,
        email="scope.schoolit@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    engineering = Department(name="Engineering Students", school_id=school.id)
    arts = Department(name="Arts Students", school_id=school.id)
    engineering_program = Program(name="BS Engineering", school_id=school.id)
    arts_program = Program(name="BA Arts", school_id=school.id)
    engineering_program.departments.append(engineering)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, engineering_program, arts_program])
    test_db.commit()

    engineering_student_user = _create_user(
        test_db,
        email="eng.student@example.com",
        school_id=school.id,
    )
    arts_student_user = _create_user(
        test_db,
        email="arts.student@example.com",
        school_id=school.id,
    )

    test_db.add_all(
        [
            StudentProfile(
                user_id=engineering_student_user.id,
                school_id=school.id,
                student_id="ENG-001",
                department_id=engineering.id,
                program_id=engineering_program.id,
                year_level=1,
            ),
            StudentProfile(
                user_id=arts_student_user.id,
                school_id=school.id,
                student_id="ART-001",
                department_id=arts.id,
                program_id=arts_program.id,
                year_level=1,
            ),
        ]
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    view_students_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.VIEW_STUDENTS)
        .first()
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STUDENT",
        unit_name="SG Student Scope",
        unit_type=GovernanceUnitType.SG,
        school_id=school.id,
        department_id=engineering.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(sg_unit)
    test_db.commit()

    viewer_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=viewer.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=view_students_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    accessible_students = governance_hierarchy_service.get_accessible_students(
        test_db,
        current_user=viewer,
    )

    assert [student.student_id for student in accessible_students] == ["ENG-001"]


def test_accessible_students_endpoint_returns_governance_scoped_students(client, test_db):
    school = _create_school(test_db, code="STUDENT-SCOPE-API")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")

    viewer = _create_user(
        test_db,
        email="scope.viewer.api@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    school_it_user = _create_user(
        test_db,
        email="scope.schoolit.api@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    engineering = Department(name="Engineering Students API", school_id=school.id)
    arts = Department(name="Arts Students API", school_id=school.id)
    engineering_program = Program(name="BS Engineering API", school_id=school.id)
    arts_program = Program(name="BA Arts API", school_id=school.id)
    engineering_program.departments.append(engineering)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, engineering_program, arts_program])
    test_db.commit()

    engineering_student_user = _create_user(
        test_db,
        email="eng.student.api@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    arts_student_user = _create_user(
        test_db,
        email="arts.student.api@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )

    test_db.add_all(
        [
            StudentProfile(
                user_id=engineering_student_user.id,
                school_id=school.id,
                student_id="ENG-API-001",
                department_id=engineering.id,
                program_id=engineering_program.id,
                year_level=1,
            ),
            StudentProfile(
                user_id=arts_student_user.id,
                school_id=school.id,
                student_id="ART-API-001",
                department_id=arts.id,
                program_id=arts_program.id,
                year_level=2,
            ),
        ]
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    view_students_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.VIEW_STUDENTS)
        .first()
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STUDENT-API",
        unit_name="SG Student Scope API",
        unit_type=GovernanceUnitType.SG,
        school_id=school.id,
        department_id=engineering.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(sg_unit)
    test_db.commit()

    viewer_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=viewer.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=view_students_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    response = client.get(
        "/api/governance/students",
        headers=_auth_headers(viewer),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["student_profile"]["student_id"] for item in payload] == ["ENG-API-001"]
    assert payload[0]["student_profile"]["department_name"] == "Engineering Students API"
    assert payload[0]["student_profile"]["program_name"] == "BS Engineering API"


def test_accessible_students_endpoint_supports_skip_and_limit(client, test_db):
    school = _create_school(test_db, code="STUDENT-SCOPE-PAGE")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")

    viewer = _create_user(
        test_db,
        email="scope.viewer.page@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    school_it_user = _create_user(
        test_db,
        email="scope.schoolit.page@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    engineering = Department(name="Engineering Students Page", school_id=school.id)
    arts = Department(name="Arts Students Page", school_id=school.id)
    engineering_program = Program(name="BS Engineering Page", school_id=school.id)
    arts_program = Program(name="BA Arts Page", school_id=school.id)
    engineering_program.departments.append(engineering)
    arts_program.departments.append(arts)
    test_db.add_all([engineering, arts, engineering_program, arts_program])
    test_db.commit()

    for email, student_id, year_level in [
        ("eng.page.001@example.com", "ENG-PAGE-001", 1),
        ("eng.page.002@example.com", "ENG-PAGE-002", 2),
        ("eng.page.003@example.com", "ENG-PAGE-003", 3),
    ]:
        student_user = _create_user(
            test_db,
            email=email,
            school_id=school.id,
            role_ids=[student_role.id],
        )
        test_db.add(
            StudentProfile(
                user_id=student_user.id,
                school_id=school.id,
                student_id=student_id,
                department_id=engineering.id,
                program_id=engineering_program.id,
                year_level=year_level,
            )
        )

    arts_student_user = _create_user(
        test_db,
        email="arts.page.001@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    test_db.add(
        StudentProfile(
            user_id=arts_student_user.id,
            school_id=school.id,
            student_id="ART-PAGE-001",
            department_id=arts.id,
            program_id=arts_program.id,
            year_level=1,
        )
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    view_students_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.VIEW_STUDENTS)
        .first()
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STUDENT-PAGE",
        unit_name="SG Student Scope Page",
        unit_type=GovernanceUnitType.SG,
        school_id=school.id,
        department_id=engineering.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(sg_unit)
    test_db.commit()

    viewer_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=viewer.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=view_students_permission.id,
        granted_by_user_id=school_it_user.id,
    )

    first_page_response = client.get(
        "/api/governance/students?limit=2",
        headers=_auth_headers(viewer),
    )
    assert first_page_response.status_code == 200
    first_page_payload = first_page_response.json()
    assert [item["student_profile"]["student_id"] for item in first_page_payload] == [
        "ENG-PAGE-001",
        "ENG-PAGE-002",
    ]

    second_page_response = client.get(
        "/api/governance/students?skip=2&limit=2",
        headers=_auth_headers(viewer),
    )
    assert second_page_response.status_code == 200
    second_page_payload = second_page_response.json()
    assert [item["student_profile"]["student_id"] for item in second_page_payload] == [
        "ENG-PAGE-003",
    ]


def test_dashboard_overview_endpoint_returns_lightweight_summary(client, test_db):
    school = _create_school(test_db, code="DASHBOARD-OVERVIEW")
    school_it_role = _create_role(test_db, name="school_IT")
    student_role = _create_role(test_db, name="student")

    viewer = _create_user(
        test_db,
        email="dashboard.viewer@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    school_it_user = _create_user(
        test_db,
        email="dashboard.schoolit@example.com",
        school_id=school.id,
        role_ids=[school_it_role.id],
    )

    engineering = Department(name="Dashboard Engineering", school_id=school.id)
    arts = Department(name="Dashboard Arts", school_id=school.id)
    engineering_program_a = Program(name="Dashboard BSIT", school_id=school.id)
    engineering_program_b = Program(name="Dashboard BSCS", school_id=school.id)
    arts_program = Program(name="Dashboard BA", school_id=school.id)
    engineering_program_a.departments.append(engineering)
    engineering_program_b.departments.append(engineering)
    arts_program.departments.append(arts)
    test_db.add_all(
        [
            engineering,
            arts,
            engineering_program_a,
            engineering_program_b,
            arts_program,
        ]
    )
    test_db.commit()

    for email, student_id, program_id in [
        ("dashboard.student.1@example.com", "DASH-ENG-001", engineering_program_a.id),
        ("dashboard.student.2@example.com", "DASH-ENG-002", engineering_program_b.id),
        ("dashboard.student.3@example.com", "DASH-ENG-003", engineering_program_a.id),
    ]:
        student_user = _create_user(
            test_db,
            email=email,
            school_id=school.id,
            role_ids=[student_role.id],
        )
        test_db.add(
            StudentProfile(
                user_id=student_user.id,
                school_id=school.id,
                student_id=student_id,
                department_id=engineering.id,
                program_id=program_id,
                year_level=1,
            )
        )

    arts_student_user = _create_user(
        test_db,
        email="dashboard.student.arts@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    test_db.add(
        StudentProfile(
            user_id=arts_student_user.id,
            school_id=school.id,
            student_id="DASH-ART-001",
            department_id=arts.id,
            program_id=arts_program.id,
            year_level=1,
        )
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    permission_lookup = {
        permission.permission_code: permission
        for permission in test_db.query(GovernancePermission).all()
    }

    sg_unit = GovernanceUnit(
        unit_code="DASH-SG",
        unit_name="Dashboard SG",
        unit_type=GovernanceUnitType.SG,
        school_id=school.id,
        department_id=engineering.id,
        created_by_user_id=school_it_user.id,
    )
    test_db.add(sg_unit)
    test_db.commit()

    viewer_membership = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=viewer.id,
        assigned_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=permission_lookup[PermissionCode.VIEW_STUDENTS].id,
        granted_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=permission_lookup[PermissionCode.MANAGE_ANNOUNCEMENTS].id,
        granted_by_user_id=school_it_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=viewer_membership.id,
        permission_id=permission_lookup[PermissionCode.MANAGE_MEMBERS].id,
        granted_by_user_id=school_it_user.id,
    )

    org_unit_a = GovernanceUnit(
        unit_code="DASH-ORG-A",
        unit_name="Dashboard ORG A",
        unit_type=GovernanceUnitType.ORG,
        school_id=school.id,
        parent_unit_id=sg_unit.id,
        department_id=engineering.id,
        program_id=engineering_program_a.id,
        created_by_user_id=viewer.id,
        is_active=True,
    )
    org_unit_b = GovernanceUnit(
        unit_code="DASH-ORG-B",
        unit_name="Dashboard ORG B",
        unit_type=GovernanceUnitType.ORG,
        school_id=school.id,
        parent_unit_id=sg_unit.id,
        department_id=engineering.id,
        program_id=engineering_program_b.id,
        created_by_user_id=viewer.id,
        is_active=True,
    )
    test_db.add_all([org_unit_a, org_unit_b])
    test_db.commit()

    for governance_unit, email in [
        (org_unit_a, "dashboard.org.a@example.com"),
        (org_unit_b, "dashboard.org.b@example.com"),
    ]:
        member_user = _create_user(
            test_db,
            email=email,
            school_id=school.id,
            role_ids=[student_role.id],
        )
        _create_governance_member(
            test_db,
            governance_unit_id=governance_unit.id,
            user_id=member_user.id,
            assigned_by_user_id=viewer.id,
        )

    announcement_base = datetime(2026, 3, 22, 8, 0, 0)
    test_db.add_all(
        [
            GovernanceAnnouncement(
                governance_unit_id=sg_unit.id,
                school_id=school.id,
                title=f"Dashboard Announcement {index}",
                body="Body",
                status=status_value,
                created_by_user_id=viewer.id,
                updated_by_user_id=viewer.id,
                created_at=announcement_base + timedelta(minutes=index),
                updated_at=announcement_base + timedelta(minutes=index),
            )
            for index, status_value in [
                (1, GovernanceAnnouncementStatus.DRAFT),
                (2, GovernanceAnnouncementStatus.PUBLISHED),
                (3, GovernanceAnnouncementStatus.PUBLISHED),
                (4, GovernanceAnnouncementStatus.ARCHIVED),
                (5, GovernanceAnnouncementStatus.PUBLISHED),
                (6, GovernanceAnnouncementStatus.PUBLISHED),
            ]
        ]
    )
    test_db.commit()

    response = client.get(
        f"/api/governance/units/{sg_unit.id}/dashboard-overview",
        headers=_auth_headers(viewer),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["governance_unit_id"] == sg_unit.id
    assert payload["unit_type"] == "SG"
    assert payload["total_students"] == 3
    assert payload["published_announcement_count"] == 4
    assert [item["title"] for item in payload["recent_announcements"]] == [
        "Dashboard Announcement 6",
        "Dashboard Announcement 5",
        "Dashboard Announcement 4",
        "Dashboard Announcement 3",
        "Dashboard Announcement 2",
    ]
    assert [
        (item["unit_code"], item["member_count"])
        for item in payload["child_units"]
    ] == [
        ("DASH-ORG-A", 1),
        ("DASH-ORG-B", 1),
    ]


def test_governance_access_endpoint_returns_aggregated_permission_codes(client, test_db):
    school = _create_school(test_db, code="ACCESS-ME")
    ssg_role = _create_role(test_db, name="ssg")
    ssg_user = _create_user(
        test_db,
        email="access.member@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    _seed_permission_catalog(test_db)
    manage_attendance_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ATTENDANCE)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ACCESS",
        unit_name="SSG Access",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=ssg_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=manage_attendance_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    response = client.get(
        "/api/governance/access/me",
        headers=_auth_headers(ssg_user),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == ssg_user.id
    assert payload["permission_codes"] == ["manage_attendance"]
    assert len(payload["units"]) == 1
    assert payload["units"][0]["unit_code"] == "SSG-ACCESS"


def test_governance_routes_require_supported_role_or_active_membership(client, test_db):
    school = _create_school(test_db, code="GOV-ROLE-GUARD")
    unsupported_role = _create_role(test_db, name="legacy_misc")
    unsupported_user = _create_user(
        test_db,
        email="legacy.misc@example.com",
        school_id=school.id,
        role_ids=[unsupported_role.id],
    )

    response = client.get(
        "/api/governance/access/me",
        headers=_auth_headers(unsupported_user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "A Campus Admin, student, or active governance membership is required for governance routes"
    )


def test_ssg_attendance_features_are_blocked_until_manage_attendance_is_granted(client, test_db):
    school = _create_school(test_db, code="SSG-EMPTY")
    ssg_role = _create_role(test_db, name="ssg")
    ssg_user = _create_user(
        test_db,
        email="empty.features@example.com",
        school_id=school.id,
        role_ids=[ssg_role.id],
    )

    blocked_response = client.get(
        f"/api/attendance/students/overview",
        headers=_auth_headers(ssg_user),
    )

    assert blocked_response.status_code == 403
    assert blocked_response.json()["detail"] == "Insufficient permissions"

    _seed_permission_catalog(test_db)
    manage_attendance_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ATTENDANCE)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-EMPTY-FEATURES",
        unit_name="SSG Empty Features",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=ssg_user.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    ssg_membership = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=ssg_user.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_membership.id,
        permission_id=manage_attendance_permission.id,
        granted_by_user_id=ssg_user.id,
    )

    allowed_response = client.get(
        f"/api/attendance/students/overview",
        headers=_auth_headers(ssg_user),
    )

    assert allowed_response.status_code == 200
    assert allowed_response.json() == []


def test_departments_and_programs_are_listed_only_within_the_actor_school(client, test_db):
    school_a = _create_school(test_db, code="SCOPE-A")
    school_b = _create_school(test_db, code="SCOPE-B")
    campus_admin_role = _create_role(test_db, name="campus_admin")

    campus_admin_a = _create_user(
        test_db,
        email="campus.admin.a@example.com",
        school_id=school_a.id,
        role_ids=[campus_admin_role.id],
    )
    campus_admin_b = _create_user(
        test_db,
        email="campus.admin.b@example.com",
        school_id=school_b.id,
        role_ids=[campus_admin_role.id],
    )

    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering",
        program_name="BS Computer Engineering",
        school_id=school_a.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Engineering",
        program_name="BS Computer Engineering",
        school_id=school_b.id,
    )

    departments_a_response = client.get(
        f"/api/departments/",
        headers=_auth_headers(campus_admin_a),
    )
    assert departments_a_response.status_code == 200
    assert departments_a_response.json() == [
        {
            "id": department_a.id,
            "school_id": school_a.id,
            "name": "Engineering",
        }
    ]

    departments_b_response = client.get(
        f"/api/departments/",
        headers=_auth_headers(campus_admin_b),
    )
    assert departments_b_response.status_code == 200
    assert departments_b_response.json() == [
        {
            "id": department_b.id,
            "school_id": school_b.id,
            "name": "Engineering",
        }
    ]

    cross_school_department_response = client.get(
        f"/api/departments/{department_b.id}",
        headers=_auth_headers(campus_admin_a),
    )
    assert cross_school_department_response.status_code == 404

    programs_a_response = client.get(
        f"/api/programs/",
        headers=_auth_headers(campus_admin_a),
    )
    assert programs_a_response.status_code == 200
    programs_a_payload = programs_a_response.json()
    assert len(programs_a_payload) == 1
    assert programs_a_payload[0]["id"] == program_a.id
    assert programs_a_payload[0]["school_id"] == school_a.id
    assert programs_a_payload[0]["name"] == "BS Computer Engineering"
    assert programs_a_payload[0]["department_ids"] == [department_a.id]

    programs_b_response = client.get(
        f"/api/programs/",
        headers=_auth_headers(campus_admin_b),
    )
    assert programs_b_response.status_code == 200
    programs_b_payload = programs_b_response.json()
    assert len(programs_b_payload) == 1
    assert programs_b_payload[0]["id"] == program_b.id
    assert programs_b_payload[0]["school_id"] == school_b.id
    assert programs_b_payload[0]["name"] == "BS Computer Engineering"
    assert programs_b_payload[0]["department_ids"] == [department_b.id]

    cross_school_program_response = client.get(
        f"/api/programs/{program_b.id}",
        headers=_auth_headers(campus_admin_a),
    )
    assert cross_school_program_response.status_code == 404


def test_governance_units_are_listed_only_within_the_actor_school(client, test_db):
    school_a = _create_school(test_db, code="GU-A")
    school_b = _create_school(test_db, code="GU-B")
    campus_admin_role = _create_role(test_db, name="campus_admin")

    campus_admin_a = _create_user(
        test_db,
        email="governance.admin.a@example.com",
        school_id=school_a.id,
        role_ids=[campus_admin_role.id],
    )
    campus_admin_b = _create_user(
        test_db,
        email="governance.admin.b@example.com",
        school_id=school_b.id,
        role_ids=[campus_admin_role.id],
    )

    unit_a = GovernanceUnit(
        unit_code="SSG-A",
        unit_name="Campus A SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school_a.id,
        created_by_user_id=campus_admin_a.id,
    )
    unit_b = GovernanceUnit(
        unit_code="SSG-B",
        unit_name="Campus B SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school_b.id,
        created_by_user_id=campus_admin_b.id,
    )
    test_db.add_all([unit_a, unit_b])
    test_db.commit()

    _create_governance_member(
        test_db,
        governance_unit_id=unit_a.id,
        user_id=campus_admin_a.id,
        assigned_by_user_id=campus_admin_a.id,
    )

    response = client.get(
        "/api/governance/units",
        headers=_auth_headers(campus_admin_a),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["unit_code"] for item in payload] == ["SSG-A"]
    assert payload[0]["school_id"] == school_a.id
    assert payload[0]["member_count"] == 1


def test_ssg_cannot_create_sg_with_other_school_department(client, test_db):
    school_a = _create_school(test_db, code="SG-SCOPE-A")
    school_b = _create_school(test_db, code="SG-SCOPE-B")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")

    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Scope A",
        program_name="BS Computer Engineering Scope A",
        school_id=school_a.id,
    )
    department_b, _ = _create_academic_scope(
        test_db,
        department_name="Engineering Scope B",
        program_name="BS Computer Engineering Scope B",
        school_id=school_b.id,
    )

    campus_admin = _create_user(
        test_db,
        email="scope.campus.admin@example.com",
        school_id=school_a.id,
        role_ids=[campus_admin_role.id],
    )
    ssg_officer = _create_user(
        test_db,
        email="scope.ssg.officer@example.com",
        school_id=school_a.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=ssg_officer.id,
        school_id=school_a.id,
        student_id="SG-SCOPE-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )

    create_ssg_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(campus_admin),
        json={
            "unit_code": "SSG-SCOPE",
            "unit_name": "Scope SSG",
            "unit_type": "SSG",
        },
    )
    assert create_ssg_response.status_code == 201
    ssg_unit_id = create_ssg_response.json()["id"]

    assign_member_response = client.post(
        f"/api/governance/units/{ssg_unit_id}/members",
        headers=_auth_headers(campus_admin),
        json={
            "user_id": ssg_officer.id,
            "position_title": "President",
            "permission_codes": ["create_sg"],
        },
    )
    assert assign_member_response.status_code == 201

    create_sg_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_officer),
        json={
            "unit_code": "SG-FOREIGN",
            "unit_name": "Foreign SG",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit_id,
            "department_id": department_b.id,
        },
    )

    assert create_sg_response.status_code == 400
    assert create_sg_response.json()["detail"] == "Invalid department_id for this school"


def test_sg_event_queries_are_filtered_to_their_department_scope(client, test_db):
    school = _create_school(test_db, code="SG-EVENT-SCOPE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering",
        program_name="BS Computer Engineering",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Business",
        program_name="BS Accountancy",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="sg.events.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.events.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-EVENT-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-EVENT",
        unit_name="SSG Event Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ENGINEERING",
        unit_name="Engineering SG",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    engineering_event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Assembly",
        department_ids=[department_a.id],
    )
    _create_event(
        test_db,
        school_id=school.id,
        name="Business Forum",
        department_ids=[department_b.id],
    )

    response = client.get(
        f"/api/events/?governance_context=SG",
        headers=_auth_headers(sg_user),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [engineering_event.id]


def test_org_event_queries_are_filtered_to_their_program_scope(client, test_db):
    school = _create_school(test_db, code="ORG-EVENT-SCOPE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering ORG",
        program_name="BS Computer Engineering ORG",
        school_id=school.id,
    )
    program_b = Program(name="BS Civil Engineering ORG", school_id=school.id)
    program_b.departments.append(department)
    test_db.add(program_b)
    test_db.commit()
    campus_admin = _create_user(
        test_db,
        email="org.events.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    org_user = _create_user(
        test_db,
        email="org.events.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=org_user.id,
        school_id=school.id,
        student_id="ORG-EVENT-001",
        department_id=department.id,
        program_id=program_a.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ORG-EVENT",
        unit_name="SSG ORG Event Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ORG-EVENT",
        unit_name="Engineering SG ORG",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    org_unit = GovernanceUnit(
        unit_code="ORG-CPE",
        unit_name="Computer Engineering Organization",
        unit_type=GovernanceUnitType.ORG,
        parent_unit=sg_unit,
        school_id=school.id,
        department_id=department.id,
        program_id=program_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit, org_unit])
    test_db.commit()

    org_member = _create_governance_member(
        test_db,
        governance_unit_id=org_unit.id,
        user_id=org_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=org_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    program_a_event = _create_event(
        test_db,
        school_id=school.id,
        name="Computer Engineering Congress",
        department_ids=[department.id],
        program_ids=[program_a.id],
    )
    _create_event(
        test_db,
        school_id=school.id,
        name="Civil Engineering Congress",
        department_ids=[department.id],
        program_ids=[program_b.id],
    )

    response = client.get(
        f"/api/events/?governance_context=ORG",
        headers=_auth_headers(org_user),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [program_a_event.id]


def test_sg_event_create_without_governance_context_is_forced_to_department_scope(client, test_db):
    school = _create_school(test_db, code="SG-EVENT-CREATE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Create",
        program_name="BS Computer Engineering Create",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Business Create",
        program_name="BS Accountancy Create",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="sg.create.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.create.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-CREATE-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-CREATE",
        unit_name="SSG SG Create Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ENGINEERING-CREATE",
        unit_name="Engineering SG Create Scope",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    start_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=2)
    response = client.post(
        f"/api/events/",
        headers=_auth_headers(sg_user),
        json={
            "name": "Scoped SG Event",
            "location": "Engineering Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "status": "upcoming",
            "department_ids": [department_b.id],
            "program_ids": [program_b.id],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["department_ids"] == [department_a.id]
    assert payload["program_ids"] == []

    created_event = (
        test_db.query(EventModel)
        .options(
            joinedload(EventModel.departments),
            joinedload(EventModel.programs),
        )
        .filter(EventModel.id == payload["id"])
        .first()
    )
    assert created_event is not None
    assert [department.id for department in created_event.departments] == [department_a.id]
    assert created_event.programs == []


def test_org_event_create_without_governance_context_is_forced_to_program_scope(client, test_db):
    school = _create_school(test_db, code="ORG-EVENT-CREATE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering ORG Create",
        program_name="BS Computer Engineering ORG Create",
        school_id=school.id,
    )
    program_b = Program(name="BS Civil Engineering ORG Create", school_id=school.id)
    program_b.departments.append(department)
    test_db.add(program_b)
    test_db.commit()
    campus_admin = _create_user(
        test_db,
        email="org.create.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    org_user = _create_user(
        test_db,
        email="org.create.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=org_user.id,
        school_id=school.id,
        student_id="ORG-CREATE-001",
        department_id=department.id,
        program_id=program_a.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ORG-CREATE",
        unit_name="SSG ORG Create Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ORG-CREATE",
        unit_name="Engineering SG ORG Create Scope",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    org_unit = GovernanceUnit(
        unit_code="ORG-CREATE-CPE",
        unit_name="Computer Engineering Organization Create Scope",
        unit_type=GovernanceUnitType.ORG,
        parent_unit=sg_unit,
        school_id=school.id,
        department_id=department.id,
        program_id=program_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit, org_unit])
    test_db.commit()

    org_member = _create_governance_member(
        test_db,
        governance_unit_id=org_unit.id,
        user_id=org_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=org_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    start_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=2)
    response = client.post(
        f"/api/events/",
        headers=_auth_headers(org_user),
        json={
            "name": "Scoped ORG Event",
            "location": "Program Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "status": "upcoming",
            "department_ids": [],
            "program_ids": [program_b.id],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["department_ids"] == [department.id]
    assert payload["program_ids"] == [program_a.id]

    created_event = (
        test_db.query(EventModel)
        .options(
            joinedload(EventModel.departments),
            joinedload(EventModel.programs),
        )
        .filter(EventModel.id == payload["id"])
        .first()
    )
    assert created_event is not None
    assert [department_row.id for department_row in created_event.departments] == [department.id]
    assert [program.id for program in created_event.programs] == [program_a.id]


def test_sg_event_status_cannot_start_before_scheduled_start_time(client, test_db):
    school = _create_school(test_db, code="SG-STATUS-START")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Status Start",
        program_name="BS Computer Engineering Status Start",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="status.start.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="status.start.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-STATUS-START-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-STATUS-START",
        unit_name="SSG Status Start Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STATUS-START",
        unit_name="Engineering SG Status Start",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    start_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) + timedelta(hours=1)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Future Start Event",
        department_ids=[department.id],
        start_datetime=start_datetime,
        end_datetime=start_datetime + timedelta(hours=2),
    )

    response = client.patch(
        f"/api/events/{event.id}/status?status=ongoing&governance_context=SG",
        headers=_auth_headers(sg_user),
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail.startswith("You cannot start this event yet.")
    assert start_datetime.isoformat(sep=" ", timespec="minutes") in detail

    test_db.refresh(event)
    assert event.status == ModelEventStatus.UPCOMING


def test_sg_event_status_cannot_reopen_closed_event_to_upcoming(client, test_db):
    school = _create_school(test_db, code="SG-STATUS-REOPEN")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Status Reopen",
        program_name="BS Computer Engineering Status Reopen",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="status.reopen.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="status.reopen.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-STATUS-REOPEN-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-STATUS-REOPEN",
        unit_name="SSG Status Reopen Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STATUS-REOPEN",
        unit_name="Engineering SG Status Reopen",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    end_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) - timedelta(hours=1)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Closed Event",
        department_ids=[department.id],
        start_datetime=end_datetime - timedelta(hours=2),
        end_datetime=end_datetime,
        sign_out_grace_minutes=0,
    )
    event.status = ModelEventStatus.COMPLETED
    test_db.commit()

    response = client.patch(
        f"/api/events/{event.id}/status?status=upcoming&governance_context=SG",
        headers=_auth_headers(sg_user),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "You cannot reopen this event because it is already completed."
    )

    test_db.refresh(event)
    assert event.status == ModelEventStatus.COMPLETED


def test_sg_event_status_reopen_during_sign_out_syncs_back_to_ongoing(client, test_db):
    school = _create_school(test_db, code="SG-STATUS-REOPEN-SIGNOUT")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Status Reopen Signout",
        program_name="BS Computer Engineering Status Reopen Signout",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="status.reopen.signout.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="status.reopen.signout.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-STATUS-REOPEN-SIGNOUT-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-STATUS-REOPEN-SIGNOUT",
        unit_name="SSG Status Reopen Signout Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STATUS-REOPEN-SIGNOUT",
        unit_name="Engineering SG Status Reopen Signout",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    now_local = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Sign-Out Window Event",
        department_ids=[department.id],
        start_datetime=now_local - timedelta(hours=2),
        end_datetime=now_local - timedelta(minutes=5),
        sign_out_grace_minutes=15,
    )
    event.status = ModelEventStatus.CANCELLED
    test_db.commit()

    response = client.patch(
        f"/api/events/{event.id}/status?status=upcoming&governance_context=SG",
        headers=_auth_headers(sg_user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ongoing"

    test_db.refresh(event)
    assert event.status == ModelEventStatus.ONGOING


def test_sg_event_status_reopen_closed_cancelled_event_syncs_to_completed(client, test_db):
    school = _create_school(test_db, code="SG-STATUS-REOPEN-CLOSED-CANCELLED")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Status Reopen Closed Cancelled",
        program_name="BS Computer Engineering Status Reopen Closed Cancelled",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="status.reopen.closed.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="status.reopen.closed.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-STATUS-REOPEN-CLOSED-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-STATUS-REOPEN-CLOSED-CANCELLED",
        unit_name="SSG Status Reopen Closed Cancelled Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-STATUS-REOPEN-CLOSED-CANCELLED",
        unit_name="Engineering SG Status Reopen Closed Cancelled",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    now_local = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Closed Cancelled Event",
        department_ids=[department.id],
        start_datetime=now_local - timedelta(hours=3),
        end_datetime=now_local - timedelta(hours=1),
        sign_out_grace_minutes=0,
    )
    event.status = ModelEventStatus.CANCELLED
    test_db.commit()

    response = client.patch(
        f"/api/events/{event.id}/status?status=upcoming&governance_context=SG",
        headers=_auth_headers(sg_user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    test_db.refresh(event)
    assert event.status == ModelEventStatus.COMPLETED


def test_sg_event_default_override_and_reset_are_used_for_future_events(client, test_db):
    school = _create_school(test_db, code="SG-EVENT-DEFAULTS")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Event Defaults",
        program_name="BS Computer Engineering Event Defaults",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="sg.defaults.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.defaults.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-DEFAULTS-001",
        department_id=department.id,
        program_id=program.id,
    )
    test_db.add(
        SchoolSetting(
            school_id=school.id,
            event_default_early_check_in_minutes=30,
            event_default_late_threshold_minutes=10,
            event_default_sign_out_grace_minutes=20,
        )
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-DEFAULTS",
        unit_name="SSG SG Defaults",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-DEFAULTS",
        unit_name="Engineering SG Defaults",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    defaults_response = client.put(
        f"/api/governance/units/{sg_unit.id}/event-defaults",
        headers=_auth_headers(sg_user),
        json={
            "early_check_in_minutes": 50,
            "late_threshold_minutes": 15,
            "sign_out_grace_minutes": 35,
        },
    )

    assert defaults_response.status_code == 200
    defaults_payload = defaults_response.json()
    assert defaults_payload["inherits_school_defaults"] is False
    assert defaults_payload["override_early_check_in_minutes"] == 50
    assert defaults_payload["effective_early_check_in_minutes"] == 50
    assert defaults_payload["effective_late_threshold_minutes"] == 15
    assert defaults_payload["effective_sign_out_grace_minutes"] == 35

    start_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=2)
    create_override_response = client.post(
        f"/api/events/?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "name": "SG Override Default Event",
            "location": "Engineering Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
        },
    )

    assert create_override_response.status_code == 201
    override_event_payload = create_override_response.json()
    assert override_event_payload["early_check_in_minutes"] == 50
    assert override_event_payload["late_threshold_minutes"] == 15
    assert override_event_payload["sign_out_grace_minutes"] == 35

    reset_response = client.put(
        f"/api/governance/units/{sg_unit.id}/event-defaults",
        headers=_auth_headers(sg_user),
        json={
            "early_check_in_minutes": None,
            "late_threshold_minutes": None,
            "sign_out_grace_minutes": None,
        },
    )

    assert reset_response.status_code == 200
    reset_payload = reset_response.json()
    assert reset_payload["inherits_school_defaults"] is True
    assert reset_payload["effective_early_check_in_minutes"] == 30
    assert reset_payload["effective_late_threshold_minutes"] == 10
    assert reset_payload["effective_sign_out_grace_minutes"] == 20

    create_inherited_response = client.post(
        f"/api/events/?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "name": "SG Inherited Default Event",
            "location": "Engineering Hall",
            "start_datetime": (start_datetime + timedelta(days=1)).isoformat(),
            "end_datetime": (end_datetime + timedelta(days=1)).isoformat(),
        },
    )

    assert create_inherited_response.status_code == 201
    inherited_event_payload = create_inherited_response.json()
    assert inherited_event_payload["early_check_in_minutes"] == 30
    assert inherited_event_payload["late_threshold_minutes"] == 10
    assert inherited_event_payload["sign_out_grace_minutes"] == 20


def test_org_event_default_override_is_used_for_future_events(client, test_db):
    school = _create_school(test_db, code="ORG-EVENT-DEFAULTS")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering ORG Defaults",
        program_name="BS Computer Engineering ORG Defaults",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="org.defaults.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    org_user = _create_user(
        test_db,
        email="org.defaults.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=org_user.id,
        school_id=school.id,
        student_id="ORG-DEFAULTS-001",
        department_id=department.id,
        program_id=program.id,
    )
    test_db.add(
        SchoolSetting(
            school_id=school.id,
            event_default_early_check_in_minutes=33,
            event_default_late_threshold_minutes=9,
            event_default_sign_out_grace_minutes=19,
        )
    )
    test_db.commit()

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ORG-DEFAULTS",
        unit_name="SSG ORG Defaults",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ORG-DEFAULTS",
        unit_name="Engineering SG ORG Defaults",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    org_unit = GovernanceUnit(
        unit_code="ORG-DEFAULTS-CPE",
        unit_name="Computer Engineering ORG Defaults",
        unit_type=GovernanceUnitType.ORG,
        parent_unit=sg_unit,
        school_id=school.id,
        department_id=department.id,
        program_id=program.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit, org_unit])
    test_db.commit()

    org_member = _create_governance_member(
        test_db,
        governance_unit_id=org_unit.id,
        user_id=org_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=org_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    defaults_response = client.put(
        f"/api/governance/units/{org_unit.id}/event-defaults",
        headers=_auth_headers(org_user),
        json={
            "early_check_in_minutes": 55,
            "late_threshold_minutes": 17,
            "sign_out_grace_minutes": 28,
        },
    )

    assert defaults_response.status_code == 200
    defaults_payload = defaults_response.json()
    assert defaults_payload["unit_type"] == "ORG"
    assert defaults_payload["effective_early_check_in_minutes"] == 55
    assert defaults_payload["effective_late_threshold_minutes"] == 17
    assert defaults_payload["effective_sign_out_grace_minutes"] == 28

    start_datetime = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0) + timedelta(days=1)
    end_datetime = start_datetime + timedelta(hours=2)
    create_response = client.post(
        f"/api/events/?governance_context=ORG",
        headers=_auth_headers(org_user),
        json={
            "name": "ORG Override Default Event",
            "location": "Program Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
        },
    )

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["department_ids"] == [department.id]
    assert payload["program_ids"] == [program.id]
    assert payload["early_check_in_minutes"] == 55
    assert payload["late_threshold_minutes"] == 17
    assert payload["sign_out_grace_minutes"] == 28


def test_sg_event_update_without_governance_context_rejects_out_of_scope_event(client, test_db):
    school = _create_school(test_db, code="SG-EVENT-UPDATE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Update",
        program_name="BS Computer Engineering Update",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Business Update",
        program_name="BS Accountancy Update",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="sg.update.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.update.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-UPDATE-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )

    _seed_permission_catalog(test_db)
    manage_events_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_EVENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-UPDATE",
        unit_name="SSG SG Update Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ENGINEERING-UPDATE",
        unit_name="Engineering SG Update Scope",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_events_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    out_of_scope_event = _create_event(
        test_db,
        school_id=school.id,
        name="Business Assembly Update",
        department_ids=[department_b.id],
    )

    response = client.patch(
        f"/api/events/{out_of_scope_event.id}",
        headers=_auth_headers(sg_user),
        json={"name": "Edited by SG"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Event not found"

    test_db.refresh(out_of_scope_event)
    assert out_of_scope_event.name == "Business Assembly Update"


def test_sg_manual_attendance_blocks_students_outside_department_scope(client, test_db):
    school = _create_school(test_db, code="SG-ATTEND-SCOPE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Attendance",
        program_name="BS Computer Engineering Attendance",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Business Attendance",
        program_name="BS Accountancy Attendance",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="sg.attendance.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="sg.attendance.user@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    allowed_student = _create_user(
        test_db,
        email="allowed.student@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    blocked_student = _create_user(
        test_db,
        email="blocked.student@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-ATTEND-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )
    allowed_profile = _create_student_profile(
        test_db,
        user_id=allowed_student.id,
        school_id=school.id,
        student_id="SG-ATTEND-ALLOWED",
        department_id=department_a.id,
        program_id=program_a.id,
    )
    blocked_profile = _create_student_profile(
        test_db,
        user_id=blocked_student.id,
        school_id=school.id,
        student_id="SG-ATTEND-BLOCKED",
        department_id=department_b.id,
        program_id=program_b.id,
    )

    _seed_permission_catalog(test_db)
    manage_attendance_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ATTENDANCE)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-ATTEND",
        unit_name="SSG Attendance Scope",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ATTEND",
        unit_name="Engineering SG Attendance",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_attendance_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Attendance Event",
        department_ids=[department_a.id],
    )

    allowed_response = client.post(
        f"/api/attendance/manual?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "event_id": event.id,
            "student_id": allowed_profile.student_id,
        },
    )
    assert allowed_response.status_code == 200

    blocked_response = client.post(
        f"/api/attendance/manual?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "event_id": event.id,
            "student_id": blocked_profile.student_id,
        },
    )
    assert blocked_response.status_code == 404
    assert blocked_response.json()["detail"] == "Student not found"


def test_sg_manual_attendance_sign_out_requires_early_open_and_preserves_status_audit_fields(
    client,
    test_db,
):
    school = _create_school(test_db, code="SG-ATTEND-OVERRIDE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Override",
        program_name="BS Computer Engineering Override",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="attendance.override.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="attendance.override.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    allowed_student = _create_user(
        test_db,
        email="attendance.override.allowed@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-OVERRIDE-001",
        department_id=department.id,
        program_id=program.id,
    )
    allowed_profile = _create_student_profile(
        test_db,
        user_id=allowed_student.id,
        school_id=school.id,
        student_id="SG-OVERRIDE-ALLOWED",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_attendance_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ATTENDANCE)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-OVERRIDE",
        unit_name="SSG Attendance Override",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-OVERRIDE",
        unit_name="Engineering SG Override",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_attendance_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Override Event",
        department_ids=[department.id],
        start_datetime=manila_now - timedelta(minutes=5),
        end_datetime=manila_now + timedelta(hours=1),
        late_threshold_minutes=15,
        sign_out_grace_minutes=10,
    )

    check_in_response = client.post(
        f"/api/attendance/manual?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "event_id": event.id,
            "student_id": allowed_profile.student_id,
        },
    )
    assert check_in_response.status_code == 200
    assert check_in_response.json()["action"] == "time_in"

    attendance = (
        test_db.query(AttendanceModel)
        .filter(
            AttendanceModel.event_id == event.id,
            AttendanceModel.student_id == allowed_profile.id,
        )
        .one()
    )
    assert attendance.status == "late"
    assert attendance.check_in_status == "late"
    assert attendance.check_out_status is None
    assert attendance.time_out is None

    blocked_sign_out_response = client.post(
        f"/api/attendance/manual?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "event_id": event.id,
            "student_id": allowed_profile.student_id,
        },
    )
    assert blocked_sign_out_response.status_code == 409
    blocked_detail = blocked_sign_out_response.json()["detail"]
    assert blocked_detail["action"] == "sign_out"
    assert blocked_detail["reason_code"] == "sign_out_not_open_yet"

    open_sign_out_response = client.post(
        f"/api/events/{event.id}/sign-out/open-early?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={"use_sign_out_grace_minutes": True},
    )
    assert open_sign_out_response.status_code == 200
    assert open_sign_out_response.json()["sign_out_grace_minutes"] == 10
    test_db.refresh(event)
    end_delta_seconds = abs((event.end_datetime - manila_now).total_seconds())
    assert end_delta_seconds <= 5
    assert event.sign_out_grace_minutes == 10

    sign_out_response = client.post(
        f"/api/attendance/manual?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={
            "event_id": event.id,
            "student_id": allowed_profile.student_id,
        },
    )
    assert sign_out_response.status_code == 200
    sign_out_payload = sign_out_response.json()
    assert sign_out_payload["action"] == "time_out"
    assert sign_out_payload["duration_minutes"] >= 0

    test_db.refresh(attendance)
    assert attendance.time_out is not None
    assert attendance.check_in_status == "late"
    assert attendance.check_out_status == "present"
    assert attendance.status == "late"


def test_sg_sign_out_early_cannot_open_before_event_start(client, test_db):
    school = _create_school(test_db, code="SG-OVERRIDE-FUTURE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Override Future",
        program_name="BS Computer Engineering Override Future",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="attendance.future.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="attendance.future.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-OVERRIDE-FUTURE-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_attendance_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ATTENDANCE)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-SG-FUTURE",
        unit_name="SSG Attendance Future",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-FUTURE",
        unit_name="Engineering SG Future",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_attendance_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Future Override Event",
        department_ids=[department.id],
        start_datetime=manila_now + timedelta(minutes=30),
        end_datetime=manila_now + timedelta(hours=2),
        early_check_in_minutes=10,
        late_threshold_minutes=15,
        sign_out_grace_minutes=10,
    )

    response = client.post(
        f"/api/events/{event.id}/sign-out/open-early?governance_context=SG",
        headers=_auth_headers(sg_user),
        json={"use_sign_out_grace_minutes": False, "close_after_minutes": 12},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Early sign-out can only be opened after the event has started."


def test_governance_announcements_are_persisted_per_unit(client, test_db):
    school = _create_school(test_db, code="SG-ANNOUNCE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Announcements",
        program_name="BS Computer Engineering Announcements",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="announcement.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="announcement.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-ANNOUNCE-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    manage_announcements_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_ANNOUNCEMENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-ANNOUNCE",
        unit_name="SSG Announcements",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-ANNOUNCE",
        unit_name="Engineering SG Announcements",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_announcements_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    create_response = client.post(
        f"/api/governance/units/{sg_unit.id}/announcements",
        headers=_auth_headers(sg_user),
        json={
            "title": "Engineering Week",
            "body": "Engineering Week has been published.",
            "status": "published",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["governance_unit_id"] == sg_unit.id
    assert created["status"] == "published"

    list_response = client.get(
        f"/api/governance/units/{sg_unit.id}/announcements",
        headers=_auth_headers(sg_user),
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["title"] == "Engineering Week"

    update_response = client.patch(
        f"/api/governance/announcements/{created['id']}",
        headers=_auth_headers(sg_user),
        json={"status": "archived"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "archived"

    delete_response = client.delete(
        f"/api/governance/announcements/{created['id']}",
        headers=_auth_headers(sg_user),
    )
    assert delete_response.status_code == 204


def test_campus_admin_announcement_monitor_is_school_scoped(client, test_db):
    school_a = _create_school(test_db, code="ANN-MON-A")
    school_b = _create_school(test_db, code="ANN-MON-B")
    campus_admin_role = _create_role(test_db, name="campus_admin")

    campus_admin_a = _create_user(
        test_db,
        email="announcement.monitor.a@example.com",
        school_id=school_a.id,
        role_ids=[campus_admin_role.id],
    )
    campus_admin_b = _create_user(
        test_db,
        email="announcement.monitor.b@example.com",
        school_id=school_b.id,
        role_ids=[campus_admin_role.id],
    )

    ssg_a = GovernanceUnit(
        unit_code="SSG-MON-A",
        unit_name="Campus A SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school_a.id,
        created_by_user_id=campus_admin_a.id,
    )
    sg_a = GovernanceUnit(
        unit_code="SG-MON-A",
        unit_name="Campus A Engineering SG",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_a,
        school_id=school_a.id,
        created_by_user_id=campus_admin_a.id,
    )
    ssg_b = GovernanceUnit(
        unit_code="SSG-MON-B",
        unit_name="Campus B SSG",
        unit_type=GovernanceUnitType.SSG,
        school_id=school_b.id,
        created_by_user_id=campus_admin_b.id,
    )
    test_db.add_all([ssg_a, sg_a, ssg_b])
    test_db.commit()

    test_db.add_all(
        [
            GovernanceAnnouncement(
                governance_unit_id=ssg_a.id,
                school_id=school_a.id,
                title="Campus A Published",
                body="Campus A published announcement.",
                status=GovernanceAnnouncementStatus.PUBLISHED,
                created_by_user_id=campus_admin_a.id,
                updated_by_user_id=campus_admin_a.id,
            ),
            GovernanceAnnouncement(
                governance_unit_id=sg_a.id,
                school_id=school_a.id,
                title="Campus A Draft",
                body="Campus A draft announcement.",
                status=GovernanceAnnouncementStatus.DRAFT,
                created_by_user_id=campus_admin_a.id,
                updated_by_user_id=campus_admin_a.id,
            ),
            GovernanceAnnouncement(
                governance_unit_id=ssg_b.id,
                school_id=school_b.id,
                title="Campus B Published",
                body="Campus B published announcement.",
                status=GovernanceAnnouncementStatus.PUBLISHED,
                created_by_user_id=campus_admin_b.id,
                updated_by_user_id=campus_admin_b.id,
            ),
        ]
    )
    test_db.commit()

    response = client.get(
        "/api/governance/announcements/monitor?status=published",
        headers=_auth_headers(campus_admin_a),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Campus A Published"
    assert payload[0]["governance_unit_code"] == "SSG-MON-A"
    assert payload[0]["governance_unit_type"] == "SSG"


def test_governance_student_notes_require_manage_students_and_stay_scoped(client, test_db):
    school = _create_school(test_db, code="SG-NOTES")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Notes",
        program_name="BS Computer Engineering Notes",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Education Notes",
        program_name="BSED Notes",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="notes.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    sg_user = _create_user(
        test_db,
        email="notes.sg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    allowed_student = _create_user(
        test_db,
        email="notes.allowed@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    blocked_student = _create_user(
        test_db,
        email="notes.blocked@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=sg_user.id,
        school_id=school.id,
        student_id="SG-NOTES-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )
    allowed_profile = _create_student_profile(
        test_db,
        user_id=allowed_student.id,
        school_id=school.id,
        student_id="SG-NOTES-ALLOWED",
        department_id=department_a.id,
        program_id=program_a.id,
    )
    blocked_profile = _create_student_profile(
        test_db,
        user_id=blocked_student.id,
        school_id=school.id,
        student_id="SG-NOTES-BLOCKED",
        department_id=department_b.id,
        program_id=program_b.id,
    )

    _seed_permission_catalog(test_db)
    manage_students_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.MANAGE_STUDENTS)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-NOTES",
        unit_name="SSG Notes",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    sg_unit = GovernanceUnit(
        unit_code="SG-NOTES",
        unit_name="Engineering SG Notes",
        unit_type=GovernanceUnitType.SG,
        parent_unit=ssg_unit,
        school_id=school.id,
        department_id=department_a.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add_all([ssg_unit, sg_unit])
    test_db.commit()

    sg_member = _create_governance_member(
        test_db,
        governance_unit_id=sg_unit.id,
        user_id=sg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=sg_member.id,
        permission_id=manage_students_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    save_response = client.put(
        f"/api/governance/units/{sg_unit.id}/student-notes/{allowed_profile.id}",
        headers=_auth_headers(sg_user),
        json={"tags": ["Priority", "Officer Candidate"], "notes": "Track for SG mentoring."},
    )
    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["tags"] == ["Priority", "Officer Candidate"]
    assert payload["notes"] == "Track for SG mentoring."

    read_response = client.get(
        f"/api/governance/units/{sg_unit.id}/student-notes/{allowed_profile.id}",
        headers=_auth_headers(sg_user),
    )
    assert read_response.status_code == 200
    assert read_response.json()["tags"] == ["Priority", "Officer Candidate"]

    blocked_response = client.get(
        f"/api/governance/units/{sg_unit.id}/student-notes/{blocked_profile.id}",
        headers=_auth_headers(sg_user),
    )
    assert blocked_response.status_code == 404
    assert blocked_response.json()["detail"] == "Student not found in this governance scope"


def test_student_event_list_shows_all_upcoming_events_but_keeps_active_scope_filters(client, test_db):
    school = _create_school(test_db, code="STU-EVENT-SCOPE")
    student_role = _create_role(test_db, name="student")
    department_a, program_a = _create_academic_scope(
        test_db,
        department_name="Engineering Event Scope",
        program_name="BS Computer Engineering Event Scope",
        school_id=school.id,
    )
    department_b, program_b = _create_academic_scope(
        test_db,
        department_name="Education Event Scope",
        program_name="BSED Event Scope",
        school_id=school.id,
    )
    alternate_program = Program(
        name="BS Civil Engineering Event Scope",
        school_id=school.id,
    )
    alternate_program.departments.append(department_a)
    test_db.add(alternate_program)
    test_db.commit()

    student_user = _create_user(
        test_db,
        email="student.scope@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=student_user.id,
        school_id=school.id,
        student_id="STUDENT-SCOPE-001",
        department_id=department_a.id,
        program_id=program_a.id,
    )

    upcoming_start = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None) + timedelta(days=1)
    upcoming_end = upcoming_start + timedelta(hours=2)

    school_event = _create_event(
        test_db,
        school_id=school.id,
        name="School-Wide Event",
        start_datetime=upcoming_start,
        end_datetime=upcoming_end,
    )
    department_event = _create_event(
        test_db,
        school_id=school.id,
        name="Engineering Event",
        department_ids=[department_a.id],
        start_datetime=upcoming_start,
        end_datetime=upcoming_end,
    )
    program_event = _create_event(
        test_db,
        school_id=school.id,
        name="Computer Engineering Event",
        department_ids=[department_a.id],
        program_ids=[program_a.id],
        start_datetime=upcoming_start,
        end_datetime=upcoming_end,
    )
    upcoming_same_department_program_event = _create_event(
        test_db,
        school_id=school.id,
        name="Civil Engineering Event",
        department_ids=[department_a.id],
        program_ids=[alternate_program.id],
        start_datetime=upcoming_start,
        end_datetime=upcoming_end,
    )
    upcoming_other_department_event = _create_event(
        test_db,
        school_id=school.id,
        name="Education Event",
        department_ids=[department_b.id],
        program_ids=[program_b.id],
        start_datetime=upcoming_start,
        end_datetime=upcoming_end,
    )
    hidden_other_department_ongoing_event = _create_event(
        test_db,
        school_id=school.id,
        name="Education Ongoing Event",
        department_ids=[department_b.id],
        program_ids=[program_b.id],
    )

    list_response = client.get(
        f"/api/events/",
        headers=_auth_headers(student_user),
    )
    assert list_response.status_code == 200
    names = {item["name"] for item in list_response.json()}
    assert names == {
        school_event.name,
        department_event.name,
        program_event.name,
        upcoming_same_department_program_event.name,
        upcoming_other_department_event.name,
    }
    assert hidden_other_department_ongoing_event.name not in names

    detail_response = client.get(
        f"/api/events/{hidden_other_department_ongoing_event.id}",
        headers=_auth_headers(student_user),
    )
    assert detail_response.status_code == 404


def test_delete_governance_unit_soft_deactivates_sg(client, test_db):
    school = _create_school(test_db, code="SG-DELETE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    student_role = _create_role(test_db, name="student")
    department, program = _create_academic_scope(
        test_db,
        department_name="Engineering Delete",
        program_name="BS Computer Engineering Delete",
        school_id=school.id,
    )
    campus_admin = _create_user(
        test_db,
        email="delete.admin@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )
    ssg_user = _create_user(
        test_db,
        email="delete.ssg@example.com",
        school_id=school.id,
        role_ids=[student_role.id],
    )
    _create_student_profile(
        test_db,
        user_id=ssg_user.id,
        school_id=school.id,
        student_id="SSG-DELETE-001",
        department_id=department.id,
        program_id=program.id,
    )

    _seed_permission_catalog(test_db)
    create_sg_permission = (
        test_db.query(GovernancePermission)
        .filter(GovernancePermission.permission_code == PermissionCode.CREATE_SG)
        .first()
    )

    ssg_unit = GovernanceUnit(
        unit_code="SSG-DELETE",
        unit_name="SSG Delete",
        unit_type=GovernanceUnitType.SSG,
        school_id=school.id,
        created_by_user_id=campus_admin.id,
    )
    test_db.add(ssg_unit)
    test_db.commit()

    ssg_member = _create_governance_member(
        test_db,
        governance_unit_id=ssg_unit.id,
        user_id=ssg_user.id,
        assigned_by_user_id=campus_admin.id,
    )
    _grant_member_permission(
        test_db,
        governance_member_id=ssg_member.id,
        permission_id=create_sg_permission.id,
        granted_by_user_id=campus_admin.id,
    )

    create_response = client.post(
        "/api/governance/units",
        headers=_auth_headers(ssg_user),
        json={
            "unit_code": "SG-DELETE",
            "unit_name": "Engineering SG Delete",
            "unit_type": "SG",
            "parent_unit_id": ssg_unit.id,
            "department_id": department.id,
        },
    )
    assert create_response.status_code == 201
    sg_unit_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/governance/units/{sg_unit_id}",
        headers=_auth_headers(ssg_user),
    )
    assert delete_response.status_code == 204

    list_response = client.get(
        f"/api/governance/units?unit_type=SG&parent_unit_id={ssg_unit.id}",
        headers=_auth_headers(ssg_user),
    )
    assert list_response.status_code == 200
    assert list_response.json() == []


def test_campus_admin_create_event_without_near_start_override_when_full_early_window_is_available(
    client,
    test_db,
):
    school = _create_school(test_db, code="EVENT-NO-OVERRIDE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    campus_admin = _create_user(
        test_db,
        email="event.no.override@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    start_datetime = manila_now + timedelta(hours=2)
    end_datetime = start_datetime + timedelta(hours=1)

    response = client.post(
        f"/api/events/",
        headers=_auth_headers(campus_admin),
        json={
            "name": "Far Future Event",
            "location": "Campus Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "early_check_in_minutes": 30,
            "late_threshold_minutes": 10,
            "sign_out_grace_minutes": 20,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["present_until_override_at"] is None
    assert payload["late_until_override_at"] is None


def test_campus_admin_create_event_adds_near_start_attendance_override_windows(
    client,
    test_db,
):
    school = _create_school(test_db, code="EVENT-WITH-OVERRIDE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    campus_admin = _create_user(
        test_db,
        email="event.with.override@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    start_datetime = manila_now + timedelta(minutes=1)
    end_datetime = manila_now + timedelta(minutes=71)

    response = client.post(
        f"/api/events/",
        headers=_auth_headers(campus_admin),
        json={
            "name": "Near Start Event",
            "location": "Campus Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "early_check_in_minutes": 30,
            "late_threshold_minutes": 10,
            "sign_out_grace_minutes": 20,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["present_until_override_at"] is not None
    assert payload["late_until_override_at"] is not None

    present_until_override_at = datetime.fromisoformat(payload["present_until_override_at"])
    late_until_override_at = datetime.fromisoformat(payload["late_until_override_at"])

    assert abs((present_until_override_at - (manila_now + timedelta(minutes=30))).total_seconds()) <= 5
    assert abs((late_until_override_at - (manila_now + timedelta(minutes=40))).total_seconds()) <= 5


def test_campus_admin_create_event_rejects_near_start_override_when_start_is_already_in_the_past(
    client,
    test_db,
):
    school = _create_school(test_db, code="EVENT-PAST-START")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    campus_admin = _create_user(
        test_db,
        email="event.past.start@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    start_datetime = manila_now - timedelta(minutes=1)
    end_datetime = manila_now + timedelta(minutes=70)

    response = client.post(
        f"/api/events/",
        headers=_auth_headers(campus_admin),
        json={
            "name": "Past Start Event",
            "location": "Campus Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "early_check_in_minutes": 30,
            "late_threshold_minutes": 10,
            "sign_out_grace_minutes": 20,
        },
    )

    assert response.status_code == 400
    assert "start time is already in the past" in response.json()["detail"]


def test_campus_admin_create_event_rejects_too_short_near_start_override_window(
    client,
    test_db,
):
    school = _create_school(test_db, code="EVENT-SHORT-OVERRIDE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    campus_admin = _create_user(
        test_db,
        email="event.short.override@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    start_datetime = manila_now + timedelta(minutes=1)
    end_datetime = manila_now + timedelta(minutes=59)

    response = client.post(
        f"/api/events/",
        headers=_auth_headers(campus_admin),
        json={
            "name": "Short Event",
            "location": "Campus Hall",
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "early_check_in_minutes": 30,
            "late_threshold_minutes": 10,
            "sign_out_grace_minutes": 20,
        },
    )

    assert response.status_code == 400
    assert "too short for the near-start attendance override" in response.json()["detail"]


def test_campus_admin_update_event_can_add_and_clear_near_start_attendance_override_windows(
    client,
    test_db,
):
    school = _create_school(test_db, code="EVENT-UPDATE-OVERRIDE")
    campus_admin_role = _create_role(test_db, name="campus_admin")
    campus_admin = _create_user(
        test_db,
        email="event.update.override@example.com",
        school_id=school.id,
        role_ids=[campus_admin_role.id],
    )

    manila_now = datetime.now(ZoneInfo("Asia/Manila")).replace(tzinfo=None, microsecond=0)
    event = _create_event(
        test_db,
        school_id=school.id,
        name="Editable Event",
        start_datetime=manila_now + timedelta(hours=2),
        end_datetime=manila_now + timedelta(hours=3),
        early_check_in_minutes=30,
        late_threshold_minutes=10,
        sign_out_grace_minutes=20,
    )

    add_override_response = client.patch(
        f"/api/events/{event.id}",
        headers=_auth_headers(campus_admin),
        json={
            "start_datetime": (manila_now + timedelta(minutes=1)).isoformat(),
            "end_datetime": (manila_now + timedelta(minutes=71)).isoformat(),
        },
    )

    assert add_override_response.status_code == 200
    add_override_payload = add_override_response.json()
    assert add_override_payload["present_until_override_at"] is not None
    assert add_override_payload["late_until_override_at"] is not None

    clear_override_response = client.patch(
        f"/api/events/{event.id}",
        headers=_auth_headers(campus_admin),
        json={
            "start_datetime": (manila_now + timedelta(hours=4)).isoformat(),
            "end_datetime": (manila_now + timedelta(hours=5)).isoformat(),
        },
    )

    assert clear_override_response.status_code == 200
    clear_override_payload = clear_override_response.json()
    assert clear_override_payload["present_until_override_at"] is None
    assert clear_override_payload["late_until_override_at"] is None


