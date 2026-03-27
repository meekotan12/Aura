"""Workflow/status routes for the event router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/{event_id}/sign-out/open-early", response_model=EventSchema)
@router.post("/{event_id}/sign-out-override/open", response_model=EventSchema)
def open_sign_out_early(
    event_id: int,
    payload: SignOutOpenEarlyRequest = Body(...),
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    _ensure_event_attendance_manager(db, current_user)
    school_id = _require_school_scope(current_user)

    event = (
        _school_scoped_event_query(db, school_id)
        .options(
            joinedload(EventModel.departments),
            joinedload(EventModel.programs),
        )
        .filter(EventModel.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    _ensure_event_is_attendance_writable_in_governance_scope(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )

    sync_result = sync_event_workflow_status(db, event)
    if sync_result.changed:
        db.commit()
        db.refresh(event)

    if event.status == ModelEventStatus.CANCELLED:
        raise HTTPException(status_code=409, detail="Cancelled events cannot open sign-out early.")
    if event.status == ModelEventStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Sign-out is already closed for this event.")

    now_local = datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0)
    if now_local < event.start_datetime:
        raise HTTPException(
            status_code=409,
            detail="Early sign-out can only be opened after the event has started.",
        )
    if now_local >= event.end_datetime:
        raise HTTPException(
            status_code=409,
            detail="Early sign-out can only be opened before the scheduled event end.",
        )

    selected_sign_out_grace_minutes = (
        int(event.sign_out_grace_minutes)
        if payload.use_sign_out_grace_minutes
        else int(payload.close_after_minutes or 0)
    )
    if not payload.use_sign_out_grace_minutes:
        event.sign_out_grace_minutes = selected_sign_out_grace_minutes

    event.end_datetime = now_local
    event.sign_out_override_until = None
    event.present_until_override_at = None
    event.late_until_override_at = None
    sync_event_workflow_status(db, event, current_time=now_local)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}/status", response_model=EventSchema)
def update_event_status(
    event_id: int,
    status: EventStatus,
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

        if status in {EventStatus.ongoing, EventStatus.upcoming}:
            now_local = datetime.now(get_event_timezone()).replace(tzinfo=None, microsecond=0)
            _expected_status, computed_time_status = get_expected_workflow_status(
                db_event,
                current_time=now_local,
            )
            conflict_detail = _build_status_conflict_detail(
                requested_status=status,
                computed_time_status=computed_time_status,
                event=db_event,
            )
            if conflict_detail is not None:
                raise HTTPException(status_code=409, detail=conflict_detail)

        was_completed = db_event.status == ModelEventStatus.COMPLETED
        db_event.status = ModelEventStatus[status.value.upper()]

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
    except Exception as exc:
        db.rollback()
        logger.error("Status update error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}") from exc
