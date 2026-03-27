"""Use: Handles face recognition and face-based attendance API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs face recognition and face-based attendance features.
Role: Router layer. It receives HTTP requests, checks access rules, and returns API responses.
"""

from __future__ import annotations

from datetime import datetime
import math

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import (
    get_current_application_user,
    get_current_student_user,
    get_school_id_or_403,
    has_any_role,
)
from app.core.dependencies import get_db
from app.models.attendance import Attendance as AttendanceModel
from app.models.event import Event as EventModel, EventStatus as ModelEventStatus
from app.models.governance_hierarchy import PermissionCode
from app.models.user import StudentProfile, User as UserModel
from app.schemas.event import EventLocationVerificationResponse
from app.schemas.face_recognition import (
    Base64ImageRequest,
    FaceAttendanceScanRequest,
    FaceAttendanceScanResponse,
    FaceRegistrationResponse,
    FaceVerificationResponse,
)
from app.services.attendance_face_scan import (
    get_registered_face_candidates_for_event,
    get_registered_face_candidates_for_school,
    student_display_name,
)
from app.services.event_attendance_service import get_event_participant_student_ids
from app.services.face_recognition import (
    FaceRecognitionService,
    LivenessResult,
    is_face_scan_bypass_enabled_for_user,
)
from app.services.attendance_status import (
    finalize_completed_attendance_status,
)
from app.services.event_geolocation import (
    find_attendance_geolocation_travel_risk,
    verify_event_geolocation_for_attendance,
)
from app.services.notification_center_service import send_attendance_notification
from app.services.event_time_status import get_attendance_decision, get_sign_out_decision
from app.services.event_workflow_status import sync_event_workflow_status
from app.services import governance_hierarchy_service


router = APIRouter(prefix="/face", tags=["face-recognition"])
face_service = FaceRecognitionService()


def _require_student_profile(current_user: UserModel) -> StudentProfile:
    profile = getattr(current_user, "student_profile", None)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users with a student profile can register a student face.",
        )
    return profile


def _get_school_event_or_404(db: Session, event_id: int, school_id: int) -> EventModel:
    event = (
        db.query(EventModel)
        .filter(EventModel.id == event_id, EventModel.school_id == school_id)
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    sync_result = sync_event_workflow_status(db, event)
    if sync_result.changed:
        db.commit()
        db.refresh(event)
    if event.status == ModelEventStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event is cancelled.")
    return event


def _serialize_attendance_decision(decision) -> dict[str, object]:
    payload = decision.to_dict()
    for key, value in list(payload.items()):
        if isinstance(value, datetime):
            payload[key] = value.isoformat()
    return payload


def _attendance_time_window_detail(event: EventModel, *, action: str = "check_in") -> dict[str, object]:
    decision = (
        get_sign_out_decision(
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
        if action == "sign_out"
        else get_attendance_decision(
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
    )
    return _serialize_attendance_decision(decision)


def _attendance_scan_error_detail(
    *,
    code: str,
    message: str,
    **extra: object,
) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
    }
    detail.update(extra)
    return detail


@router.post("/register", response_model=FaceRegistrationResponse)
def register_face_from_base64(
    payload: Base64ImageRequest,
    current_user: UserModel = Depends(get_current_student_user),
    db: Session = Depends(get_db),
):
    profile = _require_student_profile(current_user)
    image_bytes = face_service.decode_base64_image(payload.image_base64)
    encoding, liveness = face_service.extract_encoding_from_bytes(
        image_bytes,
        require_single_face=True,
        enforce_liveness=True,
    )

    profile.update_face_encoding(face_service.encoding_to_bytes(encoding))
    profile.registration_complete = True
    db.commit()
    db.refresh(profile)

    return FaceRegistrationResponse(
        message="Face registered successfully.",
        student_id=profile.student_id,
        liveness=liveness.to_dict(),
    )


@router.post("/register-upload", response_model=FaceRegistrationResponse)
async def register_face_from_upload(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_student_user),
    db: Session = Depends(get_db),
):
    profile = _require_student_profile(current_user)
    image_bytes = await file.read()
    encoding, liveness = face_service.extract_encoding_from_bytes(
        image_bytes,
        require_single_face=True,
        enforce_liveness=True,
    )

    profile.update_face_encoding(face_service.encoding_to_bytes(encoding))
    profile.registration_complete = True
    db.commit()
    db.refresh(profile)

    return FaceRegistrationResponse(
        message="Face registered successfully.",
        student_id=profile.student_id,
        liveness=liveness.to_dict(),
    )


@router.post("/verify", response_model=FaceVerificationResponse)
def verify_face_against_registered_students(
    payload: Base64ImageRequest,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    school_id = get_school_id_or_403(current_user)
    image_bytes = face_service.decode_base64_image(payload.image_base64)
    encoding, liveness = face_service.extract_encoding_from_bytes(
        image_bytes,
        require_single_face=True,
        enforce_liveness=True,
    )

    candidates = get_registered_face_candidates_for_school(db, school_id)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered student faces found in this school.",
        )

    match = face_service.find_best_match(
        encoding,
        [scoped_candidate.candidate for scoped_candidate in candidates],
    )
    if not match.matched or match.candidate is None:
        return FaceVerificationResponse(
            match_found=False,
            distance=round(match.distance, 6) if math.isfinite(match.distance) else None,
            confidence=round(match.confidence, 6),
            threshold=round(match.threshold, 6),
            liveness=liveness.to_dict(),
        )

    student_lookup = {
        scoped_candidate.candidate.identifier: scoped_candidate.student
        for scoped_candidate in candidates
    }
    student = student_lookup.get(match.candidate.identifier)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Matched student could not be loaded.",
        )

    return FaceVerificationResponse(
        match_found=True,
        student_id=student.student_id,
        student_name=student_display_name(student),
        distance=round(match.distance, 6),
        confidence=round(match.confidence, 6),
        threshold=round(match.threshold, 6),
        liveness=liveness.to_dict(),
    )


