"""Use: Handles security center features and privileged account checks API endpoints.
Where to use: Use this through the FastAPI app when the frontend or an API client needs security center features and privileged account checks features.
Role: Router layer. It receives HTTP requests, checks access rules, and returns API responses.
"""

from __future__ import annotations

from datetime import datetime

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    decode_token_to_token_data,
    get_current_admin_or_campus_admin,
    get_current_application_user,
    oauth2_scheme,
)
from app.core.dependencies import get_db
from app.models.face_recognition import UserFaceRecognitionProfile
from app.models.platform_features import UserSession
from app.models.user import User
from app.schemas.face_recognition import (
    Base64ImageRequest,
    SecurityFaceLivenessResponse,
    SecurityFaceReferenceResponse,
    SecurityFaceStatusResponse,
    SecurityFaceVerificationRequest,
    SecurityFaceVerificationResponse,
)
from app.schemas.security import (
    LoginHistoryItem,
    MfaStatusResponse,
    MfaStatusUpdate,
    RevokeSessionResponse,
    UserSessionItem,
)
from app.services.auth_session import issue_full_access_token_response
from app.services.security_service import (
    get_or_create_security_setting,
    list_active_sessions,
    list_login_history_for_actor,
    record_login_history,
    revoke_other_sessions,
    revoke_session,
)
from app.services.face_recognition import FaceRecognitionService

router = APIRouter(prefix="/auth/security", tags=["security"])
face_service = FaceRecognitionService()


