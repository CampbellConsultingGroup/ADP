"""FastAPI dependency functions for authentication (ADP-SPEC-026)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from adp.auth.models import UNAUTHENTICATED_USER, AuthenticatedUser
from adp.authz.roles import PersonaRole


def get_current_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency: return the authenticated user set by AuthMiddleware.

    Falls back to UNAUTHENTICATED_USER when auth is disabled (development mode).
    """
    return getattr(request.state, "user", UNAUTHENTICATED_USER)


def require_role(minimum_role: PersonaRole):
    """Return a FastAPI dependency that enforces a minimum PersonaRole.

    Usage:
        dependencies=[Depends(require_role(PersonaRole.SOLUTION_ARCHITECT))]
    """
    _PRIVILEGE_ORDER = [
        PersonaRole.ENTERPRISE_ARCHITECT,
        PersonaRole.SOLUTION_ARCHITECT,
        PersonaRole.TECHNICAL_ARCHITECT,
        PersonaRole.REVIEWER,
    ]

    def _check(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        user_idx = (
            _PRIVILEGE_ORDER.index(user.role)
            if user.role in _PRIVILEGE_ORDER
            else len(_PRIVILEGE_ORDER)
        )
        req_idx = (
            _PRIVILEGE_ORDER.index(minimum_role)
            if minimum_role in _PRIVILEGE_ORDER
            else len(_PRIVILEGE_ORDER)
        )

        if user_idx > req_idx:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient privileges. Required: {minimum_role.value}, "
                    f"your role: {user.role.value}"
                ),
            )
        return user

    return Depends(_check)
