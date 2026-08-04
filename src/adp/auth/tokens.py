"""JWT validation and JWKS caching for Keycloak (ADP-SPEC-026).

Uses python-jose for RS256 signature verification against Keycloak's JWKS endpoint.
JWKS public keys are cached for 5 minutes to avoid hitting Keycloak on every request.
Tokens are validated locally (no introspection) — faster and works without network on each call.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

import httpx
from jose import ExpiredSignatureError, JWTError, jwt
from jose.exceptions import JWTClaimsError

from adp.auth.models import AuthenticatedUser, TokenExpiredError, TokenValidationError
from adp.authz.roles import PersonaRole

_logger = logging.getLogger("adp.auth")

# ── Group → Role precedence (highest first) ───────────────────────────────────

_GROUP_ROLE_PRIORITY: list[tuple[str, PersonaRole]] = [
    ("EnterpriseArchitect", PersonaRole.ENTERPRISE_ARCHITECT),
    # ADP-SPEC-042: was ENTERPRISE_ARCHITECT; remapped to the distinct
    # PLATFORM_ADMIN role so this group carries MANAGE_AGENT_PROMPTS
    # (Clarification Session 2026-07-24 Q1).
    ("ADPAdministrator", PersonaRole.PLATFORM_ADMIN),
    ("SolutionArchitect", PersonaRole.SOLUTION_ARCHITECT),
    ("TechnicalArchitect", PersonaRole.TECHNICAL_ARCHITECT),
]

_ROLE_PRIORITY_ORDER = [
    # PLATFORM_ADMIN holds every action ENTERPRISE_ARCHITECT does, plus one
    # more (MANAGE_AGENT_PROMPTS) -- it must outrank ENTERPRISE_ARCHITECT.
    PersonaRole.PLATFORM_ADMIN,
    PersonaRole.ENTERPRISE_ARCHITECT,
    PersonaRole.SOLUTION_ARCHITECT,
    PersonaRole.TECHNICAL_ARCHITECT,
]


def _map_groups_to_role(groups: list[str]) -> PersonaRole:
    """Return the highest-privilege role from a list of Keycloak group names.

    Unknown groups are ignored. If no recognised group is found, defaults to
    TechnicalArchitect (read-only access).
    """
    mapped: list[PersonaRole] = []
    for group in groups:
        for group_name, role in _GROUP_ROLE_PRIORITY:
            if group == group_name or group.lstrip("/") == group_name:
                mapped.append(role)
                break

    if not mapped:
        return PersonaRole.TECHNICAL_ARCHITECT

    # Return highest-privilege role
    for role in _ROLE_PRIORITY_ORDER:
        if role in mapped:
            return role
    return PersonaRole.TECHNICAL_ARCHITECT


# ── JWKS cache ────────────────────────────────────────────────────────────────

_JWKS_TTL_SECONDS = 300  # 5 minutes


class JwksCache:
    """Fetches and caches Keycloak's public JWKS keys with a TTL."""

    def __init__(self, jwks_uri: str) -> None:
        self._jwks_uri = jwks_uri
        self._keys: dict[str, Any] | None = None
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get_keys(self) -> dict[str, Any]:
        """Return cached JWKS or fetch fresh if stale."""
        async with self._lock:
            now = time.monotonic()
            if self._keys is None or (now - self._fetched_at) > _JWKS_TTL_SECONDS:
                await self._refresh()
            return self._keys  # type: ignore[return-value]

    async def _refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self._jwks_uri)
                resp.raise_for_status()
                self._keys = resp.json()
                self._fetched_at = time.monotonic()
                _logger.debug("JWKS refreshed from %s", self._jwks_uri)
        except Exception as exc:
            if self._keys is None:
                raise TokenValidationError(  # noqa: E501
                    f"Cannot fetch JWKS from {self._jwks_uri}: {exc}"
                ) from exc
            _logger.warning("JWKS refresh failed (using cached keys): %s", exc)


# ── Module-level singleton ────────────────────────────────────────────────────

_cache: JwksCache | None = None


def _jwks_uri_for(issuer: str) -> str:
    """Return the endpoint to FETCH Keycloak's signing keys from.

    Prefer the internal Keycloak URL (ADP_KEYCLOAK_INTERNAL_URL) so the API
    fetches keys over the Container Apps environment's private network, rather
    than hairpinning back through its OWN public FQDN + the /auth reverse proxy.
    That self-loop does not route inside Container Apps, so the JWKS fetch fails
    and every otherwise-valid token is rejected with 401 -- which, with no
    frontend error boundary, shows up as a black screen AFTER a successful
    login (ADP-cm9). Only the key-fetch location changes here; issuer
    VALIDATION still uses the public issuer (matching the token's `iss` claim).

    Falls back to deriving the JWKS URI from the issuer when no internal URL is
    set (local dev: Keycloak on 127.0.0.1:8080 with no /auth path prefix).
    """
    internal = os.environ.get("ADP_KEYCLOAK_INTERNAL_URL")
    if internal:
        realm = issuer.rstrip("/").rsplit("/realms/", 1)[-1]
        # Internal Keycloak serves under /auth (--http-relative-path=/auth,
        # see infra/azure/modules/keycloak.bicep), same as the /auth proxy.
        return f"{internal.rstrip('/')}/auth/realms/{realm}/protocol/openid-connect/certs"
    return f"{issuer.rstrip('/')}/protocol/openid-connect/certs"


def _get_cache() -> JwksCache:
    global _cache
    if _cache is None:
        issuer = os.environ.get("ADP_KEYCLOAK_ISSUER", "http://127.0.0.1:8080/realms/ADPRealm")
        _cache = JwksCache(_jwks_uri_for(issuer))
    return _cache


# ── Token decode ──────────────────────────────────────────────────────────────

async def decode_token(
    token: str,
    *,
    jwks_cache: JwksCache | None = None,
) -> AuthenticatedUser:
    """Validate a Keycloak JWT and return the authenticated user.

    Raises:
        TokenExpiredError: if the token's exp claim is in the past.
        TokenValidationError: for any other validation failure.
    """
    cache = jwks_cache or _get_cache()
    issuer = os.environ.get("ADP_KEYCLOAK_ISSUER", "http://127.0.0.1:8080/realms/ADPRealm")
    audience = os.environ.get("ADP_KEYCLOAK_CLIENT_ID", "adp-frontend")

    try:
        jwks = await cache.get_keys()
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"verify_aud": False},  # Keycloak may use 'account' as aud; verify iss only
        )
    except ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except JWTClaimsError as exc:
        raise TokenValidationError(f"Token claims invalid: {exc}") from exc
    except JWTError as exc:
        raise TokenValidationError(f"Token validation failed: {exc}") from exc

    # Verify issuer explicitly (belt-and-suspenders)
    token_issuer = claims.get("iss", "")
    if token_issuer != issuer:
        raise TokenValidationError(
            f"Token issuer {token_issuer!r} does not match expected {issuer!r}"
        )

    # Extract identity
    sub = claims.get("sub", "")
    username = claims.get("preferred_username", claims.get("sub", "unknown"))
    email = claims.get("email", "")

    # Extract groups from token claim (requires Group Membership mapper in Keycloak)
    raw_groups: list[str] = claims.get("groups", [])
    role = _map_groups_to_role(raw_groups)

    return AuthenticatedUser(
        sub=sub,
        username=username,
        email=email,
        role=role,
        groups=raw_groups,
    )
