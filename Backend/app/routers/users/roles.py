"""Role-management routes for the user router package."""

from .shared import *  # noqa: F403

router = APIRouter()


@router.put("/{user_id}/roles", response_model=UserWithRelations)
def update_user_roles(
    user_id: int,
    role_update: UserRoleUpdate,
    current_user: UserModel = Depends(get_current_admin_or_campus_admin),
    db: Session = Depends(get_db)
):
    user = _query_user_for_actor(db, user_id, current_user)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    requested_role_values = [canonicalize_role_name_for_storage(role_name.value) for role_name in role_update.roles]
    if _is_school_it(current_user) and not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Campus Admin cannot change user roles from Manage Users. "
                "Imported users stay students, and SSG access is managed from Manage SSG."
            ),
        )
    _assert_school_it_assignable_roles(current_user, requested_role_values)
    if _is_school_it(current_user) and not _is_admin(current_user) and _target_has_admin_or_school_it(user):
        raise HTTPException(
            status_code=403,
            detail="Campus Admin cannot update roles for admin or Campus Admin accounts.",
        )

    db.query(UserRole).filter(UserRole.user_id == user_id).delete()

    for role_name in requested_role_values:
        role = _get_role_by_name_or_alias(db, role_name)
        if not role:
            raise HTTPException(
                status_code=400,
                detail=f"Role '{role_name}' does not exist in database"
            )
        db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)

    return _serialize_user(user)