def _extract_current_jti(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        return str(jti) if jti else None
    except JWTError:
        return None


@router.get("/mfa-status", response_model=MfaStatusResponse)
def get_mfa_status(
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    setting = get_or_create_security_setting(db, current_user)
    db.commit()
    db.refresh(setting)
    return MfaStatusResponse(
        user_id=current_user.id,
        mfa_enabled=setting.mfa_enabled,
        trusted_device_days=setting.trusted_device_days,
        updated_at=setting.updated_at,
    )


@router.put("/mfa-status", response_model=MfaStatusResponse)
def update_mfa_status(
    payload: MfaStatusUpdate,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    setting = get_or_create_security_setting(db, current_user)
    setting.mfa_enabled = payload.mfa_enabled
    if payload.trusted_device_days is not None:
        setting.trusted_device_days = payload.trusted_device_days
    db.commit()
    db.refresh(setting)
    return MfaStatusResponse(
        user_id=current_user.id,
        mfa_enabled=setting.mfa_enabled,
        trusted_device_days=setting.trusted_device_days,
        updated_at=setting.updated_at,
    )


@router.get("/sessions", response_model=list[UserSessionItem])
def get_active_sessions(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    current_jti = _extract_current_jti(token)
    sessions = list_active_sessions(db, actor_user_id=current_user.id)
    return [
        UserSessionItem(
            id=item.id,
            token_jti=item.token_jti,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            revoked_at=item.revoked_at,
            expires_at=item.expires_at,
            is_current=(current_jti is not None and item.token_jti == current_jti),
        )
        for item in sessions
    ]


@router.post("/sessions/{session_id}/revoke", response_model=RevokeSessionResponse)
def revoke_user_session(
    session_id: str,
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    revoked = revoke_session(
        db,
        session_id=session_id,
        actor_user_id=current_user.id,
        allow_self=True,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")
    db.commit()
    return RevokeSessionResponse(session_id=session_id, revoked=True)


@router.post("/sessions/revoke-others")
def revoke_all_other_sessions(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    current_jti = _extract_current_jti(token)
    current_session_id = None
    if current_jti:
        current_session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == current_user.id,
                UserSession.token_jti == current_jti,
            )
            .first()
        )
        if current_session is not None:
            current_session_id = current_session.id
    count = revoke_other_sessions(
        db,
        actor_user_id=current_user.id,
        current_session_id=current_session_id,
    )
    db.commit()
    return {"revoked_count": count}


@router.get("/login-history", response_model=list[LoginHistoryItem])
def get_login_history(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_application_user),
    db: Session = Depends(get_db),
):
    rows = list_login_history_for_actor(db, actor=current_user, limit=limit)
    return rows


@router.get("/face-status", response_model=SecurityFaceStatusResponse)
def get_face_status(
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserFaceRecognitionProfile)
        .filter(UserFaceRecognitionProfile.user_id == current_user.id)
        .first()
    )
    face_runtime_ready, face_runtime_reason = face_service.face_recognition_status()
    anti_spoof_ready, anti_spoof_reason = face_service.anti_spoof_status()
    if not face_runtime_ready:
        anti_spoof_ready = False
        anti_spoof_reason = face_runtime_reason
    return SecurityFaceStatusResponse(
        user_id=current_user.id,
        face_verification_required=True,
        face_reference_enrolled=profile is not None,
        provider=(profile.provider if profile is not None else "face_recognition"),
        updated_at=(profile.updated_at if profile is not None else None),
        last_verified_at=(profile.last_verified_at if profile is not None else None),
        liveness_enabled=True,
        anti_spoof_ready=anti_spoof_ready,
        anti_spoof_reason=anti_spoof_reason,
        live_capture_required=True,
    )


@router.post("/face-liveness", response_model=SecurityFaceLivenessResponse)
def check_face_liveness(
    payload: Base64ImageRequest,
    current_user: User = Depends(get_current_admin_or_campus_admin),
):
    image_bytes = face_service.decode_base64_image(payload.image_base64)
    rgb_image = face_service.load_rgb_from_bytes(image_bytes)
    liveness = face_service.check_liveness(rgb_image)
    return SecurityFaceLivenessResponse(**liveness.to_dict())


@router.post("/face-reference", response_model=SecurityFaceReferenceResponse)
def save_face_reference(
    payload: Base64ImageRequest,
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    image_bytes = face_service.decode_base64_image(payload.image_base64)
    encoding, liveness = face_service.extract_encoding_from_bytes(
        image_bytes,
        require_single_face=True,
        enforce_liveness=True,
    )

    profile = (
        db.query(UserFaceRecognitionProfile)
        .filter(UserFaceRecognitionProfile.user_id == current_user.id)
        .first()
    )
    if profile is None:
        profile = UserFaceRecognitionProfile(
            user_id=current_user.id,
            face_encoding=face_service.encoding_to_bytes(encoding),
            provider="face_recognition",
            reference_image_sha256=face_service.compute_image_sha256(image_bytes),
        )
        db.add(profile)
    else:
        profile.face_encoding = face_service.encoding_to_bytes(encoding)
        profile.reference_image_sha256 = face_service.compute_image_sha256(image_bytes)

    db.commit()
    db.refresh(profile)

    return SecurityFaceReferenceResponse(
        user_id=current_user.id,
        face_reference_enrolled=True,
        provider=profile.provider,
        updated_at=profile.updated_at,
        liveness=liveness.to_dict(),
    )


@router.delete("/face-reference")
def delete_face_reference(
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserFaceRecognitionProfile)
        .filter(UserFaceRecognitionProfile.user_id == current_user.id)
        .first()
    )
    if profile is not None:
        db.delete(profile)
        db.commit()
    return {"user_id": current_user.id, "face_reference_enrolled": False}


@router.post("/face-verify", response_model=SecurityFaceVerificationResponse)
def verify_face_reference(
    payload: SecurityFaceVerificationRequest,
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserFaceRecognitionProfile)
        .filter(UserFaceRecognitionProfile.user_id == current_user.id)
        .first()
    )
    if profile is None or not profile.face_encoding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No face reference is enrolled for this account.",
        )

    image_bytes = face_service.decode_base64_image(payload.image_base64)
    encoding, liveness = face_service.extract_encoding_from_bytes(
        image_bytes,
        require_single_face=True,
        enforce_liveness=True,
    )
    comparison = face_service.compare_encodings(
        encoding,
        face_service.encoding_from_bytes(bytes(profile.face_encoding)),
        threshold=payload.threshold,
    )
    token_data = decode_token_to_token_data(token)
    issued_session: dict[str, object | None] | None = None

    if comparison.matched:
        profile.last_verified_at = datetime.utcnow()
        if token_data.face_pending:
            issued_session = issue_full_access_token_response(
                db=db,
                user=current_user,
                request=request,
            )
            record_login_history(
                db,
                email_attempted=current_user.email,
                user=current_user,
                success=True,
                auth_method="face_verification",
                request=request,
            )
        db.commit()
        db.refresh(profile)

    return SecurityFaceVerificationResponse(
        matched=comparison.matched,
        distance=round(comparison.distance, 6),
        confidence=round(comparison.confidence, 6),
        threshold=round(comparison.threshold, 6),
        liveness=liveness.to_dict(),
        verified_at=(profile.last_verified_at if comparison.matched else None),
        access_token=(
            str(issued_session["access_token"])
            if issued_session is not None and issued_session.get("access_token") is not None
            else None
        ),
        token_type=(
            str(issued_session["token_type"])
            if issued_session is not None and issued_session.get("token_type") is not None
            else None
        ),
        session_id=(
            str(issued_session["session_id"])
            if issued_session is not None and issued_session.get("session_id") is not None
            else None
        ),
        face_verification_pending=(
            bool(issued_session.get("face_verification_pending"))
            if issued_session is not None
            else bool(token_data.face_pending and not comparison.matched)
        ),
    )

