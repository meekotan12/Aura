"""Use: Shares student face candidate scoping and public attendance persistence helpers.
Where to use: Use this from attendance-related routers that need event-scoped face matching.
Role: Service layer. It keeps scope and persistence rules out of router files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.attendance import Attendance as AttendanceModel
from app.models.event import Event as EventModel
from app.models.user import StudentProfile, User as UserModel
from app.schemas.event import EventLocationVerificationResponse
from app.services.attendance_status import finalize_completed_attendance_status
from app.services.event_attendance_service import get_event_participant_student_ids
from app.services.event_time_status import get_attendance_decision, get_event_status, get_sign_out_decision
from app.services.face_recognition import FaceCandidate, FaceMatchResult, LivenessResult
from app.services.notification_center_service import send_attendance_notification


@dataclass(frozen=True)
class ScopedStudentFaceCandidate:
    student: StudentProfile
    candidate: FaceCandidate


@dataclass(frozen=True)
class PublicAttendancePersistenceResult:
    action: str
    message: str
    reason_code: str | None = None
    attendance_id: int | None = None
    time_in: datetime | None = None
    time_out: datetime | None = None
    duration_minutes: int | None = None


def student_display_name(student: StudentProfile) -> str:
    user = student.user
    if user is None:
        return student.student_id or f"Student {student.id}"
    full_name = " ".join(
        part.strip()
        for part in [user.first_name or "", user.middle_name or "", user.last_name or ""]
        if part and part.strip()
    ).strip()
    return full_name or student.student_id or f"Student {student.id}"


def _build_scoped_candidates(students: list[StudentProfile]) -> list[ScopedStudentFaceCandidate]:
    candidates: list[ScopedStudentFaceCandidate] = []
    for student in students:
        if not student.face_encoding:
            continue
        candidates.append(
            ScopedStudentFaceCandidate(
                student=student,
                candidate=FaceCandidate(
                    identifier=student.id,
                    label=student_display_name(student),
                    encoding_bytes=bytes(student.face_encoding),
                ),
            )
        )
    return candidates


def get_registered_face_candidates_for_school(
    db: Session,
    school_id: int,
) -> list[ScopedStudentFaceCandidate]:
    students = (
        db.query(StudentProfile)
        .options(joinedload(StudentProfile.user))
        .join(UserModel, StudentProfile.user_id == UserModel.id)
        .filter(
            UserModel.school_id == school_id,
            StudentProfile.face_encoding.isnot(None),
            StudentProfile.is_face_registered.is_(True),
        )
        .all()
    )
    return _build_scoped_candidates(students)


def get_registered_face_candidates_for_event(
    db: Session,
    event: EventModel,
) -> list[ScopedStudentFaceCandidate]:
    participant_ids = get_event_participant_student_ids(db, event)
    if not participant_ids:
        return []

    students = (
        db.query(StudentProfile)
        .options(joinedload(StudentProfile.user))
        .filter(
            StudentProfile.id.in_(participant_ids),
            StudentProfile.face_encoding.isnot(None),
            StudentProfile.is_face_registered.is_(True),
        )
        .all()
    )
    return _build_scoped_candidates(students)


def resolve_face_match_scope(
    *,
    face_service,
    encoding,
    event_candidates: list[ScopedStudentFaceCandidate],
    school_candidates: list[ScopedStudentFaceCandidate],
    threshold: float | None = None,
) -> tuple[str, StudentProfile | None, FaceMatchResult]:
    empty_match = FaceMatchResult(
        matched=False,
        threshold=float(threshold or face_service.settings.face_match_threshold),
        distance=float("inf"),
        confidence=0.0,
        candidate=None,
    )

    if event_candidates:
        event_match = face_service.find_best_match(
            encoding,
            [candidate.candidate for candidate in event_candidates],
            threshold=threshold,
        )
        if event_match.matched and event_match.candidate is not None:
            event_lookup = {
                candidate.candidate.identifier: candidate.student
                for candidate in event_candidates
            }
            return "in_scope", event_lookup.get(event_match.candidate.identifier), event_match
    else:
        event_match = empty_match

    if school_candidates:
        school_match = face_service.find_best_match(
            encoding,
            [candidate.candidate for candidate in school_candidates],
            threshold=threshold,
        )
        if school_match.matched and school_match.candidate is not None:
            school_lookup = {
                candidate.candidate.identifier: candidate.student
                for candidate in school_candidates
            }
            return "out_of_scope", school_lookup.get(school_match.candidate.identifier), school_match
        return "no_match", None, school_match

    return "no_match", None, event_match


def resolve_public_attendance_phase(event: EventModel) -> str | None:
    time_status = get_event_status(
        start_time=event.start_datetime,
        end_time=event.end_datetime,
        early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
        late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
        sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
        sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
        sign_out_override_until=getattr(event, "sign_out_override_until", None),
        present_until_override_at=getattr(event, "present_until_override_at", None),
        late_until_override_at=getattr(event, "late_until_override_at", None),
    )
    if time_status.event_status in {"early_check_in", "late_check_in", "absent_check_in"}:
        return "sign_in"
    if time_status.event_status == "sign_out_open":
        return "sign_out"
    return None


def persist_public_attendance_scan(
    db: Session,
    *,
    event: EventModel,
    student: StudentProfile,
    phase: str,
    scanned_at: datetime,
    geo_response: EventLocationVerificationResponse | None,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
    liveness: LivenessResult | None = None,
) -> PublicAttendancePersistenceResult:
    active_attendance = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event.id,
            AttendanceModel.time_out.is_(None),
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )
    latest_attendance = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event.id,
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )

    if phase == "sign_in":
        if active_attendance is not None:
            return PublicAttendancePersistenceResult(
                action="already_signed_in",
                reason_code="attendance_already_in_progress",
                attendance_id=active_attendance.id,
                time_in=active_attendance.time_in,
                message="Attendance is already active for this student in this event.",
            )
        if latest_attendance is not None and latest_attendance.time_out is not None:
            return PublicAttendancePersistenceResult(
                action="already_signed_out",
                reason_code="attendance_already_completed",
                attendance_id=latest_attendance.id,
                time_in=latest_attendance.time_in,
                time_out=latest_attendance.time_out,
                duration_minutes=(
                    int(max(0, (latest_attendance.time_out - latest_attendance.time_in).total_seconds() / 60))
                    if latest_attendance.time_in and latest_attendance.time_out
                    else None
                ),
                message="Attendance has already been completed for this student and event.",
            )

        attendance_decision = get_attendance_decision(
            start_time=event.start_datetime,
            end_time=event.end_datetime,
            early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
            late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
            sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
            sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
            sign_out_override_until=getattr(event, "sign_out_override_until", None),
            present_until_override_at=getattr(event, "present_until_override_at", None),
            late_until_override_at=getattr(event, "late_until_override_at", None),
        )
        if not attendance_decision.attendance_allowed:
            return PublicAttendancePersistenceResult(
                action="rejected",
                reason_code=attendance_decision.reason_code or "attendance_not_allowed",
                message=attendance_decision.message,
            )

        attendance = AttendanceModel(
            student_id=student.id,
            event_id=event.id,
            time_in=scanned_at,
            method="face_scan",
            status=attendance_decision.attendance_status or "absent",
            check_in_status=attendance_decision.attendance_status,
            check_out_status=None,
            verified_by=None,
            notes="Pending sign-out.",
            geo_distance_m=geo_response.distance_m if geo_response else None,
            geo_effective_distance_m=geo_response.effective_distance_m if geo_response else None,
            geo_latitude=latitude,
            geo_longitude=longitude,
            geo_accuracy_m=accuracy_m,
            liveness_label=str(liveness.label) if liveness is not None else None,
            liveness_score=float(liveness.score) if liveness is not None else None,
        )
        db.add(attendance)
        db.flush()
        if student.user is not None:
            notification_category = (
                "late_attendance"
                if attendance_decision.attendance_status == "late"
                else "attendance_sign_in"
            )
            send_attendance_notification(
                db,
                user=student.user,
                school_id=event.school_id,
                category=notification_category,
                subject=(
                    f"Late attendance recorded for {event.name}"
                    if notification_category == "late_attendance"
                    else f"Sign-in recorded for {event.name}"
                ),
                message=(
                    f"Your sign-in for {event.name} was recorded and marked {attendance_decision.attendance_status}."
                    " Complete sign-out during the allowed window to validate attendance."
                ),
                metadata_json={
                    "event_id": event.id,
                    "attendance_id": attendance.id,
                    "action": "sign_in",
                    "source": "public_attendance",
                    "display_status": attendance_decision.attendance_status,
                },
            )
        db.commit()
        db.refresh(attendance)
        return PublicAttendancePersistenceResult(
            action="time_in",
            attendance_id=attendance.id,
            time_in=attendance.time_in,
            message="Check-in recorded successfully.",
        )

    if active_attendance is None:
        if latest_attendance is not None and latest_attendance.time_out is not None:
            return PublicAttendancePersistenceResult(
                action="already_signed_out",
                reason_code="attendance_already_completed",
                attendance_id=latest_attendance.id,
                time_in=latest_attendance.time_in,
                time_out=latest_attendance.time_out,
                duration_minutes=(
                    int(max(0, (latest_attendance.time_out - latest_attendance.time_in).total_seconds() / 60))
                    if latest_attendance.time_in and latest_attendance.time_out
                    else None
                ),
                message="Attendance has already been completed for this student and event.",
            )
        return PublicAttendancePersistenceResult(
            action="rejected",
            reason_code="no_active_attendance_for_sign_out",
            message="This student does not have an active sign-in for this event.",
        )

    sign_out_decision = get_sign_out_decision(
        start_time=event.start_datetime,
        end_time=event.end_datetime,
        early_check_in_minutes=getattr(event, "early_check_in_minutes", 0),
        late_threshold_minutes=getattr(event, "late_threshold_minutes", 0),
        sign_out_grace_minutes=getattr(event, "sign_out_grace_minutes", 0),
        sign_out_open_delay_minutes=getattr(event, "sign_out_open_delay_minutes", 0),
        sign_out_override_until=getattr(event, "sign_out_override_until", None),
        present_until_override_at=getattr(event, "present_until_override_at", None),
        late_until_override_at=getattr(event, "late_until_override_at", None),
    )
    if not sign_out_decision.attendance_allowed:
        return PublicAttendancePersistenceResult(
            action="rejected",
            reason_code=sign_out_decision.reason_code or "attendance_not_allowed",
            message=sign_out_decision.message,
        )

    active_attendance.time_out = scanned_at
    active_attendance.check_out_status = "present"
    finalized_status, finalized_note = finalize_completed_attendance_status(
        check_in_status=active_attendance.check_in_status or active_attendance.status,
        check_out_status=active_attendance.check_out_status,
    )
    active_attendance.status = finalized_status
    active_attendance.notes = finalized_note
    if student.user is not None:
        send_attendance_notification(
            db,
            user=student.user,
            school_id=event.school_id,
            category="attendance_sign_out",
            subject=f"Sign-out recorded for {event.name}",
            message=(
                f"Your sign-out for {event.name} was recorded successfully."
                if finalized_status in {"present", "late"}
                else f"Your sign-out for {event.name} was recorded, but the attendance is not valid."
            ),
            metadata_json={
                "event_id": event.id,
                "attendance_id": active_attendance.id,
                "action": "sign_out",
                "source": "public_attendance",
                "display_status": finalized_status,
            },
        )
    db.commit()
    db.refresh(active_attendance)

    return PublicAttendancePersistenceResult(
        action="time_out",
        attendance_id=active_attendance.id,
        time_in=active_attendance.time_in,
        time_out=active_attendance.time_out,
        duration_minutes=int(
            max(0, (active_attendance.time_out - active_attendance.time_in).total_seconds() / 60)
        ),
        message="Check-out recorded successfully.",
    )


def build_outcome_liveness_payload(result: LivenessResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    return result.to_dict()
