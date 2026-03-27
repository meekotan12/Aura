from __future__ import annotations

import base64
from datetime import datetime, timedelta

import numpy as np

from app.models.department import Department
from app.models.event import Event, EventStatus
from app.models.program import Program
from app.models.school import School
from app.models.user import StudentProfile, User
from app.routers import public_attendance
from app.services.attendance_face_scan import get_registered_face_candidates_for_event
from app.services.event_time_status import get_event_timezone
from app.services.face_recognition import DetectedFaceProbe, LivenessResult


def _frame_payload() -> str:
    return "data:image/jpeg;base64," + base64.b64encode(b"public-kiosk-frame").decode("ascii")


def _face_encoding(value: float) -> bytes:
    return np.asarray([value], dtype=np.float64).tobytes()


def _real_probe(index: int, value: float) -> DetectedFaceProbe:
    return DetectedFaceProbe(
        index=index,
        location=(10 + index, 20 + index, 30 + index, 40 + index),
        liveness=LivenessResult(label="Real", score=0.99),
        encoding=np.asarray([value], dtype=np.float64),
        error_code=None,
    )


def _spoof_probe(index: int) -> DetectedFaceProbe:
    return DetectedFaceProbe(
        index=index,
        location=(10 + index, 20 + index, 30 + index, 40 + index),
        liveness=LivenessResult(label="Fake", score=0.02),
        encoding=None,
        error_code="spoof_detected",
    )


def _create_school(test_db, *, code: str, name: str) -> School:
    school = School(
        name=name,
        school_name=name,
        school_code=code,
        address=f"{name} Address",
        active_status=True,
    )
    test_db.add(school)
    test_db.commit()
    test_db.refresh(school)
    return school


def _create_department(test_db, *, school: School, name: str) -> Department:
    department = Department(school_id=school.id, name=name)
    test_db.add(department)
    test_db.commit()
    test_db.refresh(department)
    return department


def _create_program(test_db, *, school: School, name: str, department: Department | None = None) -> Program:
    program = Program(school_id=school.id, name=name)
    if department is not None:
        program.departments = [department]
    test_db.add(program)
    test_db.commit()
    test_db.refresh(program)
    return program


def _create_student(
    test_db,
    *,
    school: School,
    email: str,
    student_id: str,
    first_name: str,
    last_name: str,
    face_value: float,
    department: Department | None = None,
    program: Program | None = None,
) -> StudentProfile:
    user = User(
        email=email,
        school_id=school.id,
        first_name=first_name,
        last_name=last_name,
        must_change_password=False,
    )
    user.set_password("password123")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    student = StudentProfile(
        user_id=user.id,
        school_id=school.id,
        student_id=student_id,
        department_id=department.id if department is not None else None,
        program_id=program.id if program is not None else None,
        year_level=1,
        face_encoding=_face_encoding(face_value),
        is_face_registered=True,
        registration_complete=True,
    )
    test_db.add(student)
    test_db.commit()
    test_db.refresh(student)
    return student


def _create_event(
    test_db,
    *,
    school: School,
    name: str,
    latitude: float,
    longitude: float,
    radius_m: float,
    start_offset_minutes: int,
    end_offset_minutes: int,
    departments: list[Department] | None = None,
    programs: list[Program] | None = None,
) -> Event:
    now = datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0)
    event = Event(
        school_id=school.id,
        name=name,
        location=f"{name} Hall",
        geo_latitude=latitude,
        geo_longitude=longitude,
        geo_radius_m=radius_m,
        geo_required=True,
        geo_max_accuracy_m=25,
        start_datetime=now + timedelta(minutes=start_offset_minutes),
        end_datetime=now + timedelta(minutes=end_offset_minutes),
        status=EventStatus.UPCOMING,
    )
    if departments:
        event.departments = departments
    if programs:
        event.programs = programs
    test_db.add(event)
    test_db.commit()
    test_db.refresh(event)
    return event


