"""CRUD routes for the event router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/", response_model=EventWithRelations, status_code=status.HTTP_201_CREATED)
def create_event(
    event: EventCreate,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        _ensure_event_manager(db, current_user)
        school_id = _require_school_scope(current_user)
        payload_fields_set = _get_payload_fields_set(event)

        if event.start_datetime >= event.end_datetime:
            raise HTTPException(status_code=400, detail="End datetime must be after start datetime")

        validate_event_geolocation_fields(
            latitude=event.geo_latitude,
            longitude=event.geo_longitude,
            radius_m=event.geo_radius_m,
            required=event.geo_required,
        )

        resolved_governance_unit, scoped_department_ids, scoped_program_ids = (
            _resolve_governance_event_write_unit_and_scope(
                db,
                current_user=current_user,
                governance_context=governance_context,
            )
        )
        school_settings = _get_school_settings(db, school_id=school_id)
        (
            default_early_check_in_minutes,
            default_late_threshold_minutes,
            default_sign_out_grace_minutes,
        ) = resolve_governance_event_default_values(
            school_settings=school_settings,
            governance_unit=resolved_governance_unit,
        )
        effective_early_check_in_minutes = (
            event.early_check_in_minutes
            if "early_check_in_minutes" in payload_fields_set
            else default_early_check_in_minutes
        )
        effective_late_threshold_minutes = (
            event.late_threshold_minutes
            if "late_threshold_minutes" in payload_fields_set
            else default_late_threshold_minutes
        )
        effective_sign_out_grace_minutes = (
            event.sign_out_grace_minutes
            if "sign_out_grace_minutes" in payload_fields_set
            else default_sign_out_grace_minutes
        )
        effective_sign_out_open_delay_minutes = int(event.sign_out_open_delay_minutes or 0)
        if effective_sign_out_open_delay_minutes > effective_sign_out_grace_minutes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "sign_out_open_delay_minutes cannot be greater than "
                    "sign_out_grace_minutes."
                ),
            )
        now_local = datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0)
        (
            present_until_override_at,
            late_until_override_at,
        ) = _resolve_near_start_attendance_override_window(
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            early_check_in_minutes=effective_early_check_in_minutes,
            late_threshold_minutes=effective_late_threshold_minutes,
            current_time=now_local,
        )

        db_event = EventModel(
            school_id=school_id,
            name=event.name,
            location=event.location,
            geo_latitude=event.geo_latitude,
            geo_longitude=event.geo_longitude,
            geo_radius_m=event.geo_radius_m,
            geo_required=event.geo_required,
            geo_max_accuracy_m=event.geo_max_accuracy_m,
            early_check_in_minutes=effective_early_check_in_minutes,
            late_threshold_minutes=effective_late_threshold_minutes,
            sign_out_grace_minutes=effective_sign_out_grace_minutes,
            sign_out_open_delay_minutes=effective_sign_out_open_delay_minutes,
            present_until_override_at=present_until_override_at,
            late_until_override_at=late_until_override_at,
            start_datetime=event.start_datetime,
            end_datetime=event.end_datetime,
            status=ModelEventStatus[event.status.value.upper()],
        )
        db.add(db_event)
        db.flush()

        target_department_ids = list(event.department_ids or [])
        target_program_ids = list(event.program_ids or [])
        if resolved_governance_unit is not None:
            target_department_ids, target_program_ids = scoped_department_ids, scoped_program_ids

        if target_department_ids:
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.school_id == school_id,
                DepartmentModel.id.in_(target_department_ids)
            ).all()
            if len(departments) != len(target_department_ids):
                missing = set(target_department_ids) - {department.id for department in departments}
                raise HTTPException(status_code=404, detail=f"Departments not found: {missing}")
            db_event.departments = departments

        if target_program_ids:
            programs = db.query(ProgramModel).options(
                joinedload(ProgramModel.departments)
            ).filter(
                ProgramModel.school_id == school_id,
                ProgramModel.id.in_(target_program_ids)
            ).all()
            if len(programs) != len(target_program_ids):
                missing = set(target_program_ids) - {program.id for program in programs}
                raise HTTPException(status_code=404, detail=f"Programs not found: {missing}")
            db_event.programs = programs

        auto_sync_result = None
        if db_event.status not in {ModelEventStatus.CANCELLED, ModelEventStatus.COMPLETED}:
            auto_sync_result = sync_event_workflow_status(db, db_event)

        if db_event.status == ModelEventStatus.COMPLETED and not (
            auto_sync_result and auto_sync_result.attendance_finalized
        ):
            finalize_completed_event_attendance(db, db_event)

        db.commit()
        db.refresh(db_event)
        return db_event

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Event creation failed (possible duplicate)")
    except Exception as exc:
        db.rollback()
        logger.error("Event creation error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.patch("/{event_id}", response_model=EventSchema)
def update_event(
    event_id: int,
    event_update: EventUpdate,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        _ensure_event_manager(db, current_user)
        school_id = _require_school_scope(current_user)

        db_event = (
            _school_scoped_event_query(db, school_id)
            .options(
                joinedload(EventModel.departments),
                joinedload(EventModel.programs),
            )
            .filter(EventModel.id == event_id)
            .first()
        )
        if not db_event:
            raise HTTPException(status_code=404, detail="Event not found")
        _ensure_event_is_writable_in_governance_scope(
            db,
            current_user=current_user,
            event=db_event,
            governance_context=governance_context,
        )

        was_completed = db_event.status == ModelEventStatus.COMPLETED

        new_start = (
            event_update.start_datetime
            if event_update.start_datetime is not None
            else db_event.start_datetime
        )
        new_end = (
            event_update.end_datetime
            if event_update.end_datetime is not None
            else db_event.end_datetime
        )
        if new_start >= new_end:
            raise HTTPException(status_code=400, detail="End datetime must be after start datetime")

        new_geo_latitude = (
            event_update.geo_latitude if event_update.geo_latitude is not None else db_event.geo_latitude
        )
        new_geo_longitude = (
            event_update.geo_longitude if event_update.geo_longitude is not None else db_event.geo_longitude
        )
        new_geo_radius = (
            event_update.geo_radius_m if event_update.geo_radius_m is not None else db_event.geo_radius_m
        )
        new_geo_required = (
            event_update.geo_required if event_update.geo_required is not None else bool(db_event.geo_required)
        )
        validate_event_geolocation_fields(
            latitude=new_geo_latitude,
            longitude=new_geo_longitude,
            radius_m=new_geo_radius,
            required=new_geo_required,
        )
        merged_early_check_in_minutes = (
            event_update.early_check_in_minutes
            if event_update.early_check_in_minutes is not None
            else int(db_event.early_check_in_minutes or 0)
        )
        merged_late_threshold_minutes = (
            event_update.late_threshold_minutes
            if event_update.late_threshold_minutes is not None
            else int(db_event.late_threshold_minutes or 0)
        )
        merged_sign_out_grace_minutes = (
            event_update.sign_out_grace_minutes
            if event_update.sign_out_grace_minutes is not None
            else int(db_event.sign_out_grace_minutes or 0)
        )
        merged_sign_out_open_delay_minutes = (
            event_update.sign_out_open_delay_minutes
            if event_update.sign_out_open_delay_minutes is not None
            else int(getattr(db_event, "sign_out_open_delay_minutes", 0) or 0)
        )
        if merged_sign_out_open_delay_minutes > merged_sign_out_grace_minutes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "sign_out_open_delay_minutes cannot be greater than "
                    "sign_out_grace_minutes."
                ),
            )
        now_local = datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0)
        (
            present_until_override_at,
            late_until_override_at,
        ) = _resolve_near_start_attendance_override_window(
            start_datetime=new_start,
            end_datetime=new_end,
            early_check_in_minutes=merged_early_check_in_minutes,
            late_threshold_minutes=merged_late_threshold_minutes,
            current_time=now_local,
        )

        if event_update.name is not None:
            db_event.name = event_update.name
        if event_update.location is not None:
            db_event.location = event_update.location
        if event_update.geo_latitude is not None:
            db_event.geo_latitude = event_update.geo_latitude
        if event_update.geo_longitude is not None:
            db_event.geo_longitude = event_update.geo_longitude
        if event_update.geo_radius_m is not None:
            db_event.geo_radius_m = event_update.geo_radius_m
        if event_update.geo_required is not None:
            db_event.geo_required = event_update.geo_required
        if event_update.geo_max_accuracy_m is not None:
            db_event.geo_max_accuracy_m = event_update.geo_max_accuracy_m
        if event_update.early_check_in_minutes is not None:
            db_event.early_check_in_minutes = event_update.early_check_in_minutes
        if event_update.late_threshold_minutes is not None:
            db_event.late_threshold_minutes = event_update.late_threshold_minutes
        if event_update.sign_out_grace_minutes is not None:
            db_event.sign_out_grace_minutes = event_update.sign_out_grace_minutes
        if event_update.sign_out_grace_minutes is None:
            db_event.sign_out_grace_minutes = merged_sign_out_grace_minutes
        if event_update.sign_out_open_delay_minutes is not None:
            db_event.sign_out_open_delay_minutes = event_update.sign_out_open_delay_minutes
        if event_update.sign_out_open_delay_minutes is None:
            db_event.sign_out_open_delay_minutes = merged_sign_out_open_delay_minutes
        db_event.start_datetime = new_start
        db_event.end_datetime = new_end
        db_event.present_until_override_at = present_until_override_at
        db_event.late_until_override_at = late_until_override_at
        if event_update.status is not None:
            db_event.status = ModelEventStatus[event_update.status.value.upper()]

        resolved_scope = _resolve_governance_event_write_scope(
            db,
            current_user=current_user,
            governance_context=governance_context,
        )
        target_department_ids = (
            list(event_update.department_ids) if event_update.department_ids is not None else None
        )
        target_program_ids = (
            list(event_update.program_ids) if event_update.program_ids is not None else None
        )
        if resolved_scope is not None:
            target_department_ids, target_program_ids = resolved_scope

        if target_department_ids is not None:
            db_event.departments = []
            db.flush()
            departments = db.query(DepartmentModel).filter(
                DepartmentModel.school_id == school_id,
                DepartmentModel.id.in_(target_department_ids)
            ).all()
            if len(departments) != len(target_department_ids):
                missing = set(target_department_ids) - {department.id for department in departments}
                raise HTTPException(status_code=404, detail=f"Departments not found: {missing}")
            db_event.departments = departments

        if target_program_ids is not None:
            db_event.programs = []
            db.flush()
            programs = db.query(ProgramModel).options(
                joinedload(ProgramModel.departments)
            ).filter(
                ProgramModel.school_id == school_id,
                ProgramModel.id.in_(target_program_ids)
            ).all()
            if len(programs) != len(target_program_ids):
                missing = set(target_program_ids) - {program.id for program in programs}
                raise HTTPException(status_code=404, detail=f"Programs not found: {missing}")
            db_event.programs = programs

        auto_sync_result = None
        if db_event.status not in {ModelEventStatus.CANCELLED, ModelEventStatus.COMPLETED}:
            auto_sync_result = sync_event_workflow_status(db, db_event)

        if db_event.status == ModelEventStatus.COMPLETED and not was_completed and not (
            auto_sync_result and auto_sync_result.attendance_finalized
        ):
            finalize_completed_event_attendance(db, db_event)

        db.commit()
        db.refresh(db_event)
        return db_event

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        logger.error("Integrity error during event update: %s", exc)
        raise HTTPException(status_code=400, detail="Update failed due to data integrity issues") from exc
    except ValueError as exc:
        db.rollback()
        logger.error("Value error during event update: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid data format: {exc}") from exc
    except Exception as exc:
        db.rollback()
        logger.error("Unexpected error during event update: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    _ensure_event_manager(db, current_user)
    school_id = _require_school_scope(current_user)

    event = (
        _school_scoped_event_query(db, school_id)
        .options(
            joinedload(EventModel.attendances),
            joinedload(EventModel.departments),
            joinedload(EventModel.programs),
        )
        .filter(EventModel.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _ensure_event_is_writable_in_governance_scope(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )

    event.departments = []
    event.programs = []
    for attendance in event.attendances:
        db.delete(attendance)

    db.delete(event)
    db.commit()
