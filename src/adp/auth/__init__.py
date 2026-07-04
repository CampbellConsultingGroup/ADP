"""ADP authentication module — Keycloak OIDC integration (ADP-SPEC-026)."""

from adp.auth.deps import get_current_user, require_role
from adp.auth.middleware import AuthMiddleware
from adp.auth.models import UNAUTHENTICATED_USER, AuthenticatedUser

__all__ = [
    "AuthMiddleware",
    "get_current_user",
    "require_role",
    "AuthenticatedUser",
    "UNAUTHENTICATED_USER",
]
