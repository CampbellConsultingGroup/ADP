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
        # /auth/{path} (ADP-cm9) is a transparent reverse proxy to Keycloak,
        # not an ADP business action -- Keycloak enforces its own security for
        # these paths, and AuthMiddleware only ever gates /api/v1/. Out of
        # scope for this action-based model by design, same as /health.
        if route.path.startswith("/auth/"):
            continue
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


# ── APM US3: sensitive risk & compliance reads ARE gated (the exception) ──────

def test_reviewer_denied_risk_read(app: FastAPI) -> None:
    """Risk fields are sensitive: a reviewer (no READ_APPLICATION_RISK) is 403'd."""
    resp = _client_as(app, PersonaRole.REVIEWER).get("/api/v1/applications/X/risk")
    assert resp.status_code == 403


def test_reviewer_denied_out_of_support(app: FastAPI) -> None:
    resp = _client_as(app, PersonaRole.REVIEWER).get(
        "/api/v1/applications/risk/out-of-support"
    )
    assert resp.status_code == 403


def test_reviewer_denied_risk_write(app: FastAPI) -> None:
    """WRITE_APPLICATION_RISK overrides the /applications prefix (WRITE_APPLICATION)."""
    resp = _client_as(app, PersonaRole.REVIEWER).put("/api/v1/applications/X/risk", json={})
    assert resp.status_code == 403


def test_risk_write_route_maps_to_sensitive_action() -> None:
    from adp.authz.roles import ActionType
    assert (
        required_action_for("PUT", "/api/v1/applications/{app_id}/risk")
        == ActionType.WRITE_APPLICATION_RISK
    )


def test_risk_action_grant_matrix() -> None:
    from adp.authz.permissions import is_permitted
    from adp.authz.roles import ActionType
    assert is_permitted(PersonaRole.SOLUTION_ARCHITECT, ActionType.READ_APPLICATION_RISK)
    assert is_permitted(PersonaRole.TECHNICAL_ARCHITECT, ActionType.WRITE_APPLICATION_RISK)
    assert is_permitted(PersonaRole.ENTERPRISE_ARCHITECT, ActionType.READ_APPLICATION_RISK)
    assert not is_permitted(PersonaRole.REVIEWER, ActionType.READ_APPLICATION_RISK)
    assert not is_permitted(PersonaRole.REVIEWER, ActionType.WRITE_APPLICATION_RISK)


async def test_risk_read_gate_allows_permitted_role() -> None:
    """A permitted role passes the read-gate dependency without raising."""
    from adp.authz.enforcement import require_action_dep
    from adp.authz.roles import ActionType
    dep = require_action_dep(ActionType.READ_APPLICATION_RISK)
    await dep(user=_user(PersonaRole.SOLUTION_ARCHITECT))  # must not raise


# ── APM US4: sensitive cost (TCO) reads ARE gated ──────────────────────────────

def test_reviewer_denied_cost_read(app: FastAPI) -> None:
    resp = _client_as(app, PersonaRole.REVIEWER).get("/api/v1/applications/X/cost")
    assert resp.status_code == 403


def test_reviewer_denied_cost_rollup(app: FastAPI) -> None:
    resp = _client_as(app, PersonaRole.REVIEWER).get("/api/v1/applications/cost/rollup")
    assert resp.status_code == 403


def test_reviewer_denied_cost_write(app: FastAPI) -> None:
    """WRITE_APPLICATION_COST overrides the /applications prefix (WRITE_APPLICATION)."""
    resp = _client_as(app, PersonaRole.REVIEWER).put("/api/v1/applications/X/cost", json={})
    assert resp.status_code == 403


def test_cost_write_route_maps_to_sensitive_action() -> None:
    from adp.authz.roles import ActionType
    assert (
        required_action_for("PUT", "/api/v1/applications/{app_id}/cost")
        == ActionType.WRITE_APPLICATION_COST
    )


# ── APM US7: sensitive governance/contract reads ARE gated ────────────────────

def test_reviewer_denied_governance_read(app: FastAPI) -> None:
    resp = _client_as(app, PersonaRole.REVIEWER).get("/api/v1/applications/X/governance")
    assert resp.status_code == 403


def test_reviewer_denied_renewals_soon(app: FastAPI) -> None:
    resp = _client_as(app, PersonaRole.REVIEWER).get(
        "/api/v1/applications/governance/renewals-soon"
    )
    assert resp.status_code == 403


