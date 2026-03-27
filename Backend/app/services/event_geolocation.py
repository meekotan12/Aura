"""Use: Contains the main backend rules for event location verification.
Where to use: Use this from routers, workers, or other services when event location verification logic is needed.
Role: Service layer. It keeps business logic out of the route files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.attendance import Attendance as AttendanceModel
from app.models.event import Event as EventModel
from app.schemas.event import (
    EventAttendanceDecisionInfo,
    EventLocationVerificationResponse,
    EventTimeStatusInfo,
)
from app.services.event_time_status import get_attendance_decision, get_event_status
from app.services.geolocation import GeoCheckResult, geofence_check, haversine_m

settings = get_settings()


@dataclass(frozen=True)
class AttendanceGeolocationTravelRisk:
    distance_m: float
    elapsed_s: float
    speed_mps: float


def validate_event_geolocation_fields(
    *,
    latitude: float | None,
    longitude: float | None,
    radius_m: float | None,
    required: bool,
) -> None:
    provided = [latitude is not None, longitude is not None, radius_m is not None]
    if any(provided) and not all(provided):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event geofence requires latitude, longitude, and radius together.",
        )
    if required and not all(provided):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geofence coordinates and radius are required when geolocation is enabled.",
        )


def build_event_time_status_info(event: EventModel) -> EventTimeStatusInfo:
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
    return EventTimeStatusInfo(**time_status.to_dict())


def build_event_attendance_decision_info(event: EventModel) -> EventAttendanceDecisionInfo:
    decision = get_attendance_decision(
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
    return EventAttendanceDecisionInfo(**decision.to_dict())


def build_event_location_verification_response(
    geo_result: GeoCheckResult,
    *,
    accuracy_m: float | None,
    time_status: EventTimeStatusInfo | None = None,
    attendance_decision: EventAttendanceDecisionInfo | None = None,
) -> EventLocationVerificationResponse:
    return EventLocationVerificationResponse(
        ok=geo_result.ok,
        reason=geo_result.reason,
        distance_m=round(geo_result.distance_m, 3),
        effective_distance_m=(
            round(geo_result.effective_distance_m, 3)
            if geo_result.effective_distance_m is not None
            else None
        ),
        radius_m=round(geo_result.radius_m, 3),
        accuracy_m=round(accuracy_m, 3) if accuracy_m is not None else None,
        time_status=time_status,
        attendance_decision=attendance_decision,
    )


def build_event_geolocation_error_detail(
    *,
    code: str,
    message: str,
    response: EventLocationVerificationResponse | None = None,
    **extra: object,
) -> dict[str, object]:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if response is not None:
        detail.update(response.model_dump())
    detail.update(extra)
    return detail


def _event_has_geolocation_config(event: EventModel) -> bool:
    return (
        event.geo_latitude is not None
        and event.geo_longitude is not None
        and event.geo_radius_m is not None
    )


def _run_event_geolocation_check(
    event: EventModel,
    *,
    latitude: float,
    longitude: float,
    accuracy_m: float | None,
) -> GeoCheckResult:
    return geofence_check(
        user_lat=latitude,
        user_lng=longitude,
        event_lat=float(event.geo_latitude),
        event_lng=float(event.geo_longitude),
        radius_m=float(event.geo_radius_m),
        accuracy_m=accuracy_m,
        max_allowed_accuracy_m=float(
            event.geo_max_accuracy_m or settings.geo_max_allowed_accuracy_m
        ),
        require_accuracy=bool(event.geo_required),
    )


def verify_event_geolocation(
    event: EventModel,
    *,
    latitude: float,
    longitude: float,
    accuracy_m: float | None,
) -> EventLocationVerificationResponse:
    if not _event_has_geolocation_config(event):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=build_event_geolocation_error_detail(
                code="event_geolocation_not_configured",
                message="Event geolocation is not configured.",
            ),
        )

    geo_result = _run_event_geolocation_check(
        event,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
    )
    return build_event_location_verification_response(
        geo_result,
        accuracy_m=accuracy_m,
        time_status=build_event_time_status_info(event),
        attendance_decision=build_event_attendance_decision_info(event),
    )


def verify_event_geolocation_for_attendance(
    event: EventModel,
    *,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
) -> EventLocationVerificationResponse | None:
    if not _event_has_geolocation_config(event):
        if bool(event.geo_required):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=build_event_geolocation_error_detail(
                    code="event_geolocation_required_but_not_configured",
                    message="Event geolocation is required but not configured.",
                ),
            )
        return None

    if latitude is None or longitude is None:
        if bool(event.geo_required):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=build_event_geolocation_error_detail(
                    code="event_geolocation_coordinates_required",
                    message="Latitude and longitude are required for this event.",
                ),
            )
        return None

    geo_result = _run_event_geolocation_check(
        event,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
    )
    response = build_event_location_verification_response(
        geo_result,
        accuracy_m=accuracy_m,
        time_status=build_event_time_status_info(event),
        attendance_decision=build_event_attendance_decision_info(event),
    )
    if not geo_result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=build_event_geolocation_error_detail(
                code="event_geolocation_verification_failed",
                message="The current location is not valid for this event attendance scan.",
                response=response,
            ),
        )
    return response


def find_attendance_geolocation_travel_risk(
    db: Session,
    *,
    student_profile_id: int,
    latitude: float,
    longitude: float,
    scanned_at: datetime,
) -> AttendanceGeolocationTravelRisk | None:
    previous = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student_profile_id,
            AttendanceModel.geo_latitude.isnot(None),
            AttendanceModel.geo_longitude.isnot(None),
            AttendanceModel.time_in.isnot(None),
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )
    if previous is None or previous.time_in is None:
        return None

    elapsed_seconds = (scanned_at - previous.time_in).total_seconds()
    if elapsed_seconds <= 0:
        return None

    distance_m = haversine_m(
        float(previous.geo_latitude),
        float(previous.geo_longitude),
        float(latitude),
        float(longitude),
    )
    speed_mps = distance_m / elapsed_seconds
    if speed_mps <= settings.geo_max_travel_speed_mps:
        return None

    return AttendanceGeolocationTravelRisk(
        distance_m=float(distance_m),
        elapsed_s=float(elapsed_seconds),
        speed_mps=float(speed_mps),
    )


__all__ = [
    "AttendanceGeolocationTravelRisk",
    "build_event_attendance_decision_info",
    "build_event_geolocation_error_detail",
    "build_event_location_verification_response",
    "build_event_time_status_info",
    "find_attendance_geolocation_travel_risk",
    "validate_event_geolocation_fields",
    "verify_event_geolocation",
    "verify_event_geolocation_for_attendance",
]
