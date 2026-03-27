"""Override routes for the attendance router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/events/{event_id}/mark-excused")
def mark_excused_attendance(
    event_id: int,
    student_ids: List[str],
    reason: str,
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

    students = db.query(StudentProfile).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.student_id.in_(student_ids),
        User.school_id == school_id,
    ).all()

    for student in students:
        _ensure_student_in_attendance_scope(student, governance_units)
        _ensure_student_is_event_participant(student, event)
        attendance = db.query(AttendanceModel).filter(
            AttendanceModel.student_id == student.id,
            AttendanceModel.event_id == event_id
        ).first()

        if attendance:
            attendance.status = AttendanceStatus.EXCUSED
            attendance.notes = reason
        else:
            attendance = AttendanceModel(
                student_id=student.id,
                event_id=event_id,
                status=AttendanceStatus.EXCUSED,
                notes=reason,
                method="manual",
                verified_by=current_user.id
            )
            db.add(attendance)

    db.commit()
    return {"message": f"Marked {len(students)} students as excused"}


@router.post("/mark-absent-no-timeout")
def mark_absent_no_timeout(
    event_id: int,
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

    if event.status != EventStatus.COMPLETED:
        raise HTTPException(400, "Can only mark absent for completed events")

    attendances_to_update = db.query(AttendanceModel).filter(
        AttendanceModel.event_id == event_id,
        AttendanceModel.time_in.isnot(None),
        AttendanceModel.time_out.is_(None),
        AttendanceModel.status.in_(["present", "late", "absent"]),
    ).all()

    updated_count = 0
    for attendance in attendances_to_update:
        attendance.check_out_status = "absent"
        attendance.status, final_note = finalize_completed_attendance_status(
            check_in_status=attendance.check_in_status or attendance.status,
            check_out_status=attendance.check_out_status,
        )
        attendance.notes = (
            f"Auto-marked absent - no sign-out recorded. {final_note or attendance.notes or ''}"
        ).strip()
        updated_count += 1

    db.commit()

    return {
        "message": f"Marked {updated_count} students as absent",
        "event_id": event_id,
        "updated_count": updated_count
    }
