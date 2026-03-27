"""Student-management routes for the user router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/students/", response_model=UserWithRelations, status_code=201)
def create_student_account(
    student: StudentAccountCreate,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db),
):
    from . import EmailDeliveryError, generate_secure_password, send_welcome_email

    school_id = _actor_school_scope_id(current_user)
    if school_id is None:
        raise HTTPException(
            status_code=403,
            detail="Platform admin cannot create school-scoped students via /users/students/. Use school admin flows instead.",
        )

    _assert_email_available_for_school_or_400(db, email=student.email, school_id=school_id)
    _get_department_and_program_for_school_or_400(
        db,
        school_id=school_id,
        department_id=student.department_id,
        program_id=student.program_id,
    )

    student_role = _get_or_create_role_by_name(db, "student")

    issued_password = generate_secure_password(min_length=10, max_length=14)
    system_name = _get_school_system_name(db, school_id)

    try:
        db_user = UserModel(
            email=student.email,
            school_id=school_id,
            first_name=student.first_name,
            middle_name=student.middle_name,
            last_name=student.last_name,
            must_change_password=must_change_password_for_new_account(),
            should_prompt_password_change=should_prompt_password_change_for_new_account(),
        )
        db_user.set_password(issued_password)
        db.add(db_user)
        db.flush()

        db.add(UserRole(user_id=db_user.id, role_id=student_role.id))
        db.add(
            StudentProfile(
                user_id=db_user.id,
                school_id=school_id,
                department_id=student.department_id,
                program_id=student.program_id,
                year_level=student.year_level,
            )
        )
        db.flush()

        try:
            send_welcome_email(
                recipient_email=db_user.email,
                temporary_password=issued_password,
                first_name=db_user.first_name,
                system_name=system_name,
                password_is_temporary=True,
            )
        except EmailDeliveryError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Student account was not created because the welcome email could not be delivered. "
                    f"SMTP error: {exc}"
                ),
            ) from exc

        db.commit()
        created_user = (
            _with_user_relations(db.query(UserModel))
            .filter(UserModel.id == db_user.id)
            .first()
        )
        if created_user is None:
            raise HTTPException(status_code=500, detail="Created student account could not be reloaded")
        return _serialize_user(created_user)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create student account: {exc}")


@router.post("/admin/students/", response_model=UserWithRelations)
def create_student_profile(
    profile: StudentProfileCreate,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    target_user = _query_user_for_actor(db, profile.user_id, current_user)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    target_school_id = getattr(target_user, "school_id", None)
    if target_school_id is None:
        raise HTTPException(status_code=400, detail="Target user is not assigned to a school")

    if profile.student_id is not None and (
        db.query(StudentProfile)
        .join(UserModel, StudentProfile.user_id == UserModel.id)
        .filter(StudentProfile.student_id == profile.student_id, UserModel.school_id == target_school_id)
        .first()
    ):
        raise HTTPException(status_code=400, detail="Student ID already in use")

    _get_department_and_program_for_school_or_400(
        db,
        school_id=target_school_id,
        department_id=profile.department_id,
        program_id=profile.program_id,
    )

    try:
        student_profile = StudentProfile(
            user_id=profile.user_id,
            school_id=target_school_id,
            student_id=profile.student_id,
            department_id=profile.department_id,
            program_id=profile.program_id,
            year_level=profile.year_level or 1,
        )

        db.add(student_profile)
        db.commit()
        db.refresh(target_user)

        return _serialize_user(target_user)

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create student profile: {str(e)}"
        )


@router.patch("/student-profiles/{profile_id}", response_model=UserWithRelations)
def update_student_profile(
    profile_id: int,
    profile_update: StudentProfileBase,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db)
):
    if not _can_manage_student_profiles(db, current_user):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to manage student profiles"
        )

    profile_query = (
        db.query(StudentProfile)
        .join(UserModel, StudentProfile.user_id == UserModel.id)
        .filter(StudentProfile.id == profile_id)
    )
    actor_school_id = _actor_school_scope_id(current_user)
    if actor_school_id is not None:
        profile_query = profile_query.filter(UserModel.school_id == actor_school_id)
    profile = profile_query.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    target_user = db.query(UserModel).filter(UserModel.id == profile.user_id).first()
    target_school_id = getattr(target_user, "school_id", None)
    if target_school_id is None:
        raise HTTPException(status_code=400, detail="Target user is not assigned to a school")

    if profile_update.student_id is not None:
        if profile.student_id != profile_update.student_id:
            if (
                db.query(StudentProfile)
                .join(UserModel, StudentProfile.user_id == UserModel.id)
                .filter(
                    StudentProfile.student_id == profile_update.student_id,
                    UserModel.school_id == target_school_id,
                )
                .first()
            ):
                raise HTTPException(status_code=400, detail="Student ID already in use")
        profile.student_id = profile_update.student_id

    if profile_update.department_id is not None or profile_update.program_id is not None:
        department_id = (
            profile_update.department_id
            if profile_update.department_id is not None
            else profile.department_id
        )
        program_id = (
            profile_update.program_id
            if profile_update.program_id is not None
            else profile.program_id
        )

        _get_department_and_program_for_school_or_400(
            db,
            school_id=profile.school_id,
            department_id=department_id,
            program_id=program_id,
        )

        if profile_update.department_id is not None:
            profile.department_id = profile_update.department_id
        if profile_update.program_id is not None:
            profile.program_id = profile_update.program_id

    if profile_update.year_level is not None:
        profile.year_level = profile_update.year_level

    db.commit()
    db.refresh(profile)

    user = _query_user_for_actor(db, profile.user_id, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)


@router.delete("/student-profiles/{profile_id}", status_code=204)
def delete_student_profile(
    profile_id: int,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    profile_query = (
        db.query(StudentProfile)
        .join(UserModel, StudentProfile.user_id == UserModel.id)
        .filter(StudentProfile.id == profile_id)
    )
    actor_school_id = _actor_school_scope_id(current_user)
    if actor_school_id is not None:
        profile_query = profile_query.filter(UserModel.school_id == actor_school_id)
    profile = profile_query.first()
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    db.delete(profile)
    db.commit()

    return None
