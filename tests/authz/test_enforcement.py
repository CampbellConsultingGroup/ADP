"""Tests for request-time authorization enforcement (ADP-SPEC-004 v1.1.0).

Covers the app-level ``enforce_route_permission`` dependency and the
completeness of the route→action map. Uses FastAPI TestClient — no DB required,
because a 403 short-circuits before the endpoint (and its store dependency) runs.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, _IncludedRouter
from fastapi.testclient import TestClient

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.enforcement import SAFE_METHODS, required_action_for
from adp.authz.roles import PersonaRole


@pytest.fixture(autouse=True)
def _auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the JWT middleware; role is controlled via dependency override."""
    monkeypatch.setenv("ADP_AUTH_ENABLED", "false")


@pytest.fixture()
def app() -> FastAPI:
    from adp.api.app import create_app
    return create_app()


def _user(role: PersonaRole) -> AuthenticatedUser:
    return AuthenticatedUser(
        sub="t", username="t", email="t@localhost", role=role, groups=[]
    )


def _client_as(app: FastAPI, role: PersonaRole) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: _user(role)
    return TestClient(app, raise_server_exceptions=False)


def _iter_api_routes(app: FastAPI):
    """Yield every APIRoute in the app, descending through lazy _IncludedRouter."""
    stack: list = list(app.routes)
    while stack:
        route = stack.pop()
        if isinstance(route, APIRoute):
            yield route
        elif isinstance(route, _IncludedRouter):
            stack.extend(route.original_router.routes)


# ── Completeness: no mutating route is left without a mapped action ───────────

def test_every_mutating_route_maps_to_an_action(app: FastAPI) -> None:
    """Guards against a new mutating route shipping without an authz mapping."""
    unmapped: list[tuple[str, str]] = []
    for route in _iter_api_routes(app):
        for method in route.methods:
            if method in SAFE_METHODS:
                continue
            if required_action_for(method, route.path) is None:
                unmapped.append((method, route.path))
    assert not unmapped, f"Mutating routes with no ActionType mapped: {sorted(unmapped)}"


# ── Enforcement behavior ─────────────────────────────────────────────────────

def test_reviewer_denied_write_design(app: FastAPI) -> None:
    """A REVIEWER cannot create a design (WRITE_DESIGN)."""
    resp = _client_as(app, PersonaRole.REVIEWER).post("/api/v1/designs", json={})
    assert resp.status_code == 403


def test_reviewer_denied_business_write(app: FastAPI) -> None:
    """A REVIEWER cannot mutate business architecture (WRITE_BUSINESS_ARCH)."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities", json={}
    )
    assert resp.status_code == 403


def test_solution_architect_denied_config(app: FastAPI) -> None:
    """MANAGE_CONFIG is enterprise-only: a solution architect is denied."""
    resp = _client_as(app, PersonaRole.SOLUTION_ARCHITECT).put(
        "/api/v1/config/llm", json={}
    )
    assert resp.status_code == 403


def test_architect_not_forbidden_on_write(app: FastAPI) -> None:
    """A permitted role passes the authz gate (any non-403 status is fine here)."""
    resp = _client_as(app, PersonaRole.SOLUTION_ARCHITECT).post(
        "/api/v1/business/capabilities", json={}
    )
    assert resp.status_code != 403


def test_reviewer_reads_are_open(app: FastAPI) -> None:
    """Safe methods are never gated — a reviewer is not 403'd on a GET."""
    resp = _client_as(app, PersonaRole.REVIEWER).get("/api/v1/knowledge")
    assert resp.status_code != 403
