"""FastAPI dependency functions for authentication (ADP-SPEC-026)."""

from __future__ import annotations

from fastapi import Request

from adp.auth.models import UNAUTHENTICATED_USER, AuthenticatedUser


def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency: return the authenticated user set by AuthMiddleware.

    Falls back to UNAUTHENTICATED_USER when auth is disabled (development mode).
    """
    return getattr(request.state, "user", UNAUTHENTICATED_USER)


# NOTE: a linear ``require_role`` dependency was removed in the ADP-SPEC-004
# enforcement work. The permission model is action-based, not a role hierarchy
# (a REVIEWER may OVERRIDE_VERDICT but not WRITE_DESIGN), so authorization is
# enforced per-route via ``adp.authz.enforcement.enforce_route_permission``.
