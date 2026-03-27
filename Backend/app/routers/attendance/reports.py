"""Reporting routes for the attendance router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.get("/events/{event_id}/report", response_model=AttendanceReportResponse)
def get_event_attendance_report(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_event_report_access(db, current_user)
    governance_units = _get_attendance_governance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    actor_school_id = None
    if not (has_any_role(current_user, ["admin"]) and getattr(current_user, "school_id", None) is None):
        actor_school_id = get_school_id_or_403(current_user)

    event_query = (
        db.query(Event)
        .options(
            joinedload(Event.programs),
            joinedload(Event.departments),
        )
        .filter(Event.id == event_id)
    )
    if actor_school_id is not None:
        event_query = event_query.filter(Event.school_id == actor_school_id)
    event = event_query.first()

    if not event:
        raise HTTPException(404, "Event not found")
    _ensure_event_in_attendance_scope(event, governance_units)
    sync_result = sync_event_workflow_status(db, event)
    if sync_result.changed:
        db.commit()
        db.refresh(event)
    school_id = event.school_id
    if school_id is None:
        raise HTTPException(400, "Event is not linked to a school")

    program_ids = [program.id for program in event.programs]
    department_ids = [department.id for department in event.departments]

    participant_query = (
        db.query(
            StudentProfile.id.label("student_id"),
            StudentProfile.program_id.label("program_id"),
        )
        .join(User, StudentProfile.user_id == User.id)
        .filter(User.school_id == school_id)
    )

    if program_ids:
        participant_query = participant_query.filter(StudentProfile.program_id.in_(program_ids))
    if department_ids:
        participant_query = participant_query.filter(StudentProfile.department_id.in_(department_ids))

    participant_subquery = participant_query.subquery()

    total_participants = (
        db.query(func.count())
        .select_from(participant_subquery)
        .scalar()
        or 0
    )

    totals_by_program = {
        program_id: total
        for program_id, total in (
            db.query(
                participant_subquery.c.program_id,
                func.count().label("total"),
            )
            .group_by(participant_subquery.c.program_id)
            .all()
        )
    }
    attendance_rows = (
        db.query(
            AttendanceModel,
            participant_subquery.c.program_id,
        )
        .join(
            participant_subquery,
            AttendanceModel.student_id == participant_subquery.c.student_id,
        )
        .filter(AttendanceModel.event_id == event.id)
        .order_by(
            AttendanceModel.student_id.asc(),
            AttendanceModel.time_in.desc(),
            AttendanceModel.id.desc(),
        )
        .all()
    )

    latest_attendance_by_student: dict[int, tuple[AttendanceModel, int | None]] = {}
    for attendance, program_id in attendance_rows:
        latest_attendance_by_student.setdefault(attendance.student_id, (attendance, program_id))

    attendees = 0
    late_attendees = 0
    incomplete_attendees = 0
    present_by_program: dict[int | None, int] = {}
    late_by_program: dict[int | None, int] = {}
    incomplete_by_program: dict[int | None, int] = {}

    for attendance, program_id in latest_attendance_by_student.values():
        display_status = _attendance_display_status_value(attendance)
        is_valid = _attendance_is_valid_value(attendance)

        if is_valid:
            attendees += 1
            if display_status == AttendanceStatus.PRESENT.value:
                present_by_program[program_id] = present_by_program.get(program_id, 0) + 1
            elif display_status == AttendanceStatus.LATE.value:
                late_attendees += 1
                late_by_program[program_id] = late_by_program.get(program_id, 0) + 1
        elif display_status == AttendanceStatus.INCOMPLETE.value:
            incomplete_attendees += 1
            incomplete_by_program[program_id] = incomplete_by_program.get(program_id, 0) + 1

    program_ids_from_participants = {
        program_id
        for program_id in totals_by_program.keys()
        if program_id is not None
    }
    program_ids_for_response = program_ids_from_participants | set(program_ids)

    program_models = []
    if program_ids_for_response:
        program_models = (
            db.query(Program)
            .filter(
                Program.school_id == school_id,
                Program.id.in_(program_ids_for_response),
            )
            .order_by(Program.name.asc())
            .all()
        )

    programs_payload = [{"id": program.id, "name": program.name} for program in program_models]
    breakdown_payload = []

    for program in program_models:
        total = int(totals_by_program.get(program.id, 0) or 0)
        present = int(present_by_program.get(program.id, 0) or 0)
        late = int(late_by_program.get(program.id, 0) or 0)
        incomplete = int(incomplete_by_program.get(program.id, 0) or 0)
        absent = max(total - present - late - incomplete, 0)
        breakdown_payload.append(
            {
                "program": program.name,
                "total": total,
                "present": present,
                "late": late,
                "incomplete": incomplete,
                "absent": absent,
            }
        )

    unknown_program_total = int(totals_by_program.get(None, 0) or 0)
    if unknown_program_total > 0:
        unknown_present = int(present_by_program.get(None, 0) or 0)
        unknown_late = int(late_by_program.get(None, 0) or 0)
        unknown_incomplete = int(incomplete_by_program.get(None, 0) or 0)
        breakdown_payload.append(
            {
                "program": "Unassigned",
                "total": unknown_program_total,
                "present": unknown_present,
                "late": unknown_late,
                "incomplete": unknown_incomplete,
                "absent": max(
                    unknown_program_total - unknown_present - unknown_late - unknown_incomplete,
                    0,
                ),
            }
        )

    absentees = max(int(total_participants) - int(attendees) - int(incomplete_attendees), 0)
    attendance_rate = round((attendees / total_participants) * 100, 2) if total_participants else 0.0

    return AttendanceReportResponse(
        event_name=event.name,
        event_date=event.start_datetime.strftime("%Y-%m-%d"),
        event_location=event.location or "N/A",
        total_participants=int(total_participants),
        attendees=int(attendees),
        late_attendees=int(late_attendees),
        incomplete_attendees=int(incomplete_attendees),
        absentees=absentees,
        attendance_rate=attendance_rate,
        programs=programs_payload,
        program_breakdown=breakdown_payload,
    )


@router.get("/students/overview", response_model=List[StudentListItem])
async def get_students_attendance_overview(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    program_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None, description="Filter events from this date"),
    end_date: Optional[date] = Query(None, description="Filter events until this date"),
    governance_context: Optional[GovernanceUnitType] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_report_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    governance_units = _get_attendance_governance_units(
        db,
        current_user=current_user,
        governance_context=governance_context,
    )
    allowed_event_ids = _get_event_ids_in_attendance_scope(
        db,
        school_id=school_id,
        governance_units=governance_units,
    )

    try:
        logger.debug(
            "Building student attendance overview",
            extra={
                "start_date": str(start_date) if start_date else None,
                "end_date": str(end_date) if end_date else None,
                "department_id": department_id,
                "program_id": program_id,
                "search": search,
            },
        )

        base_query = (
            db.query(StudentProfile)
            .join(User, StudentProfile.user_id == User.id)
            .filter(User.school_id == school_id)
        )
        base_query = _apply_student_scope_filters(base_query, governance_units)

        if department_id:
            base_query = base_query.filter(StudentProfile.department_id == department_id)

        if program_id:
            base_query = base_query.filter(StudentProfile.program_id == program_id)

        if search:
            search_filter = f"%{search}%"
            base_query = base_query.filter(
                or_(
                    StudentProfile.student_id.ilike(search_filter),
                    func.concat(
                        User.first_name, ' ',
                        func.coalesce(User.middle_name + ' ', ''),
                        User.last_name
                    ).ilike(search_filter)
                )
            )

        total_students = base_query.count()
        logger.debug("Student attendance overview matched %s students", total_students)

        base_query = base_query.options(
            joinedload(StudentProfile.user),
            joinedload(StudentProfile.department),
            joinedload(StudentProfile.program)
        )

        students = base_query.offset(skip).limit(limit).all()
        logger.debug("Loaded %s students for attendance overview page", len(students))

        if not students:
            return []

        student_ids = [s.id for s in students]

        attendance_stats = {}
        event_counts = {}

        try:
            attendance_query = db.query(AttendanceModel).join(
                Event, AttendanceModel.event_id == Event.id
            ).filter(
                AttendanceModel.student_id.in_(student_ids),
                Event.school_id == school_id,
            )
            if governance_units:
                if not allowed_event_ids:
                    logger.debug("Attendance overview matched no in-scope events")
                    attendance_results = []
                else:
                    attendance_query = attendance_query.filter(Event.id.in_(allowed_event_ids))

            if start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                attendance_query = attendance_query.filter(Event.start_datetime >= start_datetime)

            if end_date:
                end_datetime = datetime.combine(end_date, datetime.max.time())
                attendance_query = attendance_query.filter(Event.start_datetime <= end_datetime)

            attendance_results = (
                attendance_query.order_by(
                    AttendanceModel.student_id.asc(),
                    AttendanceModel.event_id.asc(),
                    AttendanceModel.time_in.desc(),
                    AttendanceModel.id.desc(),
                ).all()
                if (allowed_event_ids or not governance_units)
                else []
            )
            logger.debug(
                "Attendance overview aggregate query returned %s rows",
                len(attendance_results),
            )

            latest_by_student_and_event: dict[tuple[int, int], AttendanceModel] = {}
            for attendance in attendance_results:
                latest_by_student_and_event.setdefault(
                    (attendance.student_id, attendance.event_id),
                    attendance,
                )

            grouped_attendances: dict[int, list[AttendanceModel]] = {}
            for attendance in latest_by_student_and_event.values():
                grouped_attendances.setdefault(attendance.student_id, []).append(attendance)

            for student_id, student_attendances in grouped_attendances.items():
                attendance_stats[student_id] = {
                    "attended": sum(
                        1 for attendance in student_attendances if _attendance_is_valid_value(attendance)
                    ),
                    "last_attendance": max(
                        (attendance.time_in for attendance in student_attendances if attendance.time_in),
                        default=None,
                    ),
                }
                event_counts[student_id] = len(student_attendances)

        except Exception:
            logger.exception("Attendance overview aggregate query failed")
            attendance_stats = {}
            event_counts = {}

        result = []
        for student in students:
            try:
                stats = attendance_stats.get(student.id, {'attended': 0, 'last_attendance': None})
                attended = stats['attended']
                last_attendance = stats['last_attendance']

                total_events = event_counts.get(student.id, 0)

                first_name = getattr(student.user, 'first_name', '') or ''
                middle_name = getattr(student.user, 'middle_name', '') or ''
                last_name = getattr(student.user, 'last_name', '') or ''

                middle_part = f"{middle_name} " if middle_name else ""
                full_name = f"{first_name} {middle_part}{last_name}".strip()

                attendance_rate = round((attended / total_events * 100) if total_events > 0 else 0, 2)

                result.append(StudentListItem(
                    id=student.id,
                    student_id=student.student_id,
                    full_name=full_name,
                    department_name=getattr(student.department, 'name', None) if student.department else None,
                    program_name=getattr(student.program, 'name', None) if student.program else None,
                    year_level=student.year_level,
                    total_events=total_events,
                    attendance_rate=attendance_rate,
                    last_attendance=last_attendance
                ))

            except Exception:
                logger.exception("Failed to process attendance overview row", extra={"student_id": student.id})
                continue

        logger.debug("Returning %s student attendance overview rows", len(result))
        return result

    except Exception as exc:
        logger.exception("Attendance overview request failed")
        raise HTTPException(500, f"Database error: {str(exc)}") from exc


@router.get("/students/{student_id}/report", response_model=StudentAttendanceReport)
def get_student_attendance_report(
    student_id: int,
    start_date: Optional[date] = Query(None, description="Filter events from this date"),
    end_date: Optional[date] = Query(None, description="Filter events until this date"),
    status: Optional[AttendanceStatus] = Query(None, description="Filter by attendance status"),
    event_type: Optional[str] = Query(None, description="Filter by event type/category"),
    governance_context: Optional[GovernanceUnitType] = Query(None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    can_view_own_records = (
        has_any_role(current_user, ["student"])
        and current_user.student_profile is not None
        and current_user.student_profile.id == student_id
    )
    if not can_view_own_records:
        _ensure_attendance_report_access(db, current_user)
    school_id = get_school_id_or_403(current_user)
    governance_units = (
        []
        if can_view_own_records
        else _get_attendance_governance_units(
            db,
            current_user=current_user,
            governance_context=governance_context,
        )
    )
    allowed_event_ids = _get_event_ids_in_attendance_scope(
        db,
        school_id=school_id,
        governance_units=governance_units,
    )

    student = db.query(StudentProfile).options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.department),
        joinedload(StudentProfile.program)
    ).join(User, StudentProfile.user_id == User.id).filter(
        StudentProfile.id == student_id,
        User.school_id == school_id,
    ).first()

    if not student:
        raise HTTPException(404, "Student not found")
    _ensure_student_in_attendance_scope(student, governance_units)

    attendances: list[AttendanceModel] = []
    attendance_query = db.query(AttendanceModel).options(
        joinedload(AttendanceModel.event)
    ).join(Event, AttendanceModel.event_id == Event.id).filter(
        AttendanceModel.student_id == student_id,
        Event.school_id == school_id,
    )
    if governance_units:
        if not allowed_event_ids:
            attendances = []
            attendance_query = None
        else:
            attendance_query = attendance_query.filter(Event.id.in_(allowed_event_ids))

    if attendance_query is not None and start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        attendance_query = attendance_query.filter(Event.start_datetime >= start_datetime)

    if attendance_query is not None and end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        attendance_query = attendance_query.filter(Event.start_datetime <= end_datetime)

    if attendance_query is not None and event_type:
        attendance_query = attendance_query.filter(Event.event_type == event_type)

    if attendance_query is not None:
        attendances = attendance_query.order_by(Event.start_datetime.desc()).all()

    if status is not None:
        attendances = [attendance for attendance in attendances if _attendance_matches_status_filter(attendance, status)]

    total_attended = len([a for a in attendances if _attendance_is_valid_value(a)])
    total_late = len(
        [
            a
            for a in attendances
            if _attendance_display_status_value(a) == AttendanceStatus.LATE.value
            and _attendance_is_valid_value(a)
        ]
    )
    total_incomplete = len(
        [a for a in attendances if _attendance_display_status_value(a) == AttendanceStatus.INCOMPLETE.value]
    )
    total_absent = len(
        [a for a in attendances if _attendance_display_status_value(a) == AttendanceStatus.ABSENT.value]
    )
    total_excused = len(
        [a for a in attendances if _attendance_display_status_value(a) == AttendanceStatus.EXCUSED.value]
    )
    total_events = len(attendances)

    attendance_rate = (total_attended / total_events * 100) if total_events > 0 else 0
    last_attendance = max([a.time_in for a in attendances if a.time_in]) if attendances else None

    middle_name = student.user.middle_name
    full_name = f"{student.user.first_name} {middle_name + ' ' if middle_name else ''}{student.user.last_name}"

    summary = StudentAttendanceSummary(
        student_id=student.student_id,
        student_name=full_name,
        total_events=total_events,
        attended_events=total_attended,
        late_events=total_late,
        incomplete_events=total_incomplete,
        absent_events=total_absent,
        excused_events=total_excused,
        attendance_rate=round(attendance_rate, 2),
        last_attendance=last_attendance
    )

    attendance_records = []
    for attendance in attendances:
        attendance_records.append(_build_student_attendance_detail(attendance))

    monthly_stats = {}
    for attendance in attendances:
        if attendance.event and attendance.event.start_datetime:
            month_key = attendance.event.start_datetime.strftime("%Y-%m")
            if month_key not in monthly_stats:
                monthly_stats[month_key] = empty_attendance_display_status_counts()
            status_value = _attendance_display_status_value(attendance)
            monthly_stats[month_key][status_value] = monthly_stats[month_key].get(status_value, 0) + 1

    event_type_stats = {}
    for attendance in attendances:
        if attendance.event:
            event_type = getattr(attendance.event, 'event_type', 'Regular Events')
            event_type_stats[event_type] = event_type_stats.get(event_type, 0) + 1

    return StudentAttendanceReport(
        student=summary,
        attendance_records=attendance_records,
        monthly_stats=monthly_stats,
        event_type_stats=event_type_stats
    )


@router.get("/students/{student_id}/stats")
def get_student_attendance_stats(
    student_id: int,
    start_date: Optional[date] = Query(None, description="Filter events from this date"),
    end_date: Optional[date] = Query(None, description="Filter events until this date"),
    group_by: Optional[str] = Query("month", description="Group by: month, week, day"),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    can_view_own_records = (
        has_any_role(current_user, ["student"])
        and current_user.student_profile is not None
        and current_user.student_profile.id == student_id
    )
    if not can_view_own_records:
        _ensure_attendance_report_access(db, current_user)
    school_id = get_school_id_or_403(current_user)

    student_in_school = db.query(StudentProfile.id).join(
        User, StudentProfile.user_id == User.id
    ).filter(
        StudentProfile.id == student_id,
        User.school_id == school_id,
    ).first()
    if not student_in_school:
        raise HTTPException(404, "Student not found")

    base_query = db.query(AttendanceModel).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(
        AttendanceModel.student_id == student_id,
        Event.school_id == school_id,
    )

    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        base_query = base_query.filter(Event.start_datetime >= start_datetime)

    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        base_query = base_query.filter(Event.start_datetime <= end_datetime)

    status_counts = base_query.with_entities(
        AttendanceModel.status,
        func.count(AttendanceModel.id).label('count')
    ).group_by(AttendanceModel.status).all()

    date_trunc_mapping = {
        "day": "day",
        "week": "week",
        "month": "month",
        "year": "year"
    }

    trunc_period = date_trunc_mapping.get(group_by, "month")

    trend_query = base_query.with_entities(
        func.date_trunc(trunc_period, Event.start_datetime).label('period'),
        AttendanceModel.status,
        func.count(AttendanceModel.id).label('count')
    ).filter(
        Event.start_datetime.isnot(None)
    ).group_by(
        func.date_trunc(trunc_period, Event.start_datetime),
        AttendanceModel.status
    ).order_by('period')

    trend_results = trend_query.all()

    event_type_query = base_query.join(Event).with_entities(
        Event.event_type.label('type'),
        AttendanceModel.status,
        func.count(AttendanceModel.id).label('count')
    ).group_by(Event.event_type, AttendanceModel.status).all()

    status_distribution = empty_attendance_status_counts()
    for row in status_counts:
        status_distribution[normalize_attendance_status(row.status)] = int(row.count)

    return {
        "status_distribution": status_distribution,
        "trend_data": [
            {
                "period": row.period.strftime(
                    "%Y-%m-%d" if group_by == "day"
                    else "%Y-%m" if group_by == "month"
                    else "%Y-%U" if group_by == "week"
                    else "%Y"
                ) if row.period else None,
                "status": normalize_attendance_status(row.status),
                "count": row.count
            }
            for row in trend_results
        ],
        "event_type_breakdown": [
            {
                "event_type": row.type or "Unknown",
                "status": normalize_attendance_status(row.status),
                "count": row.count
            }
            for row in event_type_query
        ],
        "date_range": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "group_by": group_by
        }
    }


@router.get("/summary", response_model=Dict[str, Any])
def get_attendance_summary(
    start_date: Optional[date] = Query(None, description="Filter events from this date"),
    end_date: Optional[date] = Query(None, description="Filter events until this date"),
    department_id: Optional[int] = Query(None),
    program_id: Optional[int] = Query(None),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _ensure_attendance_report_access(db, current_user)
    school_id = get_school_id_or_403(current_user)

    query = db.query(AttendanceModel).join(
        Event, AttendanceModel.event_id == Event.id
    ).filter(Event.school_id == school_id)

    if start_date:
        query = query.filter(Event.start_datetime >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(Event.start_datetime <= datetime.combine(end_date, datetime.max.time()))

    if department_id or program_id:
        query = query.join(StudentProfile, AttendanceModel.student_id == StudentProfile.id).join(
            User, StudentProfile.user_id == User.id
        ).filter(User.school_id == school_id)
        if department_id:
            query = query.filter(StudentProfile.department_id == department_id)
        if program_id:
            query = query.filter(StudentProfile.program_id == program_id)

    total_records = query.count()
    present_count = query.filter(AttendanceModel.status == "present").count()
    late_count = query.filter(AttendanceModel.status == "late").count()
    absent_count = query.filter(AttendanceModel.status == "absent").count()
    excused_count = query.filter(AttendanceModel.status == "excused").count()
    attended_count = present_count + late_count

    unique_students = query.with_entities(AttendanceModel.student_id).distinct().count()
    unique_events = query.with_entities(AttendanceModel.event_id).distinct().count()

    return {
        "summary": {
            "total_attendance_records": total_records,
            "present_count": present_count,
            "late_count": late_count,
            "attended_count": attended_count,
            "absent_count": absent_count,
            "excused_count": excused_count,
            "attendance_rate": round((attended_count / total_records * 100) if total_records > 0 else 0, 2),
            "unique_students": unique_students,
            "unique_events": unique_events
        },
        "filters_applied": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "department_id": department_id,
            "program_id": program_id
        }
    }
