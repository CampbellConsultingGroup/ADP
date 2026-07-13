"""Authentication models for ADP (ADP-SPEC-026)."""

from __future__ import annotations

from dataclasses import dataclass, field

from adp.authz.roles import PersonaRole


class TokenValidationError(Exception):
    """Raised when a JWT token fails any validation check."""


class TokenExpiredError(TokenValidationError):
    """Raised when a JWT token's exp claim is in the past."""


@dataclass
class AuthenticatedUser:
    """Represents the signed-in user extracted from a validated Keycloak JWT."""

    sub: str
    username: str
    email: str
    role: PersonaRole
    groups: list[str] = field(default_factory=list)

    @property
    def actor(self) -> str:
        """The identity string recorded in audit entries."""
        return self.username


# Sentinel used when ADP_AUTH_ENABLED=false (development / testing)
UNAUTHENTICATED_USER = AuthenticatedUser(
    sub="dev",
    username="architect",
    email="architect@localhost",
    role=PersonaRole.ENTERPRISE_ARCHITECT,
    groups=[],
)
