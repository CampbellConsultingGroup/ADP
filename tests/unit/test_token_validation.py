"""Unit tests for JWT token validation (ADP-SPEC-026 T001-T006).

Uses a real RSA key pair generated at test time so no Keycloak instance is needed.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from adp.auth.models import TokenExpiredError, TokenValidationError
from adp.auth.tokens import JwksCache, _map_groups_to_role, decode_token
from adp.authz.roles import PersonaRole

# ── Test RSA key pair fixture ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate a fresh RSA-2048 key pair for token signing in tests."""
    from cryptography.hazmat.backends import default_backend
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture(scope="module")
def jwks_from_key(rsa_key_pair):
    """Build a JWKS dict from the test RSA key using python-jose."""
    _, public_key = rsa_key_pair
    from jose.backends import RSAKey
    jwk_key = RSAKey(public_key, algorithm="RS256")
    jwk_dict = jwk_key.to_dict()
    jwk_dict["kid"] = "test-key-001"
    jwk_dict["alg"] = "RS256"
    jwk_dict["use"] = "sig"
    return {"keys": [jwk_dict]}


def _make_token(
    rsa_key_pair,
    *,
    iss: str = "http://127.0.0.1:8080/realms/ADPRealm",
    exp_offset: int = 3600,
    username: str = "alice",
    groups: list[str] | None = None,
    sub: str = "user-sub-001",
    email: str = "alice@example.com",
    azp: str | None = "adp-frontend",
    aud: str | list[str] | None = "account",
):
    """Sign a JWT token using the test private key."""
    from jose import jwt

    private_key, _ = rsa_key_pair
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    payload = {
        "sub": sub,
        "iss": iss,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "preferred_username": username,
        "email": email,
        "groups": groups or [],
    }
    if azp is not None:
        payload["azp"] = azp
    if aud is not None:
        payload["aud"] = aud
    return jwt.encode(payload, pem.decode(), algorithm="RS256", headers={"kid": "test-key-001"})


async def _make_cache(jwks_from_key) -> JwksCache:
    """Return a JwksCache that serves the test JWKS without network calls."""
    cache = JwksCache("http://unused")
    cache.get_keys = AsyncMock(return_value=jwks_from_key)
    return cache


# ── T001: valid token decodes correctly ──────────────────────────────────────

@pytest.mark.asyncio
async def test_valid_token_decodes_correctly(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, username="alice", groups=["SolutionArchitect"])
    cache = await _make_cache(jwks_from_key)
    user = await decode_token(token, jwks_cache=cache)
    assert user.username == "alice"
    assert user.role == PersonaRole.SOLUTION_ARCHITECT
    assert user.sub == "user-sub-001"


# ── T002: expired token raises ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_token_raises(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, exp_offset=-1)  # expired 1 second ago
    cache = await _make_cache(jwks_from_key)
    with pytest.raises(TokenExpiredError):
        await decode_token(token, jwks_cache=cache)


# ── T003: wrong issuer raises ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wrong_issuer_raises(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, iss="https://evil.example.com/realms/evil")
    cache = await _make_cache(jwks_from_key)
    with pytest.raises(TokenValidationError):
        await decode_token(token, jwks_cache=cache)


# ── T004: no group defaults to technical_architect ───────────────────────────

@pytest.mark.asyncio
async def test_no_group_defaults_to_reviewer(rsa_key_pair, jwks_from_key):
    """ADP-blp.1: no recognised group means least privilege, not an architect."""
    token = _make_token(rsa_key_pair, groups=[])
    cache = await _make_cache(jwks_from_key)
    user = await decode_token(token, jwks_cache=cache)
    assert user.role == PersonaRole.REVIEWER


# ── T005: ADPAdministrator maps to platform_admin (ADP-SPEC-042) ────────────
# Was enterprise_architect prior to ADP-SPEC-042; remapped per Clarification
# Session 2026-07-24 Q1 -- no architect role, including Enterprise Architect,
# gains admin-screen access solely by virtue of that role.

@pytest.mark.asyncio
async def test_admin_group_maps_to_platform_admin(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, groups=["ADPAdministrator"])
    cache = await _make_cache(jwks_from_key)
    user = await decode_token(token, jwks_cache=cache)
    assert user.role == PersonaRole.PLATFORM_ADMIN


