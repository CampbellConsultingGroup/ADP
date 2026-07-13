"""ADP authorization — role model, permission table, and enforcement functions."""

from adp.authz.permissions import (
    PERMISSION_GRANTS,
    PERMISSIONS_VERSION,
    REQUIRES_CONFIRMATION,
    PermissionDeniedError,
    is_permitted,
    require_action,
    requires_confirmation,
)
from adp.authz.roles import ActionType, PersonaRole

__all__ = [
    "PersonaRole",
    "ActionType",
    "PERMISSION_GRANTS",
    "PERMISSIONS_VERSION",
    "REQUIRES_CONFIRMATION",
    "PermissionDeniedError",
    "is_permitted",
    "require_action",
    "requires_confirmation",
]
