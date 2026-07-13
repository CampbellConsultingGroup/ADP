"""Contract tests for AuthMiddleware (ADP-SPEC-026 T012-T015).

Tests use ADP_AUTH_ENABLED=true with a mocked decode_token to avoid needing a live Keycloak.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from adp.auth.models import AuthenticatedUser, TokenExpiredError, TokenValidationError
from adp.authz.roles import PersonaRole


def _make_user(**kwargs) -> AuthenticatedUser:
    defaults = dict(
        sub="sub-001",
        username="testuser",
        email="test@example.com",
        role=PersonaRole.ENTERPRISE_ARCHITECT,
        groups=["EnterpriseArchitect"],
    )
    defaults.update(kwargs)
    return AuthenticatedUser(**defaults)


@pytest.fixture()
def auth_client(monkeypatch):
    """TestClient with ADP_AUTH_ENABLED=true and mocked design store."""
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module

    monkeypatch.setenv("ADP_AUTH_ENABLED", "true")
    monkeypatch.setenv("ADP_KEYCLOAK_ISSUER", "http://127.0.0.1:8080/realms/ADPRealm")

    app = create_app()

    # Mock design store to avoid DB
    from unittest.mock import AsyncMock
    mock_store = AsyncMock()
    mock_store.list_all = AsyncMock(return_value=[])
    mock_store.count_all = AsyncMock(return_value=0)

    async def _fake_store():
        return mock_store

    app.dependency_overrides[designs_module._get_design_store] = _fake_store

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def noauth_client(monkeypatch):
    """TestClient with ADP_AUTH_ENABLED=false."""
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module

    monkeypatch.setenv("ADP_AUTH_ENABLED", "false")

    app = create_app()

    from unittest.mock import AsyncMock
    mock_store = AsyncMock()
    mock_store.list_all = AsyncMock(return_value=[])
    mock_store.count_all = AsyncMock(return_value=0)

    async def _fake_store():
        return mock_store

    app.dependency_overrides[designs_module._get_design_store] = _fake_store

    return TestClient(app, raise_server_exceptions=False)


# ── T012: no token returns 401 ────────────────────────────────────────────────

def test_request_without_token_returns_401(auth_client):
    resp = auth_client.get("/api/v1/designs")
    assert resp.status_code == 401
    assert "authentication" in resp.json()["detail"].lower()


# ── T013: valid token returns 200 ─────────────────────────────────────────────

def test_request_with_valid_token_returns_200(auth_client):
    user = _make_user()
    with patch("adp.auth.middleware.decode_token", new_callable=AsyncMock, return_value=user):
        resp = auth_client.get("/api/v1/designs", headers={"Authorization": "Bearer valid.token.here"})  # noqa: E501
    assert resp.status_code == 200


# ── T014: auth disabled no token succeeds ─────────────────────────────────────

def test_auth_disabled_no_token_succeeds(noauth_client):
    resp = noauth_client.get("/api/v1/designs")
    assert resp.status_code == 200


# ── T015: expired token returns 401 ──────────────────────────────────────────

def test_expired_token_returns_401(auth_client):
    with patch("adp.auth.middleware.decode_token", new_callable=AsyncMock,
               side_effect=TokenExpiredError("expired")):
        resp = auth_client.get("/api/v1/designs", headers={"Authorization": "Bearer expired.token"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


# ── Additional: health endpoint exempt ────────────────────────────────────────

def test_health_endpoint_exempt_from_auth(auth_client):
    resp = auth_client.get("/health")
    assert resp.status_code == 200  # health is exempt regardless of auth


def test_invalid_token_returns_401(auth_client):
    with patch("adp.auth.middleware.decode_token", new_callable=AsyncMock,
               side_effect=TokenValidationError("bad signature")):
        resp = auth_client.get("/api/v1/designs", headers={"Authorization": "Bearer bad.token"})
    assert resp.status_code == 401
