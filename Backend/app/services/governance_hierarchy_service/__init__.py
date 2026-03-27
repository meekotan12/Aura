"""Use: Contains the public governance hierarchy service API grouped by domain.
Where to use: Use this from routers or services when governance hierarchy logic is needed.
Role: Service package. It preserves the public import path while splitting functions by domain modules.
"""

from .engagement import (
    create_governance_announcement,
    delete_governance_announcement,
    get_governance_student_note,
    list_governance_announcements,
    list_school_governance_announcements,
    upsert_governance_student_note,
    update_governance_announcement,
)
from .membership import (
    assign_governance_member,
    delete_governance_member,
    get_accessible_students,
    search_governance_student_candidates,
    update_governance_member,
)
from .permissions import (
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
from .unit_lifecycle import (
    create_governance_unit,
    delete_governance_unit,
    get_current_governance_access,
    get_governance_dashboard_overview,
    get_governance_event_defaults,
    get_governance_unit_details,
    get_or_create_campus_ssg_setup,
    list_governance_units,
    update_governance_event_defaults,
    update_governance_unit,
)

__all__ = [name for name in globals() if not name.startswith("__")]