def test_public_nearby_events_returns_only_geofence_matches_across_schools(client, test_db):
    near_lat = 8.1575
    near_lng = 123.8431
    school_a = _create_school(test_db, code="A", name="Campus A")
    school_b = _create_school(test_db, code="B", name="Campus B")

    nearby_a = _create_event(
        test_db,
        school=school_a,
        name="Nearby A",
        latitude=near_lat,
        longitude=near_lng,
        radius_m=60,
        start_offset_minutes=-10,
        end_offset_minutes=60,
    )
    nearby_b = _create_event(
        test_db,
        school=school_b,
        name="Nearby B",
        latitude=near_lat,
        longitude=near_lng,
        radius_m=60,
        start_offset_minutes=-5,
        end_offset_minutes=45,
    )
    _create_event(
        test_db,
        school=school_a,
        name="Far Away",
        latitude=9.5,
        longitude=124.9,
        radius_m=30,
        start_offset_minutes=-5,
        end_offset_minutes=45,
    )

    response = client.post(
        "/public-attendance/events/nearby",
        json={"latitude": near_lat, "longitude": near_lng, "accuracy_m": 5},
    )

    assert response.status_code == 200
    body = response.json()
    event_ids = {item["id"] for item in body["events"]}
    school_ids = {item["school_id"] for item in body["events"]}

    assert nearby_a.id in event_ids
    assert nearby_b.id in event_ids
    assert len(body["events"]) == 2
    assert school_a.id in school_ids
    assert school_b.id in school_ids


def test_campus_wide_event_candidates_include_all_registered_students(test_db):
    school = _create_school(test_db, code="CW", name="Campus Wide")
    department_a = _create_department(test_db, school=school, name="Engineering")
    department_b = _create_department(test_db, school=school, name="Education")
    program_a = _create_program(test_db, school=school, name="BSIT", department=department_a)
    program_b = _create_program(test_db, school=school, name="BSED", department=department_b)

    student_a = _create_student(
        test_db,
        school=school,
        email="cw-a@example.com",
        student_id="CW-001",
        first_name="Campus",
        last_name="One",
        face_value=0.11,
        department=department_a,
        program=program_a,
    )
    student_b = _create_student(
        test_db,
        school=school,
        email="cw-b@example.com",
        student_id="CW-002",
        first_name="Campus",
        last_name="Two",
        face_value=0.22,
        department=department_b,
        program=program_b,
    )
    event = _create_event(
        test_db,
        school=school,
        name="Campus Event",
        latitude=8.1575,
        longitude=123.8431,
        radius_m=40,
        start_offset_minutes=-10,
        end_offset_minutes=60,
    )

    candidates = get_registered_face_candidates_for_event(test_db, event)
    candidate_ids = {candidate.student.id for candidate in candidates}

    assert candidate_ids == {student_a.id, student_b.id}


def test_public_multi_face_scan_supports_department_scope_duplicates_and_generic_unmatched(
    client,
    test_db,
    monkeypatch,
):
    monkeypatch.setattr(public_attendance, "PUBLIC_SCAN_REQUEST_MIN_INTERVAL_SECONDS", 0.0)

    school = _create_school(test_db, code="DEPT", name="Department Campus")
    department_scope = _create_department(test_db, school=school, name="Engineering")
    other_department = _create_department(test_db, school=school, name="Education")

    in_scope_student = _create_student(
        test_db,
        school=school,
        email="dept-in@example.com",
        student_id="DEPT-001",
        first_name="Scope",
        last_name="Match",
        face_value=0.15,
        department=department_scope,
    )
    _create_student(
        test_db,
        school=school,
        email="dept-out@example.com",
        student_id="DEPT-002",
        first_name="Out",
        last_name="Scope",
        face_value=0.85,
        department=other_department,
    )

    event = _create_event(
        test_db,
        school=school,
        name="Department Event",
        latitude=8.1575,
        longitude=123.8431,
        radius_m=50,
        start_offset_minutes=-10,
        end_offset_minutes=60,
        departments=[department_scope],
    )

    monkeypatch.setattr(
        public_attendance.face_service,
        "analyze_faces_from_bytes",
        lambda *_args, **_kwargs: [
            _real_probe(0, 0.15),
            _real_probe(1, 0.85),
            _real_probe(2, 0.15),
            _real_probe(3, 9.9),
            _spoof_probe(4),
        ],
    )

    response = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
            "cooldown_student_ids": [],
        },
    )

    assert response.status_code == 200
    body = response.json()
    actions = [item["action"] for item in body["outcomes"]]
    successful = next(item for item in body["outcomes"] if item["action"] == "time_in")
    out_of_scope = next(item for item in body["outcomes"] if item["action"] == "out_of_scope")
    no_match = next(item for item in body["outcomes"] if item["action"] == "no_match")

    assert actions == ["time_in", "out_of_scope", "duplicate_face", "no_match", "liveness_failed"]
    assert successful["student_id"] == in_scope_student.student_id
    assert out_of_scope["student_id"] is None
    assert out_of_scope["student_name"] is None
    assert no_match["student_id"] is None
    assert no_match["student_name"] is None


