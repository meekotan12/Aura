"""Use: Tests main API flows across the backend.
Where to use: Use this when running `pytest` to check that this backend behavior still works.
Role: Test layer. It protects the app from regressions.
"""

import json
from datetime import datetime, timedelta

from app.models import (
    Department,
    Event,
    PasswordResetRequest,
    Program,
    Role,
    School,
    SchoolAuditLog,
    SchoolSetting,
    StudentProfile,
    User,
    UserRole,
)
from app.routers import users as users_router
from app.core.security import create_access_token, verify_password
from app.utils.passwords import hash_password_bcrypt


def _create_school(test_db, *, code: str) -> School:
    school = School(
        name=f"Test School {code}",
        school_name=f"Test School {code}",
        school_code=code,
        address="Test Address",
    )
    test_db.add(school)
    test_db.commit()
    return school


def _get_or_create_role(test_db, *, name: str) -> Role:
    role = test_db.query(Role).filter(Role.name == name).first()
    if role is None:
        role = Role(name=name)
        test_db.add(role)
        test_db.commit()
    return role


def _create_user_with_role(
    test_db,
    *,
    email: str,
    role_name: str,
    password: str,
    school_id: int | None = None,
    first_name: str = "Test",
    last_name: str = "User",
    must_change_password: bool = False,
    is_active: bool = True,
) -> User:
    role = _get_or_create_role(test_db, name=role_name)
    user = User(
        email=email,
        school_id=school_id,
        first_name=first_name,
        last_name=last_name,
        must_change_password=must_change_password,
        is_active=is_active,
    )
    user.set_password(password)
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


def test_create_user_api_requires_auth(client):
    response = client.post(
        f"/api/users/",
        json={
            "email": "apitest@example.com",
            "password": "StrongPassword123!",
            "first_name": "API",
            "middle_name": "",
            "last_name": "Test",
                "roles": ["student"]
        }
    )
    assert response.status_code == 401


