"""Read/query routes for the event router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.get("/", response_model=list[EventSchema])
def read_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[EventStatus] = None,
    start_from: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    school_id = _actor_school_scope_id(current_user)
    _persist_scope_status_sync(db, school_id)

    query = _school_scoped_event_query(db, school_id).options(
        joinedload(EventModel.departments),
        joinedload(EventModel.programs),
    )
    if status:
        query = query.filter(EventModel.status == ModelEventStatus[status.value.upper()])
    if start_from:
        query = query.filter(EventModel.start_datetime >= start_from)
    if end_at:
        query = query.filter(EventModel.end_datetime <= end_at)

    events = query.order_by(EventModel.start_datetime).all()
    events = _filter_events_for_actor(
        db,
        current_user=current_user,
        governance_context=governance_context,
        events=events,
    )
    return events[skip : skip + limit]


@router.get("/ongoing", response_model=list[EventSchema])
def get_ongoing_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    school_id = _actor_school_scope_id(current_user)
    _persist_scope_status_sync(db, school_id)
    events = (
        _school_scoped_event_query(db, school_id)
        .options(
            joinedload(EventModel.departments),
            joinedload(EventModel.programs),
        )
        .filter(EventModel.status == ModelEventStatus.ONGOING)
        .order_by(EventModel.start_datetime)
        .all()
    )
    events = _filter_events_for_actor(
        db,
        current_user=current_user,
        governance_context=governance_context,
        events=events,
    )
    return events[skip : skip + limit]


@router.get("/{event_id}", response_model=EventWithRelations)
def read_event(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    school_id = _actor_school_scope_id(current_user)
    event = (
        _school_scoped_event_query(db, school_id)
        .options(
            joinedload(EventModel.programs).joinedload(ProgramModel.departments),
            joinedload(EventModel.departments),
        )
        .filter(EventModel.id == event_id)
        .first()
    )

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    _ensure_event_is_visible_for_actor(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )
    _persist_event_status_sync(db, event)
    return event


@router.get("/{event_id}/time-status", response_model=EventTimeStatusInfo)
def read_event_time_status(
    event_id: int,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    event = (
        _school_scoped_event_query(db, _actor_school_scope_id(current_user))
        .filter(EventModel.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _ensure_event_is_visible_for_actor(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )
    _persist_event_status_sync(db, event)
    return build_event_time_status_info(event)


@router.post("/{event_id}/verify-location", response_model=EventLocationVerificationResponse)
def verify_event_location(
    event_id: int,
    payload: EventLocationVerificationRequest,
    governance_context: GovernanceUnitType | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    event = (
        _school_scoped_event_query(db, _actor_school_scope_id(current_user))
        .filter(EventModel.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    _ensure_event_is_visible_for_actor(
        db,
        current_user=current_user,
        event=event,
        governance_context=governance_context,
    )
    _persist_event_status_sync(db, event)
    return verify_event_geolocation(
        event,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
    )