@router.post("/face-scan-with-recognition", response_model=FaceAttendanceScanResponse)
def record_attendance_from_face_scan(
    payload: FaceAttendanceScanRequest,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    actor_is_staff_scan = has_any_role(
        current_user,
        ["admin", "campus_admin"],
    )
    if not actor_is_staff_scan and governance_hierarchy_service.get_user_governance_unit_types(
        db,
        current_user=current_user,
    ):
        governance_hierarchy_service.ensure_governance_permission(
            db,
            current_user=current_user,
            permission_code=PermissionCode.MANAGE_ATTENDANCE,
            detail=(
                "This governance account has no attendance features yet. "
                "Campus Admin must assign manage_attendance to the governance member."
            ),
        )
        actor_is_staff_scan = True
    actor_is_student_self_scan = (
        not actor_is_staff_scan and has_any_role(current_user, ["student"])
    )

    if not actor_is_staff_scan and not actor_is_student_self_scan:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student, governance attendance operator, or admin access is required for face attendance scans.",
        )

    school_id = get_school_id_or_403(current_user)
    event = _get_school_event_or_404(db, payload.event_id, school_id)
    current_student_profile = (
        _require_student_profile(current_user) if actor_is_student_self_scan else None
    )
    bypass_face_scan = (
        actor_is_student_self_scan
        and current_student_profile is not None
        and is_face_scan_bypass_enabled_for_user(current_user)
    )
    if (
        actor_is_student_self_scan
        and current_student_profile is not None
        and not bypass_face_scan
        and not bool(current_student_profile.is_face_registered)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Register your student face before signing in to an event.",
        )

    if bypass_face_scan:
        participant_ids = set(get_event_participant_student_ids(db, event))
        if current_student_profile.id not in participant_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The signed-in student is outside this event scope.",
            )

        student = current_student_profile
        liveness = LivenessResult(
            label="Bypassed",
            score=1.0,
            reason="face_scan_bypass",
        )
        match_distance = 0.0
        match_confidence = 1.0
        match_threshold = float(payload.threshold or face_service.settings.face_match_threshold)
    else:
        if not payload.image_base64:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A live camera frame is required for face attendance scans.",
            )

        image_bytes = face_service.decode_base64_image(payload.image_base64)
        encoding, liveness = face_service.extract_encoding_from_bytes(
            image_bytes,
            require_single_face=True,
            enforce_liveness=True,
        )

        candidates = get_registered_face_candidates_for_event(db, event)
        if not candidates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered student faces found in this event scope.",
            )

        match = face_service.find_best_match(
            encoding,
            [scoped_candidate.candidate for scoped_candidate in candidates],
            threshold=payload.threshold,
        )
        if not match.matched or match.candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No matching student found.",
            )

        student_lookup = {
            scoped_candidate.candidate.identifier: scoped_candidate.student
            for scoped_candidate in candidates
        }
        student = student_lookup.get(match.candidate.identifier)
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Matched student could not be resolved.",
            )

        match_distance = round(match.distance, 6)
        match_confidence = round(match.confidence, 6)
        match_threshold = round(match.threshold, 6)

    if (
        actor_is_student_self_scan
        and current_student_profile is not None
        and student.id != current_student_profile.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The live face does not match the currently signed-in student account.",
        )

    geo_response = verify_event_geolocation_for_attendance(
        event,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
    )

    scanned_at = datetime.utcnow()
    if (
        geo_response is not None
        and payload.latitude is not None
        and payload.longitude is not None
    ):
        travel_risk = find_attendance_geolocation_travel_risk(
            db,
            student_profile_id=student.id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            scanned_at=scanned_at,
        )
        if travel_risk is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_attendance_scan_error_detail(
                    code="implausible_travel_speed",
                    message=(
                        "Location verification failed because the travel pattern "
                        "looks unrealistic."
                    ),
                    distance_m=round(travel_risk.distance_m, 3),
                    elapsed_s=round(travel_risk.elapsed_s, 3),
                    speed_mps=round(travel_risk.speed_mps, 3),
                ),
            )

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

    if active_attendance is not None:
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_attendance_scan_error_detail(
                    code=sign_out_decision.reason_code or "attendance_not_allowed",
                    message=sign_out_decision.message,
                    **_attendance_time_window_detail(event, action="sign_out"),
                ),
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
                    "display_status": finalized_status,
                },
            )
        db.commit()
        db.refresh(active_attendance)
        duration_minutes = int(
            max(
                0,
                (active_attendance.time_out - active_attendance.time_in).total_seconds() / 60,
            )
        )
        return FaceAttendanceScanResponse(
            action="timeout",
            student_id=student.student_id,
            student_name=student_display_name(student),
            attendance_id=active_attendance.id,
            distance=match_distance,
            confidence=match_confidence,
            threshold=match_threshold,
            liveness=liveness.to_dict(),
            geo=geo_response,
            time_out=active_attendance.time_out,
            duration_minutes=duration_minutes,
            message=(
                "Check-out recorded successfully."
                if finalized_status == "present"
                else "Check-out recorded successfully. Attendance was marked late based on the event late threshold."
                if finalized_status == "late"
                else "Check-out recorded successfully. The attendance remains absent based on the check-in window."
            ),
        )

    completed_attendance = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event.id,
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )
    if completed_attendance is not None and completed_attendance.time_out is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance has already been completed for this student and event.",
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_attendance_scan_error_detail(
                code=attendance_decision.reason_code or "attendance_not_allowed",
                message=attendance_decision.message,
                **_attendance_time_window_detail(event),
            ),
        )

    attendance = AttendanceModel(
        student_id=student.id,
        event_id=event.id,
        time_in=scanned_at,
        method="face_scan",
        status=attendance_decision.attendance_status or "absent",
        check_in_status=attendance_decision.attendance_status,
        check_out_status=None,
        verified_by=current_user.id,
        notes="Pending sign-out.",
        geo_distance_m=geo_response.distance_m if geo_response else None,
        geo_effective_distance_m=geo_response.effective_distance_m if geo_response else None,
        geo_latitude=payload.latitude,
        geo_longitude=payload.longitude,
        geo_accuracy_m=payload.accuracy_m,
        liveness_label=str(liveness.label),
        liveness_score=float(liveness.score),
    )
    db.add(attendance)
    db.flush()
    if student.user is not None:
        notification_category = (
            "late_attendance"
            if attendance_decision.attendance_status == "late"
            else "attendance_sign_in"
        )
        notification_subject = (
            f"Late attendance recorded for {event.name}"
            if notification_category == "late_attendance"
            else f"Sign-in recorded for {event.name}"
        )
        send_attendance_notification(
            db,
            user=student.user,
            school_id=event.school_id,
            category=notification_category,
            subject=notification_subject,
            message=(
                f"Your sign-in for {event.name} was recorded and marked {attendance_decision.attendance_status}."
                " Complete sign-out during the allowed window to validate attendance."
            ),
            metadata_json={
                "event_id": event.id,
                "attendance_id": attendance.id,
                "action": "sign_in",
                "display_status": attendance_decision.attendance_status,
            },
        )
    db.commit()
    db.refresh(attendance)

    time_in_message = (
        "Check-in recorded successfully. Sign out during the sign-out window to complete your attendance."
        if attendance_decision.attendance_status == "present"
        else "Check-in recorded successfully, but it is already inside the late window. Sign out during the sign-out window to finalize attendance."
        if attendance_decision.attendance_status == "late"
        else "Check-in recorded successfully, but it is already beyond the late threshold. Sign out during the sign-out window to finalize your absent attendance record."
    )

    return FaceAttendanceScanResponse(
        action="time_in",
        student_id=student.student_id,
        student_name=student_display_name(student),
        attendance_id=attendance.id,
        distance=match_distance,
        confidence=match_confidence,
        threshold=match_threshold,
        liveness=liveness.to_dict(),
        geo=geo_response,
        time_in=attendance.time_in,
        message=time_in_message,
    )
