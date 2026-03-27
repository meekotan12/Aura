"""Permission-oriented governance service exports."""

from .shared import (
    assign_unit_permission,
    ensure_governance_permission,
    ensure_permission_catalog,
    get_governance_units_with_permission,
    get_user_governance_permission_codes,
    get_user_governance_unit_types,
    governance_unit_matches_event_scope,
    governance_units_match_student_scope,
    user_has_governance_permission,
)

__all__ = [name for name in globals() if not name.startswith("__")]
