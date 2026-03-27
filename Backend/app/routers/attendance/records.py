"""Record/query routes for the attendance router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.get("/events/{event_id}/attendees", response_model=List[Attendance])
def get_event_attendees(
    event_id: int,
    status: Optional[AttendanceStatus] = None,
    skip: int = 0,
    limit: int = 100,
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    event = _get_event_in_school_or_404(db, event_id, school_id)
    _ensure_event_in_attendance_scope(
        event,
        _get_attendance_governance_units(
            db,
            current_user=current_user,
            governance_context=governance_context,
        ),
    )

    query = db.query(AttendanceModel).filter(
        AttendanceModel.event_id == event_id
    )

    attendances = query.order_by(
        AttendanceModel.status,
        AttendanceModel.time_in
    ).all()
    filtered = [attendance for attendance in attendances if _attendance_matches_status_filter(attendance, status)]
    return [
        _serialize_attendance_model(attendance)
        for attendance in filtered[skip : skip + limit]
    ]


@router.get("/events/{event_id}/attendances", response_model=List[AttendanceWithStudent])
def get_attendances_by_event(
    event_id: int,
    active_only: bool = Query(True, description="Only show active attendances (no time_out)"),
    skip: int = 0,
    limit: int = 100,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
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

    query = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name
    )\
    .join(StudentProfile, AttendanceModel.student_id == StudentProfile.id)\
    .join(User, StudentProfile.user_id == User.id)\
    .join(Event, AttendanceModel.event_id == Event.id)\
    .filter(
        AttendanceModel.event_id == event_id,
        Event.school_id == school_id,
        User.school_id == school_id,
    )

    if active_only:
        query = query.filter(AttendanceModel.time_out.is_(None))

    results = query.order_by(AttendanceModel.time_in.desc())\
                  .offset(skip)\
                  .limit(limit)\
                  .all()

    return [
        _serialize_attendance_with_student(
            attendance,
            student_id=student_id,
            student_name=f"{first_name} {last_name}",
        )
        for attendance, student_id, first_name, last_name in results
    ]


@router.get("/events/{event_id}/attendances/{status}", response_model=List[Attendance])
def get_attendances_by_event_and_status(
    event_id: int,
    status: AttendanceStatus,
    skip: int = 0,
    limit: int = 100,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
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
    attendances = db.query(AttendanceModel)\
        .join(Event, AttendanceModel.event_id == Event.id)\
        .filter(
            AttendanceModel.event_id == event_id,
            Event.school_id == school_id,
        )\
        .order_by(AttendanceModel.time_in.desc())\
        .all()
    filtered = [attendance for attendance in attendances if _attendance_matches_status_filter(attendance, status)]
    return [_serialize_attendance_model(attendance) for attendance in filtered[skip : skip + limit]]


@router.get("/events/{event_id}/attendances-with-students", response_model=List[AttendanceWithStudent])
def get_attendances_with_students(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
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

    results = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name
    )\
    .join(StudentProfile, AttendanceModel.student_id == StudentProfile.id)\
    .join(User, StudentProfile.user_id == User.id)\
    .join(Event, AttendanceModel.event_id == Event.id)\
    .filter(
        AttendanceModel.event_id == event_id,
        Event.school_id == school_id,
        User.school_id == school_id,
    )\
    .all()

    return [
        _serialize_attendance_with_student(
            attendance,
            student_id=student_id,
            student_name=f"{first_name} {last_name}",
        )
        for attendance, student_id, first_name, last_name in results
    ]


@router.get("/students/records", response_model=List[StudentAttendanceResponse])
def get_all_student_attendance_records(
    student_ids: List[str] = Query(None, description="Filter by specific student IDs"),
    event_id: Optional[int] = Query(None, description="Filter by event ID"),
    status: Optional[AttendanceStatus] = Query(None, description="Filter by status"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    _ensure_attendance_operator_access(db, current_user)
    school_id = get_school_id_or_403(current_user)

    query = db.query(
        AttendanceModel,
        StudentProfile.student_id,
        User.first_name,
        User.last_name,
        Event.name.label('event_name')
    ).join(
        StudentProfile, AttendanceModel.student_id == StudentProfile.id
    ).join(
        User, StudentProfile.user_id == User.id
    ).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        User.school_id == school_id,
        Event.school_id == school_id,
    )

    if student_ids:
        query = query.filter(StudentProfile.student_id.in_(student_ids))
    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    results = query.order_by(
        StudentProfile.student_id,
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    student_records = {}
    for attendance, student_id, first_name, last_name, event_name in results:
        if not _attendance_matches_status_filter(attendance, status):
            continue

        record = _build_student_attendance_record(
            attendance,
            event_name=event_name,
        )

        if student_id not in student_records:
            student_records[student_id] = {
                'student_id': student_id,
                'student_name': f"{first_name} {last_name}",
                'attendances': []
            }
        student_records[student_id]['attendances'].append(record)

    response = []
    for student_id, data in student_records.items():
        response.append(StudentAttendanceResponse(
            student_id=student_id,
            student_name=data['student_name'],
            total_records=len(data['attendances']),
            attendances=data['attendances']
        ))

    return response


@router.get("/students/{student_id}/records", response_model=StudentAttendanceResponse)
def get_student_attendance_records(
    student_id: str,
    event_id: Optional[int] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    if has_any_role(current_user, ["student"]) and current_user.student_profile and current_user.student_profile.student_id != student_id:
        raise HTTPException(403, "Can only view your own records")
    school_id = get_school_id_or_403(current_user)

    student = db.query(StudentProfile).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.student_id == student_id,
        User.school_id == school_id,
    ).first()

    if not student:
        raise HTTPException(404, "Student not found")

    query = db.query(
        AttendanceModel,
        Event.name.label('event_name')
    ).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == student.id,
        Event.school_id == school_id,
    )

    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    results = query.order_by(
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    attendances = []
    for attendance, event_name in results:
        if not _attendance_matches_status_filter(attendance, status):
            continue

        attendances.append(
            _build_student_attendance_record(
                attendance,
                event_name=event_name,
            )
        )

    return StudentAttendanceResponse(
        student_id=student_id,
        student_name=f"{student.user.first_name} {student.user.last_name}",
        total_records=len(attendances),
        attendances=attendances
    )


@router.get("/me/records", response_model=List[StudentAttendanceResponse])
def get_my_attendance_records(
    current_user: UserModel = Depends(get_current_user),
    event_id: Optional[int] = Query(None),
    status: Optional[AttendanceStatus] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    if not current_user.student_profile:
        raise HTTPException(
            status_code=403,
            detail="Only students can access their own attendance records"
        )
    school_id = get_school_id_or_403(current_user)

    student = current_user.student_profile

    query = db.query(
        AttendanceModel,
        Event.name.label('event_name')
    ).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == student.id,
        Event.school_id == school_id,
    )

    if event_id:
        query = query.filter(AttendanceModel.event_id == event_id)
    results = query.order_by(
        AttendanceModel.time_in.desc()
    ).offset(skip).limit(limit).all()

    attendances = []
    for attendance, event_name in results:
        if not _attendance_matches_status_filter(attendance, status):
            continue

        attendances.append(
            _build_student_attendance_record(
                attendance,
                event_name=event_name,
            )
        )

    return [StudentAttendanceResponse(
        student_id=student.student_id,
        student_name=f"{current_user.first_name} {current_user.last_name}",
        total_records=len(attendances),
        attendances=attendances
    )]