# ── T006: highest privilege wins ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_highest_privilege_wins(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, groups=["TechnicalArchitect", "SolutionArchitect"])
    cache = await _make_cache(jwks_from_key)
    user = await decode_token(token, jwks_cache=cache)
    assert user.role == PersonaRole.SOLUTION_ARCHITECT


@pytest.mark.asyncio
async def test_platform_admin_outranks_enterprise_architect(rsa_key_pair, jwks_from_key):
    """PLATFORM_ADMIN holds every action ENTERPRISE_ARCHITECT does, plus one more --
    it must win when a token carries both groups (ADP-SPEC-042)."""
    token = _make_token(rsa_key_pair, groups=["EnterpriseArchitect", "ADPAdministrator"])
    cache = await _make_cache(jwks_from_key)
    user = await decode_token(token, jwks_cache=cache)
    assert user.role == PersonaRole.PLATFORM_ADMIN


# ── Additional: _map_groups_to_role unit tests ────────────────────────────────

def test_map_groups_empty():
    assert _map_groups_to_role([]) == PersonaRole.REVIEWER


def test_map_groups_enterprise():
    assert _map_groups_to_role(["EnterpriseArchitect"]) == PersonaRole.ENTERPRISE_ARCHITECT


def test_map_groups_path_format():
    """Keycloak sometimes returns /GroupName — strip the leading slash."""
    assert _map_groups_to_role(["/SolutionArchitect"]) == PersonaRole.SOLUTION_ARCHITECT


def test_map_groups_unknown_group():
    assert _map_groups_to_role(["UnknownGroup", "AnotherGroup"]) == PersonaRole.REVIEWER


# ── ADP-blp.1 / ADP-blp.2: least-privilege default and client binding ─────────

def test_map_groups_reviewer():
    assert _map_groups_to_role(["/Reviewer"]) == PersonaRole.REVIEWER
    # A real role still outranks Reviewer.
    assert _map_groups_to_role(["Reviewer", "SolutionArchitect"]) == PersonaRole.SOLUTION_ARCHITECT


async def test_token_for_another_client_rejected(rsa_key_pair, jwks_from_key):
    """Validly signed by the realm, but issued to a different client."""
    token = _make_token(rsa_key_pair, azp="some-other-client", aud="account")
    with pytest.raises(TokenValidationError, match="not issued for client"):
        await decode_token(token, jwks_cache=await _make_cache(jwks_from_key))


async def test_token_without_azp_or_aud_rejected(rsa_key_pair, jwks_from_key):
    token = _make_token(rsa_key_pair, azp=None, aud=None)
    with pytest.raises(TokenValidationError, match="not issued for client"):
        await decode_token(token, jwks_cache=await _make_cache(jwks_from_key))


@pytest.mark.parametrize("aud", ["adp-frontend", ["account", "adp-frontend"]])
async def test_token_accepted_by_audience(rsa_key_pair, jwks_from_key, aud):
    token = _make_token(rsa_key_pair, azp=None, aud=aud, groups=["TechnicalArchitect"])
    user = await decode_token(token, jwks_cache=await _make_cache(jwks_from_key))
    assert user.role == PersonaRole.TECHNICAL_ARCHITECT


# ── ADP-blp.3: auth only turns off on an explicit "off" value ─────────────────

@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "True ", "enabled", "", "flase"])
def test_auth_stays_on(monkeypatch, value):
    from adp.auth.middleware import _auth_enabled

    monkeypatch.setenv("ADP_AUTH_ENABLED", value)
    assert _auth_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", " false ", "0", "no", "off"])
def test_auth_off_only_when_explicit(monkeypatch, value):
    from adp.auth.middleware import _auth_enabled

    monkeypatch.setenv("ADP_AUTH_ENABLED", value)
    assert _auth_enabled() is False


def test_auth_on_when_unset(monkeypatch):
    from adp.auth.middleware import _auth_enabled

    monkeypatch.delenv("ADP_AUTH_ENABLED", raising=False)
    assert _auth_enabled() is True
