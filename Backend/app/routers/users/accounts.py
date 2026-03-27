"""Account-management routes for the user router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/", response_model=UserCreateResponse)
def create_user(
    user: UserCreate,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    from . import EmailDeliveryError, generate_secure_password, send_welcome_email

    school_id = _actor_school_scope_id(current_user)
    if school_id is None:
        raise HTTPException(
            status_code=403,
            detail="Platform admin cannot create school-scoped users via /users. Use school admin flows instead.",
        )

    _assert_email_available_for_school_or_400(db, email=user.email, school_id=school_id)

    role_names = [canonicalize_role_name_for_storage(role.value) for role in user.roles]
    _assert_school_it_assignable_roles(current_user, role_names)

    role_map = {
        role_name: _get_role_by_name_or_alias(db, role_name)
        for role_name in role_names
    }
    missing_roles = [role_name for role_name, role in role_map.items() if role is None]

    if missing_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Role(s) not found: {', '.join(missing_roles)}"
        )

    try:
        generated_temporary_password = None
        issued_password = user.password
        if not issued_password:
            generated_temporary_password = generate_secure_password(min_length=10, max_length=14)
            issued_password = generated_temporary_password

        db_user = UserModel(
            email=user.email,
            school_id=school_id,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            must_change_password=must_change_password_for_new_account(),
            should_prompt_password_change=should_prompt_password_change_for_new_account(),
        )
        db_user.set_password(issued_password)
        db.add(db_user)
        db.flush()

        for role_name in role_names:
            db.add(UserRole(user_id=db_user.id, role_id=role_map[role_name].id))

        db.commit()
        db.refresh(db_user)
        db_user = _with_user_relations(db.query(UserModel)).filter(UserModel.id == db_user.id).first()

        system_name = _get_school_system_name(db, school_id)

        try:
            send_welcome_email(
                recipient_email=db_user.email,
                temporary_password=issued_password,
                first_name=db_user.first_name,
                system_name=system_name,
                password_is_temporary=generated_temporary_password is not None,
            )
        except EmailDeliveryError as exc:
            logger.warning(
                "Welcome email delivery failed for user_id=%s email=%s error=%s",
                db_user.id,
                db_user.email,
                str(exc),
            )

        return UserCreateResponse.model_validate(
            db_user,
            from_attributes=True,
        ).model_copy(
            update={"generated_temporary_password": generated_temporary_password},
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}")


@router.get("/", response_model=List[UserWithRelations])
def get_all_users(
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    safe_skip = max(skip, 0)
    safe_limit = max(1, min(limit, 500))

    query = _with_user_relations(db.query(UserModel))
    query = _apply_user_scope(query, current_user)
    users = query.order_by(UserModel.id.asc()).offset(safe_skip).limit(safe_limit).all()
    return _serialize_users(users)


@router.get("/by-role/{role_name}", response_model=List[UserWithRelations])
def get_users_by_role(
    role_name: str,
    skip: int = 0,
    limit: int = 100,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    safe_skip = max(skip, 0)
    safe_limit = max(1, min(limit, 500))

    query = (
        _with_user_relations(db.query(UserModel))
        .join(UserRole)
        .join(Role)
        .filter(Role.name.in_(get_role_lookup_names(role_name)))
    )
    query = _apply_user_scope(query, current_user)
    users = query.order_by(UserModel.id.asc()).offset(safe_skip).limit(safe_limit).all()

    return _serialize_users(users)


@router.get("/me/", response_model=UserWithRelations)
def get_current_user_profile(
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db)
):
    db.refresh(current_user)
    return _serialize_user(current_user)


@router.patch("/{user_id}", response_model=UserWithRelations)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db)
):
    if current_user.id != user_id and not has_required_roles(current_user, ["admin", "campus_admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to update this user"
        )

    db_user = _query_user_for_actor(db, user_id, current_user)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if _is_school_it(current_user) and not _is_admin(current_user):
        if current_user.id != db_user.id and _target_has_admin_or_school_it(db_user):
            raise HTTPException(
                status_code=403,
                detail="Campus Admin cannot modify admin or Campus Admin accounts.",
            )

    if user_update.email is not None:
        if db_user.email != user_update.email:
            existing_email_user = (
                db.query(UserModel)
                .filter(UserModel.email == user_update.email, UserModel.id != db_user.id)
                .first()
            )
            if existing_email_user:
                detail = "Email already registered in this school"
                actor_school_id = _actor_school_scope_id(current_user)
                if actor_school_id is None:
                    detail = "Email already registered"
                elif existing_email_user.school_id != actor_school_id:
                    detail = "Email already registered in another school"
                raise HTTPException(status_code=400, detail=detail)
        db_user.email = user_update.email

    if user_update.first_name is not None:
        db_user.first_name = user_update.first_name

    if user_update.middle_name is not None:
        db_user.middle_name = user_update.middle_name

    if user_update.last_name is not None:
        db_user.last_name = user_update.last_name

    db.commit()
    db.refresh(db_user)

    return _serialize_user(db_user)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    db_user = _query_user_for_actor(db, user_id, current_user)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if _is_school_it(current_user) and not _is_admin(current_user):
        if current_user.id == db_user.id:
            raise HTTPException(status_code=403, detail="Campus Admin cannot delete their own account.")
        if _target_has_admin_or_school_it(db_user):
            raise HTTPException(
                status_code=403,
                detail="Campus Admin cannot delete admin or Campus Admin accounts.",
            )

    db.delete(db_user)
    db.commit()

    return None


@router.get("/{user_id}", response_model=UserWithRelations)
def get_user_by_id(
    user_id: int,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db)
):
    if current_user.id != user_id and not has_required_roles(
        current_user, ["admin", "campus_admin"]
    ):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view this user"
        )

    user = _query_user_for_actor(db, user_id, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _serialize_user(user)