def test_reviewer_denied_governance_write(app: FastAPI) -> None:
    """WRITE_APPLICATION_GOVERNANCE overrides the /applications prefix (WRITE_APPLICATION)."""
    resp = _client_as(app, PersonaRole.REVIEWER).put(
        "/api/v1/applications/X/governance", json={}
    )
    assert resp.status_code == 403


def test_governance_write_route_maps_to_sensitive_action() -> None:
    from adp.authz.roles import ActionType
    assert (
        required_action_for("PUT", "/api/v1/applications/{app_id}/governance")
        == ActionType.WRITE_APPLICATION_GOVERNANCE
    )


# ── ADP-SPEC-039: Agent Review trigger/confirm are gated ──────────────────────

def test_reviewer_denied_agent_review_trigger(app: FastAPI) -> None:
    """Reviewer lacks SUBMIT_AI_OPERATION."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities/X/agent-review"
    )
    assert resp.status_code == 403


def test_reviewer_denied_agent_review_accept(app: FastAPI) -> None:
    """Reviewer lacks CONFIRM_AGENT_SUGGESTION."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities/X/agent-review/OP-1/suggestions/SUG-1/accept",
        json={"confirmation_id": "CONFIRM-SUG-1"},
    )
    assert resp.status_code == 403


def test_reviewer_denied_agent_review_reject(app: FastAPI) -> None:
    """Reviewer lacks CONFIRM_AGENT_SUGGESTION."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities/X/agent-review/OP-1/suggestions/SUG-1/reject"
    )
    assert resp.status_code == 403


def test_reviewer_denied_portfolio_agent_review_trigger(app: FastAPI) -> None:
    """Reviewer lacks SUBMIT_AI_OPERATION (ADP-SPEC-040)."""
    resp = _client_as(app, PersonaRole.REVIEWER).post("/api/v1/business/capabilities/agent-review")
    assert resp.status_code == 403


def test_reviewer_denied_portfolio_agent_review_accept(app: FastAPI) -> None:
    """Reviewer lacks CONFIRM_AGENT_SUGGESTION (ADP-SPEC-040)."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities/agent-review/OP-1/suggestions/SUG-1/accept",
        json={"confirmation_id": "CONFIRM-SUG-1"},
    )
    assert resp.status_code == 403


def test_reviewer_denied_portfolio_agent_review_reject(app: FastAPI) -> None:
    """Reviewer lacks CONFIRM_AGENT_SUGGESTION (ADP-SPEC-040)."""
    resp = _client_as(app, PersonaRole.REVIEWER).post(
        "/api/v1/business/capabilities/agent-review/OP-1/suggestions/SUG-1/reject"
    )
    assert resp.status_code == 403


def test_agent_review_routes_map_to_expected_actions() -> None:
    from adp.authz.roles import ActionType

    assert (
        required_action_for("POST", "/api/v1/business/capabilities/{cap_id}/agent-review")
        == ActionType.SUBMIT_AI_OPERATION
    )
    assert (
        required_action_for(
            "POST",
            "/api/v1/business/capabilities/{cap_id}/agent-review/{operation_id}"
            "/suggestions/{suggestion_id}/accept",
        )
        == ActionType.CONFIRM_AGENT_SUGGESTION
    )
    assert (
        required_action_for(
            "POST",
            "/api/v1/business/capabilities/{cap_id}/agent-review/{operation_id}"
            "/suggestions/{suggestion_id}/reject",
        )
        == ActionType.CONFIRM_AGENT_SUGGESTION
    )


def test_portfolio_agent_review_routes_map_to_expected_actions() -> None:
    """ADP-SPEC-040: distinct route shape (no {cap_id} segment), same actions."""
    from adp.authz.roles import ActionType

    assert (
        required_action_for("POST", "/api/v1/business/capabilities/agent-review")
        == ActionType.SUBMIT_AI_OPERATION
    )
    assert (
        required_action_for(
            "POST",
            "/api/v1/business/capabilities/agent-review/{operation_id}"
            "/suggestions/{suggestion_id}/accept",
        )
        == ActionType.CONFIRM_AGENT_SUGGESTION
    )
    assert (
        required_action_for(
            "POST",
            "/api/v1/business/capabilities/agent-review/{operation_id}"
            "/suggestions/{suggestion_id}/reject",
        )
        == ActionType.CONFIRM_AGENT_SUGGESTION
    )