def test_user_authentication(client, test_db):
    school = _create_school(test_db, code="AUTH-SCH")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="auth@example.com",
        school_id=school.id,
        first_name="Auth",
        last_name="Test",
        must_change_password=False,
    )
    user.set_password("AuthPassword123!")
    test_db.add(user)
    test_db.commit()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_db.add(user_role)
    test_db.commit()

    response = client.post(
        "/token",
        data={
            "username": "auth@example.com",
            "password": "AuthPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    response = client.post(
        "/token",
        data={
            "username": "auth@example.com",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401


def test_protected_endpoint(client, test_db):
    school = _create_school(test_db, code="PROTECTED-SCH")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="student@example.com",
        school_id=school.id,
        first_name="Student",
        last_name="Test",
        must_change_password=False,
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()

    user_role = UserRole(user_id=user.id, role_id=role.id)
    test_db.add(user_role)
    test_db.commit()

    token = create_access_token({"sub": user.email})

    response = client.get(
        f"/api/users/me/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "student@example.com"

    response = client.get(f"/api/users/me/")
    assert response.status_code == 401


def test_users_router_supports_canonical_api_prefix(client, test_db):
    school = _create_school(test_db, code="API-USERS")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="canonical.users@example.com",
        school_id=school.id,
        first_name="Canonical",
        last_name="User",
        must_change_password=False,
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})
    response = client.get(
        "/api/users/me/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "canonical.users@example.com"


def test_security_router_supports_canonical_api_prefix(client, test_db):
    school = _create_school(test_db, code="API-SECURITY")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="canonical.security@example.com",
        school_id=school.id,
        first_name="Canonical",
        last_name="Security",
        must_change_password=False,
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})
    response = client.get(
        "/api/auth/security/mfa-status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == user.id
    assert "mfa_enabled" in payload


def test_legacy_users_router_alias_is_removed(client, test_db):
    school = _create_school(test_db, code="LEGACY-USERS-REMOVED")
    user = _create_user_with_role(
        test_db,
        email="legacy.users.removed@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
    )

    response = client.get(
        "/users/me/",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_legacy_security_router_alias_is_removed(client, test_db):
    school = _create_school(test_db, code="LEGACY-SECURITY-REMOVED")
    user = _create_user_with_role(
        test_db,
        email="legacy.security.removed@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
    )

    response = client.get(
        "/auth/security/mfa-status",
        headers=_auth_headers(user),
    )

    assert response.status_code == 404


def test_health_endpoint_reports_pool_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"]["ok"] is True
    assert "pool" in payload
    assert "pool_class" in payload["pool"]


def test_student_login_rejects_inactive_school(client, test_db):
    school = _create_school(test_db, code="AUTH-INACTIVE-SCH")
    school.active_status = False
    test_db.commit()

    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="inactive.school.student@example.com",
        school_id=school.id,
        first_name="Inactive",
        last_name="Student",
        must_change_password=False,
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    response = client.post(
        "/login",
        json={
            "email": "inactive.school.student@example.com",
            "password": "StudentPass123!",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This account's school is inactive."


def test_login_rejects_oversized_password_without_server_error(client, test_db):
    school = _create_school(test_db, code="AUTH-LONG-PW")
    user = _create_user_with_role(
        test_db,
        email="long.password.student@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
        first_name="Long",
        last_name="Password",
    )

    response = client.post(
        "/login",
        json={
            "email": user.email,
            "password": "A" * 73,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_verify_password_accepts_legacy_passlib_bcrypt_hashes():
    legacy_hash = "$2b$12$59UOsRTJgmB5fRCpU0v9Wev8UFmxDMV9w8joJypWX8pmEqQzLRTiC"

    assert verify_password("AuthPassword123!", legacy_hash) is True
    assert verify_password("WrongPassword123!", legacy_hash) is False


def test_protected_endpoint_rejects_student_from_inactive_school(client, test_db):
    school = _create_school(test_db, code="AUTH-INACTIVE-SESSION")

    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="inactive.session.student@example.com",
        school_id=school.id,
        first_name="Inactive",
        last_name="Session",
        must_change_password=False,
    )
    user.set_password("StudentPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})

    school.active_status = False
    test_db.commit()

    response = client.get(
        f"/api/users/me/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "This account's school is inactive."


def test_deactivating_campus_admin_syncs_school_lockout_and_blocks_students(client, test_db):
    school = _create_school(test_db, code="CAMPUS-LOCKOUT")
    admin_user = _create_user_with_role(
        test_db,
        email="platform.lockout.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        first_name="Platform",
        last_name="Admin",
    )
    primary_campus_admin = _create_user_with_role(
        test_db,
        email="primary.lockout.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Primary",
        last_name="Campus",
    )
    secondary_campus_admin = _create_user_with_role(
        test_db,
        email="secondary.lockout.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Secondary",
        last_name="Campus",
    )
    student = _create_user_with_role(
        test_db,
        email="lockout.student@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
        first_name="Lockout",
        last_name="Student",
    )

    student_token = create_access_token({"sub": student.email})

    response = client.patch(
        f"/api/school/admin/school-it-accounts/{primary_campus_admin.id}/status",
        headers=_auth_headers(admin_user),
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    test_db.refresh(primary_campus_admin)
    test_db.refresh(secondary_campus_admin)
    test_db.refresh(school)
    assert primary_campus_admin.is_active is False
    assert secondary_campus_admin.is_active is False
    assert school.active_status is False

    login_response = client.post(
        "/login",
        json={"email": student.email, "password": "StudentPass123!"},
    )
    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "This account's school is inactive."

    protected_response = client.get(
        f"/api/users/me/",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert protected_response.status_code == 403
    assert protected_response.json()["detail"] == "This account's school is inactive."

    audit_log = (
        test_db.query(SchoolAuditLog)
        .filter(
            SchoolAuditLog.school_id == school.id,
            SchoolAuditLog.action == "school_it_status_update",
        )
        .order_by(SchoolAuditLog.id.desc())
        .first()
    )
    assert audit_log is not None
    audit_details = json.loads(audit_log.details)
    assert audit_details["school_active_status"] is False
    assert {item["user_id"] for item in audit_details["synced_school_it_accounts"]} == {
        primary_campus_admin.id,
        secondary_campus_admin.id,
    }


def test_reactivating_campus_admin_reactivates_school_and_restores_student_login(client, test_db):
    school = _create_school(test_db, code="CAMPUS-REACT")
    admin_user = _create_user_with_role(
        test_db,
        email="platform.reactivate.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        first_name="Platform",
        last_name="Admin",
    )
    primary_campus_admin = _create_user_with_role(
        test_db,
        email="primary.reactivate.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Primary",
        last_name="Campus",
    )
    secondary_campus_admin = _create_user_with_role(
        test_db,
        email="secondary.reactivate.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Secondary",
        last_name="Campus",
    )
    student = _create_user_with_role(
        test_db,
        email="reactivate.student@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
        first_name="Reactivate",
        last_name="Student",
    )

    deactivate_response = client.patch(
        f"/api/school/admin/school-it-accounts/{primary_campus_admin.id}/status",
        headers=_auth_headers(admin_user),
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 200

    reactivate_response = client.patch(
        f"/api/school/admin/school-it-accounts/{primary_campus_admin.id}/status",
        headers=_auth_headers(admin_user),
        json={"is_active": True},
    )

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True

    test_db.refresh(primary_campus_admin)
    test_db.refresh(secondary_campus_admin)
    test_db.refresh(school)
    assert primary_campus_admin.is_active is True
    assert secondary_campus_admin.is_active is True
    assert school.active_status is True

    login_response = client.post(
        "/token",
        data={"username": student.email, "password": "StudentPass123!"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    assert login_response.json()["access_token"]


def test_school_status_syncs_all_campus_admin_accounts_and_preserves_subscription_only_updates(
    client, test_db
):
    school = _create_school(test_db, code="SCHOOL-SYNC")
    admin_user = _create_user_with_role(
        test_db,
        email="platform.schoolsync.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        first_name="Platform",
        last_name="Admin",
    )
    primary_campus_admin = _create_user_with_role(
        test_db,
        email="primary.schoolsync.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Primary",
        last_name="Campus",
    )
    secondary_campus_admin = _create_user_with_role(
        test_db,
        email="secondary.schoolsync.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Secondary",
        last_name="Campus",
    )

    deactivate_response = client.patch(
        f"/api/school/admin/{school.id}/status",
        headers=_auth_headers(admin_user),
        json={"active_status": False},
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["active_status"] is False

    test_db.refresh(primary_campus_admin)
    test_db.refresh(secondary_campus_admin)
    test_db.refresh(school)
    assert primary_campus_admin.is_active is False
    assert secondary_campus_admin.is_active is False
    assert school.active_status is False

    deactivate_audit_log = (
        test_db.query(SchoolAuditLog)
        .filter(
            SchoolAuditLog.school_id == school.id,
            SchoolAuditLog.action == "school_status_update",
        )
        .order_by(SchoolAuditLog.id.desc())
        .first()
    )
    assert deactivate_audit_log is not None
    deactivate_audit_details = json.loads(deactivate_audit_log.details)
    assert deactivate_audit_details["active_status"] is False
    assert {item["user_id"] for item in deactivate_audit_details["synced_school_it_accounts"]} == {
        primary_campus_admin.id,
        secondary_campus_admin.id,
    }

    reactivate_response = client.patch(
        f"/api/school/admin/{school.id}/status",
        headers=_auth_headers(admin_user),
        json={"active_status": True},
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["active_status"] is True

    test_db.refresh(primary_campus_admin)
    test_db.refresh(secondary_campus_admin)
    test_db.refresh(school)
    assert primary_campus_admin.is_active is True
    assert secondary_campus_admin.is_active is True
    assert school.active_status is True

    subscription_only_response = client.patch(
        f"/api/school/admin/{school.id}/status",
        headers=_auth_headers(admin_user),
        json={"subscription_status": "paid"},
    )
    assert subscription_only_response.status_code == 200
    assert subscription_only_response.json()["subscription_status"] == "paid"

    test_db.refresh(primary_campus_admin)
    test_db.refresh(secondary_campus_admin)
    test_db.refresh(school)
    assert primary_campus_admin.is_active is True
    assert secondary_campus_admin.is_active is True
    assert school.subscription_status == "paid"


def test_legacy_school_settings_import_template_route_returns_gone(client, test_db):
    school = _create_school(test_db, code="LEGACY-IMPORT-TPL")
    campus_admin = _create_user_with_role(
        test_db,
        email="legacy.template.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Legacy",
        last_name="Template",
    )

    response = client.get(
        "/school-settings/me/users/import-template",
        headers=_auth_headers(campus_admin),
    )

    assert response.status_code == 410
    detail = response.json()["detail"]
    assert "/api/admin/import-students/template" in detail
    assert "/api/admin/import-students/preview" in detail
    assert "/api/admin/import-students" in detail


def test_legacy_school_settings_import_route_returns_gone(client, test_db):
    school = _create_school(test_db, code="LEGACY-IMPORT-POST")
    campus_admin = _create_user_with_role(
        test_db,
        email="legacy.import.campus@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Legacy",
        last_name="Import",
    )

    response = client.post(
        "/school-settings/me/users/import",
        headers=_auth_headers(campus_admin),
        files={
            "file": (
                "students.csv",
                b"email,first_name,last_name\nstudent@example.com,Test,Student\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 410
    detail = response.json()["detail"]
    assert "/api/admin/import-students/template" in detail
    assert "/api/admin/import-students/preview" in detail
    assert "/api/admin/import-students" in detail


def test_inactive_user_stays_blocked_after_school_reactivation(client, test_db):
    school = _create_school(test_db, code="REACT-INACTIVE-USER")
    admin_user = _create_user_with_role(
        test_db,
        email="platform.inactiveuser.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        first_name="Platform",
        last_name="Admin",
    )
    _create_user_with_role(
        test_db,
        email="campus.inactiveuser@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
    )
    inactive_student = _create_user_with_role(
        test_db,
        email="inactive.after.reactivation@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
        first_name="Inactive",
        last_name="Student",
        is_active=False,
    )

    deactivate_response = client.patch(
        f"/api/school/admin/{school.id}/status",
        headers=_auth_headers(admin_user),
        json={"active_status": False},
    )
    assert deactivate_response.status_code == 200

    reactivate_response = client.patch(
        f"/api/school/admin/{school.id}/status",
        headers=_auth_headers(admin_user),
        json={"active_status": True},
    )
    assert reactivate_response.status_code == 200

    login_response = client.post(
        "/login",
        json={
            "email": inactive_student.email,
            "password": "StudentPass123!",
        },
    )
    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "This account is inactive. Contact your administrator."


def test_create_event_api_uses_default_attendance_window_values(client, test_db):
    school = _create_school(test_db, code="EVENT-DEFAULTS")
    admin_role = Role(name="admin")
    test_db.add(admin_role)
    test_db.commit()

    admin_user = User(
        email="event.defaults@example.com",
        school_id=school.id,
        first_name="Event",
        last_name="Defaults",
        must_change_password=False,
    )
    admin_user.set_password("AdminPass123!")
    test_db.add(admin_user)
    test_db.commit()

    test_db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    test_db.commit()

    token = create_access_token({"sub": admin_user.email})
    start = datetime.utcnow().replace(microsecond=0) + timedelta(days=1)
    end = start + timedelta(hours=2)

    response = client.post(
        f"/api/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Default Window Event",
            "location": "Main Gym",
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["early_check_in_minutes"] == 30
    assert payload["late_threshold_minutes"] == 10
    assert payload["sign_out_grace_minutes"] == 20

    created_event = test_db.query(Event).filter(Event.id == payload["id"]).first()
    assert created_event is not None
    assert created_event.early_check_in_minutes == 30
    assert created_event.late_threshold_minutes == 10
    assert created_event.sign_out_grace_minutes == 20


def test_school_event_defaults_are_used_for_new_events(client, test_db):
    school = _create_school(test_db, code="EVENT-SCHOOL-DEFAULTS")
    campus_admin_role = Role(name="campus_admin")
    test_db.add(campus_admin_role)
    test_db.commit()

    campus_admin = User(
        email="event.school.defaults@example.com",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
        must_change_password=False,
    )
    campus_admin.set_password("CampusPass123!")
    test_db.add(campus_admin)
    test_db.commit()

    test_db.add(UserRole(user_id=campus_admin.id, role_id=campus_admin_role.id))
    test_db.commit()

    token = create_access_token({"sub": campus_admin.email})

    update_response = client.put(
        "/api/school/update",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "event_default_early_check_in_minutes": "45",
            "event_default_late_threshold_minutes": "12",
            "event_default_sign_out_grace_minutes": "25",
        },
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["event_default_early_check_in_minutes"] == 45
    assert update_payload["event_default_late_threshold_minutes"] == 12
    assert update_payload["event_default_sign_out_grace_minutes"] == 25

    start = datetime.utcnow().replace(microsecond=0) + timedelta(days=1)
    end = start + timedelta(hours=2)
    create_response = client.post(
        f"/api/events/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "School Default Event",
            "location": "Auditorium",
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
        },
    )

    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["early_check_in_minutes"] == 45
    assert create_payload["late_threshold_minutes"] == 12
    assert create_payload["sign_out_grace_minutes"] == 25

    school_settings = test_db.query(SchoolSetting).filter(SchoolSetting.school_id == school.id).first()
    assert school_settings is not None
    assert school_settings.event_default_early_check_in_minutes == 45
    assert school_settings.event_default_late_threshold_minutes == 12
    assert school_settings.event_default_sign_out_grace_minutes == 25


def test_create_user_api_does_not_force_password_change_for_new_accounts(client, test_db):
    school = _create_school(test_db, code="USER-SCH")
    admin_role = Role(name="admin")
    student_role = Role(name="student")
    test_db.add_all([admin_role, student_role])
    test_db.commit()

    admin_user = User(
        email="schooladmin@example.com",
        school_id=school.id,
        first_name="School",
        last_name="Admin",
        must_change_password=False,
    )
    admin_user.set_password("AdminPass123!")
    test_db.add(admin_user)
    test_db.commit()

    test_db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    test_db.commit()

    token = create_access_token({"sub": admin_user.email})

    response = client.post(
        f"/api/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "fresh.user@example.com",
            "first_name": "Fresh",
            "middle_name": "",
            "last_name": "User",
            "roles": ["student"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_temporary_password"]

    created_user = test_db.query(User).filter(User.email == "fresh.user@example.com").first()
    assert created_user is not None
    assert created_user.must_change_password is False
    assert created_user.should_prompt_password_change is True
    assert verify_password(payload["generated_temporary_password"], created_user.password_hash)


def test_create_student_account_api_creates_student_and_sends_welcome_email(
    client,
    test_db,
    monkeypatch,
):
    school = _create_school(test_db, code="STUDENT-CREATE")
    campus_admin = _create_user_with_role(
        test_db,
        email="campus.create.student@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
    )

    department = Department(school_id=school.id, name="School of Engineering")
    program = Program(school_id=school.id, name="BS Information Technology")
    department.programs.append(program)
    test_db.add_all([department, program])
    test_db.commit()

    sent: dict[str, object] = {}
    generated_password = "TempPass123A"

    monkeypatch.setattr(
        users_router,
        "generate_secure_password",
        lambda min_length=10, max_length=14: generated_password,
    )

    def fake_send_welcome_email(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(users_router, "send_welcome_email", fake_send_welcome_email)

    response = client.post(
        f"/api/users/students/",
        headers=_auth_headers(campus_admin),
        json={
            "email": "new.student@example.com",
            "first_name": "New",
            "middle_name": "",
            "last_name": "Student",
            "department_id": department.id,
            "program_id": program.id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "new.student@example.com"
    assert payload["school_id"] == school.id
    assert any(role["role"]["name"] == "student" for role in payload["roles"])
    assert payload["student_profile"]["department_id"] == department.id
    assert payload["student_profile"]["program_id"] == program.id
    assert payload["student_profile"]["year_level"] == 1

    created_user = test_db.query(User).filter(User.email == "new.student@example.com").first()
    assert created_user is not None
    assert created_user.school_id == school.id
    assert verify_password(generated_password, created_user.password_hash)

    created_profile = (
        test_db.query(StudentProfile)
        .filter(StudentProfile.user_id == created_user.id)
        .first()
    )
    assert created_profile is not None
    assert created_profile.school_id == school.id
    assert created_profile.department_id == department.id
    assert created_profile.program_id == program.id
    assert created_profile.year_level == 1

    assert sent["recipient_email"] == "new.student@example.com"
    assert sent["temporary_password"] == generated_password
    assert sent["first_name"] == "New"
    assert sent["password_is_temporary"] is True


def test_create_student_account_api_rolls_back_when_welcome_email_fails(
    client,
    test_db,
    monkeypatch,
):
    school = _create_school(test_db, code="STUDENT-EMAIL-FAIL")
    campus_admin = _create_user_with_role(
        test_db,
        email="campus.email.fail@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
    )

    department = Department(school_id=school.id, name="School of Business")
    program = Program(school_id=school.id, name="BS Accountancy")
    department.programs.append(program)
    test_db.add_all([department, program])
    test_db.commit()

    monkeypatch.setattr(
        users_router,
        "generate_secure_password",
        lambda min_length=10, max_length=14: "TempPass123A",
    )

    def failing_send_welcome_email(**kwargs):
        raise users_router.EmailDeliveryError("SMTP unavailable")

    monkeypatch.setattr(users_router, "send_welcome_email", failing_send_welcome_email)

    response = client.post(
        f"/api/users/students/",
        headers=_auth_headers(campus_admin),
        json={
            "email": "rollback.student@example.com",
            "first_name": "Rollback",
            "middle_name": "",
            "last_name": "Student",
            "department_id": department.id,
            "program_id": program.id,
        },
    )

    assert response.status_code == 502
    assert "welcome email could not be delivered" in response.json()["detail"]
    assert test_db.query(User).filter(User.email == "rollback.student@example.com").first() is None


def test_get_all_users_returns_paged_student_profiles(client, test_db):
    school = _create_school(test_db, code="USER-LIST")
    admin_user = _create_user_with_role(
        test_db,
        email="paged.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        school_id=school.id,
    )
    student_user = _create_user_with_role(
        test_db,
        email="paged.student@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
    )

    department = Department(school_id=school.id, name="School of Computing")
    program = Program(school_id=school.id, name="BSIT")
    department.programs.append(program)
    test_db.add_all([department, program])
    test_db.commit()

    test_db.add(
        StudentProfile(
            user_id=student_user.id,
            school_id=school.id,
            student_id="BSIT-2026-001",
            department_id=department.id,
            program_id=program.id,
            year_level=3,
        )
    )
    test_db.commit()

    response = client.get(
        f"/api/users/?skip=0&limit=2",
        headers=_auth_headers(admin_user),
    )

    assert response.status_code == 200
    payload = response.json()
    listed_student = next(user for user in payload if user["id"] == student_user.id)

    assert any(role["role"]["name"] == "student" for role in listed_student["roles"])
    assert listed_student["student_profile"]["student_id"] == "BSIT-2026-001"
    assert listed_student["student_profile"]["department_id"] == department.id
    assert listed_student["student_profile"]["program_id"] == program.id
    assert listed_student["student_profile"]["year_level"] == 3


def test_change_password_accepts_current_password_for_model_hashed_user(client, test_db):
    school = _create_school(test_db, code="CHG-MODEL")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="change.model@example.com",
        school_id=school.id,
        first_name="Change",
        last_name="Model",
        must_change_password=True,
    )
    temporary_password = "TempPass123!"
    new_password = "NewPass123!"
    user.set_password(temporary_password)
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": temporary_password,
            "new_password": new_password,
        },
    )

    assert response.status_code == 200

    test_db.expire_all()
    updated_user = test_db.query(User).filter(User.id == user.id).first()
    assert updated_user is not None
    assert updated_user.must_change_password is False
    assert verify_password(new_password, updated_user.password_hash)


def test_change_password_accepts_current_password_for_passlib_hashed_user(client, test_db):
    school = _create_school(test_db, code="CHG-PASSLIB")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    temporary_password = "TempPass123!"
    new_password = "NewPass123!"
    user = User(
        email="change.passlib@example.com",
        school_id=school.id,
        first_name="Change",
        last_name="Passlib",
        must_change_password=True,
        password_hash=hash_password_bcrypt(temporary_password),
    )
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": temporary_password,
            "new_password": new_password,
        },
    )

    assert response.status_code == 200

    test_db.expire_all()
    updated_user = test_db.query(User).filter(User.id == user.id).first()
    assert updated_user is not None
    assert updated_user.must_change_password is False
    assert verify_password(new_password, updated_user.password_hash)


def test_forgot_password_creates_pending_request_for_student(client, test_db):
    school = _create_school(test_db, code="FORGOT-STUDENT")
    student = _create_user_with_role(
        test_db,
        email="forgot.student@example.com",
        role_name="student",
        password="StudentPass123!",
        school_id=school.id,
        first_name="Forgot",
        last_name="Student",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": student.email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If the account exists, a password reset request has been submitted for administrator approval."
    )

    request_item = (
        test_db.query(PasswordResetRequest)
        .filter(PasswordResetRequest.user_id == student.id)
        .first()
    )
    assert request_item is not None
    assert request_item.school_id == school.id
    assert request_item.status == "pending"
    assert request_item.requested_email == student.email


def test_forgot_password_creates_pending_request_for_campus_admin_and_hides_it_from_campus_admin_list(
    client, test_db
):
    school = _create_school(test_db, code="FORGOT-CAMPUS")
    platform_admin = _create_user_with_role(
        test_db,
        email="platform.forgot.admin@example.com",
        role_name="admin",
        password="AdminPass123!",
        first_name="Platform",
        last_name="Admin",
    )
    requesting_campus_admin = _create_user_with_role(
        test_db,
        email="requesting.campus.admin@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Requesting",
        last_name="Campus",
    )
    reviewing_campus_admin = _create_user_with_role(
        test_db,
        email="reviewing.campus.admin@example.com",
        role_name="campus_admin",
        password="CampusPass123!",
        school_id=school.id,
        first_name="Reviewing",
        last_name="Campus",
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": requesting_campus_admin.email},
    )

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If the account exists, a password reset request has been submitted for administrator approval."
    )

    request_item = (
        test_db.query(PasswordResetRequest)
        .filter(PasswordResetRequest.user_id == requesting_campus_admin.id)
        .first()
    )
    assert request_item is not None
    assert request_item.school_id == school.id
    assert request_item.status == "pending"
    assert request_item.requested_email == requesting_campus_admin.email

    platform_response = client.get(
        "/auth/password-reset-requests",
        headers=_auth_headers(platform_admin),
    )
    assert platform_response.status_code == 200
    assert [item["email"] for item in platform_response.json()] == [
        requesting_campus_admin.email
    ]

    campus_response = client.get(
        "/auth/password-reset-requests",
        headers=_auth_headers(reviewing_campus_admin),
    )
    assert campus_response.status_code == 200
    assert campus_response.json() == []


def test_login_response_recommends_password_change_when_prompt_flag_is_set(client, test_db):
    school = _create_school(test_db, code="PROMPT-SCH")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="prompted@example.com",
        school_id=school.id,
        first_name="Prompted",
        last_name="User",
        must_change_password=False,
        should_prompt_password_change=True,
    )
    user.set_password("PromptPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    response = client.post(
        "/token",
        data={
            "username": "prompted@example.com",
            "password": "PromptPass123!",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["must_change_password"] is False
    assert data["password_change_recommended"] is True


def test_change_password_clears_password_change_prompt_flag(client, test_db):
    school = _create_school(test_db, code="PROMPT-CLR")
    role = Role(name="student")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="prompt.clear@example.com",
        school_id=school.id,
        first_name="Prompt",
        last_name="Clear",
        must_change_password=False,
        should_prompt_password_change=True,
    )
    user.set_password("PromptPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email})

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "PromptPass123!",
            "new_password": "PromptPass456!",
        },
    )

    assert response.status_code == 200

    test_db.expire_all()
    updated_user = test_db.query(User).filter(User.id == user.id).first()
    assert updated_user is not None
    assert updated_user.should_prompt_password_change is False
    assert updated_user.must_change_password is False


def test_face_pending_user_can_change_password_during_onboarding(client, test_db):
    school = _create_school(test_db, code="FACE-CHG")
    role = Role(name="school_IT")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="schoolit@example.com",
        school_id=school.id,
        first_name="School",
        last_name="IT",
        must_change_password=True,
    )
    user.set_password("TempPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email, "face_pending": True})

    response = client.post(
        "/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "TempPass123!",
            "new_password": "NextPass123!",
        },
    )

    assert response.status_code == 200


def test_face_pending_user_can_dismiss_password_change_prompt(client, test_db):
    school = _create_school(test_db, code="FACE-SKIP")
    role = Role(name="school_IT")
    test_db.add(role)
    test_db.commit()

    user = User(
        email="skip.prompt@example.com",
        school_id=school.id,
        first_name="Skip",
        last_name="Prompt",
        must_change_password=False,
        should_prompt_password_change=True,
    )
    user.set_password("SkipPass123!")
    test_db.add(user)
    test_db.commit()

    test_db.add(UserRole(user_id=user.id, role_id=role.id))
    test_db.commit()

    token = create_access_token({"sub": user.email, "face_pending": True})

    response = client.post(
        "/auth/password-change-prompt/dismiss",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    test_db.expire_all()
    updated_user = test_db.query(User).filter(User.id == user.id).first()
    assert updated_user is not None
    assert updated_user.should_prompt_password_change is False


def test_create_user_api_honors_submitted_password(client, test_db):
    school = _create_school(test_db, code="USER-PASS")
    admin_role = Role(name="admin")
    student_role = Role(name="student")
    test_db.add_all([admin_role, student_role])
    test_db.commit()

    admin_user = User(
        email="schooladmin2@example.com",
        school_id=school.id,
        first_name="School",
        last_name="Admin",
        must_change_password=False,
    )
    admin_user.set_password("AdminPass123!")
    test_db.add(admin_user)
    test_db.commit()

    test_db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    test_db.commit()

    token = create_access_token({"sub": admin_user.email})
    submitted_password = "StudentPass123!"

    response = client.post(
        f"/api/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "submitted.pass@example.com",
            "password": submitted_password,
            "first_name": "Submitted",
            "middle_name": "",
            "last_name": "Password",
            "roles": ["student"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_temporary_password"] is None

    created_user = test_db.query(User).filter(User.email == "submitted.pass@example.com").first()
    assert created_user is not None
    assert created_user.should_prompt_password_change is True
    assert verify_password(submitted_password, created_user.password_hash)


def test_campus_admin_create_user_api_rejects_non_student_roles(client, test_db):
    school = _create_school(test_db, code="USER-ROLE-LOCK")
    school_it_role = Role(name="campus_admin")
    student_role = Role(name="student")
    test_db.add_all([school_it_role, student_role])
    test_db.commit()

    campus_admin = User(
        email="campus.admin@example.com",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
        must_change_password=False,
    )
    campus_admin.set_password("CampusPass123!")
    test_db.add(campus_admin)
    test_db.commit()

    test_db.add(UserRole(user_id=campus_admin.id, role_id=school_it_role.id))
    test_db.commit()

    token = create_access_token({"sub": campus_admin.email})

    response = client.post(
        f"/api/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "blocked.officer@example.com",
            "first_name": "Blocked",
            "middle_name": "",
            "last_name": "Officer",
            "roles": ["campus_admin"],
        },
    )

    assert response.status_code == 403
    assert "Campus Admin can only assign the student role from user management" in response.json()["detail"]


def test_campus_admin_cannot_update_roles_from_manage_users(client, test_db):
    school = _create_school(test_db, code="ROLE-UPDATE-LOCK")
    school_it_role = Role(name="campus_admin")
    student_role = Role(name="student")
    test_db.add_all([school_it_role, student_role])
    test_db.commit()

    campus_admin = User(
        email="campus.roles@example.com",
        school_id=school.id,
        first_name="Campus",
        last_name="Admin",
        must_change_password=False,
    )
    campus_admin.set_password("CampusPass123!")
    test_db.add(campus_admin)
    test_db.commit()

    target_user = User(
        email="student.target@example.com",
        school_id=school.id,
        first_name="Student",
        last_name="Target",
        must_change_password=False,
    )
    target_user.set_password("StudentPass123!")
    test_db.add(target_user)
    test_db.commit()

    test_db.add_all(
        [
            UserRole(user_id=campus_admin.id, role_id=school_it_role.id),
            UserRole(user_id=target_user.id, role_id=student_role.id),
        ]
    )
    test_db.commit()

    token = create_access_token({"sub": campus_admin.email})

    response = client.put(
        f"/api/users/{target_user.id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={"roles": ["student", "campus_admin"]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Campus Admin cannot change user roles from Manage Users. "
        "Imported users stay students, and SSG access is managed from Manage SSG."
    )


def test_create_school_it_honors_submitted_password_and_sets_prompt_flag(client, test_db):
    admin_role = Role(name="admin")
    school_it_role = Role(name="school_IT")
    test_db.add_all([admin_role, school_it_role])
    test_db.commit()

    admin_user = User(
        email="platformadmin@example.com",
        first_name="Platform",
        last_name="Admin",
        must_change_password=False,
    )
    admin_user.set_password("AdminPass123!")
    test_db.add(admin_user)
    test_db.commit()

    test_db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
    test_db.commit()

    token = create_access_token({"sub": admin_user.email})
    submitted_password = "SchoolItPass123!"

    response = client.post(
        "/api/school/admin/create-school-it",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "school_name": "Prompt School",
            "primary_color": "#112233",
            "secondary_color": "#445566",
            "school_code": "PROMPT",
            "school_it_email": "school.it.prompt@example.com",
            "school_it_first_name": "School",
            "school_it_last_name": "IT",
            "school_it_password": submitted_password,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_temporary_password"] is None

    created_user = test_db.query(User).filter(User.email == "school.it.prompt@example.com").first()
    assert created_user is not None
    assert created_user.should_prompt_password_change is True
    assert verify_password(submitted_password, created_user.password_hash)