def test_public_multi_face_scan_supports_program_scoped_events(client, test_db, monkeypatch):
    monkeypatch.setattr(public_attendance, "PUBLIC_SCAN_REQUEST_MIN_INTERVAL_SECONDS", 0.0)

    school = _create_school(test_db, code="ORG", name="Program Campus")
    department = _create_department(test_db, school=school, name="Engineering")
    allowed_program = _create_program(test_db, school=school, name="BSIT", department=department)
    denied_program = _create_program(test_db, school=school, name="BSCS", department=department)

    in_scope_student = _create_student(
        test_db,
        school=school,
        email="org-in@example.com",
        student_id="ORG-001",
        first_name="Program",
        last_name="Allowed",
        face_value=0.31,
        department=department,
        program=allowed_program,
    )
    _create_student(
        test_db,
        school=school,
        email="org-out@example.com",
        student_id="ORG-002",
        first_name="Program",
        last_name="Denied",
        face_value=0.91,
        department=department,
        program=denied_program,
    )

    event = _create_event(
        test_db,
        school=school,
        name="Program Event",
        latitude=8.1575,
        longitude=123.8431,
        radius_m=50,
        start_offset_minutes=-10,
        end_offset_minutes=60,
        departments=[department],
        programs=[allowed_program],
    )

    monkeypatch.setattr(
        public_attendance.face_service,
        "analyze_faces_from_bytes",
        lambda *_args, **_kwargs: [
            _real_probe(0, 0.31),
            _real_probe(1, 0.91),
        ],
    )

    response = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    actions = [item["action"] for item in body["outcomes"]]
    success = next(item for item in body["outcomes"] if item["action"] == "time_in")

    assert actions == ["time_in", "out_of_scope"]
    assert success["student_id"] == in_scope_student.student_id


def test_public_multi_face_scan_uses_phase_based_sign_in_and_sign_out_rules(
    client,
    test_db,
    monkeypatch,
):
    monkeypatch.setattr(public_attendance, "PUBLIC_SCAN_REQUEST_MIN_INTERVAL_SECONDS", 0.0)

    school = _create_school(test_db, code="PHASE", name="Phase Campus")
    student = _create_student(
        test_db,
        school=school,
        email="phase@example.com",
        student_id="PHASE-001",
        first_name="Phase",
        last_name="Student",
        face_value=0.42,
    )
    unsigned_student = _create_student(
        test_db,
        school=school,
        email="phase-unsigned@example.com",
        student_id="PHASE-002",
        first_name="Unsigned",
        last_name="Student",
        face_value=0.73,
    )
    event = _create_event(
        test_db,
        school=school,
        name="Phase Event",
        latitude=8.1575,
        longitude=123.8431,
        radius_m=50,
        start_offset_minutes=-10,
        end_offset_minutes=20,
    )

    monkeypatch.setattr(
        public_attendance.face_service,
        "analyze_faces_from_bytes",
        lambda *_args, **_kwargs: [_real_probe(0, 0.42)],
    )

    first = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )
    second = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )

    assert first.status_code == 200
    assert first.json()["outcomes"][0]["action"] == "time_in"
    assert second.status_code == 200
    assert second.json()["outcomes"][0]["action"] == "already_signed_in"

    event.end_datetime = (
        datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0) - timedelta(minutes=1)
    )
    event.status = EventStatus.ONGOING
    test_db.add(event)
    test_db.commit()

    third = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )

    assert third.status_code == 200
    assert third.json()["outcomes"][0]["action"] == "time_out"

    fourth = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )

    assert fourth.status_code == 200
    assert fourth.json()["outcomes"][0]["action"] == "already_signed_out"

    monkeypatch.setattr(
        public_attendance.face_service,
        "analyze_faces_from_bytes",
        lambda *_args, **_kwargs: [_real_probe(0, 0.73)],
    )
    fifth = client.post(
        f"/public-attendance/events/{event.id}/multi-face-scan",
        json={
            "image_base64": _frame_payload(),
            "latitude": 8.1575,
            "longitude": 123.8431,
            "accuracy_m": 5,
        },
    )

    assert fifth.status_code == 200
    assert fifth.json()["outcomes"][0]["action"] == "rejected"
    assert fifth.json()["outcomes"][0]["reason_code"] == "no_active_attendance_for_sign_out"
