"""Password-management routes for the user router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.post("/{user_id}/reset-password", status_code=204)
def reset_user_password(
    user_id: int,
    password_update: PasswordUpdate,
    current_user: UserModel = Depends(get_current_application_user),
    db: Session = Depends(get_db)
):
    if current_user.id != user_id and not has_required_roles(current_user, ["admin", "campus_admin"]):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to reset this user's password"
        )

    user = _query_user_for_actor(db, user_id, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if _is_school_it(current_user) and not _is_admin(current_user):
        if current_user.id != user.id and _target_has_admin_or_school_it(user):
            raise HTTPException(
                status_code=403,
                detail="Campus Admin cannot reset password for admin or Campus Admin accounts.",
            )

    user.set_password(password_update.password)
    user.must_change_password = must_change_password_for_temporary_reset()
    user.should_prompt_password_change = should_prompt_password_change_for_temporary_reset()
    db.commit()

    return None
