"""Check-in and check-out routes for the attendance router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.get("/students/me", response_model=List[Attendance])
def get_my_attendance(
    event_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not has_any_role(current_user, ["student"]) or not current_user.student_profile:
        raise HTTPException(403, "User is not a student")
    school_id = get_school_id_or_403(current_user)

    query = db.query(AttendanceModel).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == current_user.student_profile.id,
        Event.school_id == school_id,
    )

    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)

    return query.order_by(AttendanceModel.time_in.desc()).offset(skip).limit(limit).all()


@router.post("/face-scan")
def record_face_scan_attendance(
    event_id: int,
    student_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    event = _get_event_in_school_or_404(db, event_id, school_id)

    student = db.query(StudentProfile).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.student_id == student_id,
        User.school_id == school_id,
    ).first()

    if not student:
        raise HTTPException(404, f"Student {student_id} not found")

    active_attendance = _active_attendance_for_student_event(
        db,
        student_profile_id=student.id,
        event_id=event_id,
    )
    if active_attendance is not None:
        sign_out_decision = _get_event_sign_out_decision(event)
        if not sign_out_decision["attendance_allowed"]:
            raise HTTPException(409, sign_out_decision)

        duration_minutes = _complete_attendance_sign_out(
            active_attendance,
            recorded_at=datetime.utcnow(),
        )
        db.commit()
        db.refresh(active_attendance)
        return {
            "message": f"Time out recorded successfully for {student_id}",
            "attendance_id": active_attendance.id,
            "student_id": student_id,
            "time_in": active_attendance.time_in,
            "time_out": active_attendance.time_out,
            "duration_minutes": duration_minutes,
        }

    attendance_decision = _get_event_attendance_decision(event)
    if not attendance_decision["attendance_allowed"]:
        raise HTTPException(409, attendance_decision)

    existing = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event_id,
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )
    if existing and existing.time_out is not None:
        raise HTTPException(400, f"Attendance already exists for student {student_id}")

    scanned_at = datetime.utcnow()
    status_value = attendance_decision["attendance_status"] or "absent"

    attendance = AttendanceModel(
        student_id=student.id,
        event_id=event_id,
        time_in=scanned_at,
        method="face_scan",
        status=status_value,
        check_in_status=status_value,
        check_out_status=None,
        verified_by=current_user.id
    )

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return {
        "message": "Attendance recorded successfully",
        "attendance_id": attendance.id,
        "student_id": student_id,
        "time_in": attendance.time_in
    }


@router.post("/manual")
def record_manual_attendance(
    data: ManualAttendanceRequest = Body(...),
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    governance_units = _get_attendance_governance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    event = _get_event_in_school_or_404(db, data.event_id, school_id)
    _ensure_event_in_attendance_scope(event, governance_units)

    student = db.query(StudentProfile).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.student_id == data.student_id,
        User.school_id == school_id,
    ).first()

    if not student:
        raise HTTPException(404, f"Student {data.student_id} not found")
    _ensure_student_in_attendance_scope(student, governance_units)
    _ensure_student_is_event_participant(student, event)

    active_attendance = _active_attendance_for_student_event(
        db,
        student_profile_id=student.id,
        event_id=data.event_id,
    )
    if active_attendance is not None:
        sign_out_decision = _get_event_sign_out_decision(event)
        if not sign_out_decision["attendance_allowed"]:
            raise HTTPException(409, sign_out_decision)

        duration_minutes = _complete_attendance_sign_out(
            active_attendance,
            recorded_at=datetime.utcnow(),
        )
        db.commit()
        db.refresh(active_attendance)
        return {
            "message": f"Recorded time out for {data.student_id}",
            "attendance_id": active_attendance.id,
            "action": "time_out",
            "duration_minutes": duration_minutes,
        }

    attendance_decision = _get_event_attendance_decision(event)
    if not attendance_decision["attendance_allowed"]:
        raise HTTPException(409, attendance_decision)

    existing = (
        db.query(AttendanceModel)
        .filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == data.event_id,
        )
        .order_by(AttendanceModel.time_in.desc(), AttendanceModel.id.desc())
        .first()
    )
    if existing and existing.time_out is not None:
        raise HTTPException(400, f"Attendance already exists for student {data.student_id}")

    recorded_at = datetime.utcnow()
    status_value = attendance_decision["attendance_status"] or "absent"

    attendance = AttendanceModel(
        student_id=student.id,
        event_id=data.event_id,
        time_in=recorded_at,
        method="manual",
        status=status_value,
        check_in_status=status_value,
        check_out_status=None,
        verified_by=current_user.id,
        notes=data.notes or "Pending sign-out."
    )

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return {
        "message": f"Recorded attendance for {data.student_id}",
        "attendance_id": attendance.id,
        "action": "time_in",
    }


@router.post("/bulk")
def record_bulk_attendance(
    data: BulkAttendanceRequest,
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    governance_units = _get_attendance_governance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )

    requested_event_ids = {record.event_id for record in data.records}
    allowed_events = {
        event.id: event
        for event in db.query(Event).filter(
            Event.id.in_(requested_event_ids),
            Event.school_id == school_id,
        ).all()
    }
    event_sync_changed = False
    for event in allowed_events.values():
        sync_result = sync_event_workflow_status(db, event)
        event_sync_changed = event_sync_changed or sync_result.changed
    if event_sync_changed:
        db.commit()

    results = []
    for record in data.records:
        event = allowed_events.get(record.event_id)
        if event is None:
            results.append({"student_id": record.student_id, "status": "event_not_in_school"})
            continue
        if not _event_matches_governance_units(event, governance_units):
            results.append({"student_id": record.student_id, "status": "event_not_in_scope"})
            continue
        attendance_decision = _get_event_attendance_decision(event)
        if not attendance_decision["attendance_allowed"]:
            results.append(
                {
                    "student_id": record.student_id,
                    "status": attendance_decision["reason_code"] or "attendance_not_allowed",
                }
            )
            continue

        student = db.query(StudentProfile).join(
            User, StudentProfile.user_id == User.id
        ).filter(
            StudentProfile.student_id == record.student_id,
            User.school_id == school_id,
        ).first()

        if not student:
            results.append({"student_id": record.student_id, "status": "not_found"})
            continue
        if governance_units and not governance_hierarchy_service.governance_units_match_student_scope(
            governance_units,
            department_id=student.department_id,
            program_id=student.program_id,
        ):
            results.append({"student_id": record.student_id, "status": "student_not_in_scope"})
            continue
        try:
            _ensure_student_is_event_participant(student, event)
        except HTTPException:
            results.append({"student_id": record.student_id, "status": "student_not_in_event_scope"})
            continue

        existing = db.query(AttendanceModel).filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == record.event_id
        ).first()

        if existing:
            results.append({"student_id": record.student_id, "status": "exists"})
            continue

        recorded_at = datetime.utcnow()
        attendance = AttendanceModel(
            student_id=student.id,
            event_id=record.event_id,
            time_in=recorded_at,
            method="manual",
            status=attendance_decision["attendance_status"] or "absent",
            check_in_status=attendance_decision["attendance_status"] or "absent",
            check_out_status=None,
            verified_by=current_user.id,
            notes=record.notes or "Pending sign-out."
        )
        db.add(attendance)
        results.append({"student_id": record.student_id, "status": "recorded"})

    db.commit()
    return {"processed": len(results), "results": results}


@router.post("/{attendance_id}/time-out")
def record_time_out(
    attendance_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)

    attendance = db.query(AttendanceModel).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.id == attendance_id
    ).filter(
        Event.school_id == school_id
    ).first()

    if not attendance:
        raise HTTPException(404, "Attendance record not found")
    _ensure_event_in_attendance_scope(
        attendance.event,
        _get_attendance_governance_units(
            db,
            current_user=current_user,
            governance_context=governance_context,
        ),
    )

    if attendance.time_out:
        raise HTTPException(400, "Time-out already recorded")

    sign_out_decision = _get_event_sign_out_decision(attendance.event)
    if not sign_out_decision["attendance_allowed"]:
        raise HTTPException(409, sign_out_decision)

    duration_minutes = _complete_attendance_sign_out(
        attendance,
        recorded_at=datetime.utcnow(),
    )
    db.commit()

    return {
        "message": "Time-out recorded successfully",
        "attendance_id": attendance_id,
        "time_in": attendance.time_in,
        "time_out": attendance.time_out,
        "duration_minutes": duration_minutes}


@router.post("/face-scan-timeout")
def record_face_scan_timeout(
    event_id: int,
    student_id: str,
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    governance_units = _get_attendance_governance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    event = _get_event_in_school_or_404(db, event_id, school_id)
    _ensure_event_in_attendance_scope(event, governance_units)

    student = db.query(StudentProfile).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.student_id == student_id,
        User.school_id == school_id,
    ).first()

    if not student:
        raise HTTPException(404, f"Student {student_id} not found")
    _ensure_student_in_attendance_scope(student, governance_units)
    _ensure_student_is_event_participant(student, event)

    attendance = db.query(AttendanceModel).filter(
        AttendanceModel.student_id == student.id,
        AttendanceModel.event_id == event_id,
        AttendanceModel.time_out.is_(None)
    ).first()

    if not attendance:
        raise HTTPException(404, f"No active attendance found for student {student_id}")

    if attendance.time_out:
        raise HTTPException(400, f"Timeout already recorded for this attendance")

    sign_out_decision = _get_event_sign_out_decision(event)
    if not sign_out_decision["attendance_allowed"]:
        raise HTTPException(409, sign_out_decision)

    duration_minutes = _complete_attendance_sign_out(
        attendance,
        recorded_at=datetime.utcnow(),
    )
    db.commit()

    return {
        "message": "Face scan timeout recorded successfully",
        "attendance_id": attendance.id,
        "student_id": student_id,
        "time_in": attendance.time_in,
        "time_out": attendance.time_out,
        "duration_minutes": duration_minutes
    }
