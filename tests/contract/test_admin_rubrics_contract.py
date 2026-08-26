"""Contract tests for the Admin Scoring Rubric Management API (ADP-68z).

Full-stack against the real service on in-memory SQLite. Mirrors
test_admin_prompts_contract.py's exact fixture shape -- role is controlled via a
get_current_user dependency override, since ADP_AUTH_ENABLED=false's default caller
(ENTERPRISE_ARCHITECT) deliberately does NOT hold MANAGE_SCORING_RUBRICS.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.admin import rubric_registry, rubric_service
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole

_VALID_WEIGHTS = {
    "strategic_alignment": 0.30, "revenue_cost_impact": 0.20,
    "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10,
    "risk_compliance_contribution": 0.15, "evidence_measurability": 0.10,
}


def _user(role: PersonaRole) -> AuthenticatedUser:
    return AuthenticatedUser(sub="t", username="t", email="t@localhost", role=role, groups=[])


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/rubrics.db")
    async with engine.begin() as conn:
        await conn.run_sync(rubric_service._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # rubric_registry's own read-path factory (used directly by list_rubrics(),
    # not via a router-level override) -- point it at the SAME SQLite DB and pin
    # the loop, mirroring tests/unit/admin/test_rubric_registry.py.
    monkeypatch.setattr(rubric_registry, "_session_factory", factory)
    monkeypatch.setattr(rubric_registry, "_engine_loop", asyncio.get_running_loop())

    from adp.api.app import create_app
    from adp.api.routers import admin_rubrics_router as admin_router

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[admin_router._get_session] = _override
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.PLATFORM_ADMIN)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await engine.dispose()


async def test_list_returns_business_value_with_defaults(client) -> None:
    c, _app = client
    resp = await c.get("/api/v1/admin/scoring-rubrics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"]
    assert len(items) == 1
    item = items[0]
    assert item["rubric_id"] == "business_value"
    assert item["is_override"] is False
    assert item["version"] == 0
    assert item["active_weights"] == {
        "strategic_alignment": 0.25, "revenue_cost_impact": 0.25,
        "customer_stakeholder_impact": 0.15, "competitive_differentiation": 0.10,
        "risk_compliance_contribution": 0.15, "evidence_measurability": 0.10,
    }
    assert item["dimension_labels"]["strategic_alignment"] == "Strategic Alignment"


async def test_list_denied_without_manage_scoring_rubrics(client) -> None:
    """A caller without MANAGE_SCORING_RUBRICS (e.g. a plain Enterprise Architect)
    gets 403 with no weight content in the body."""
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.get("/api/v1/admin/scoring-rubrics")
    assert resp.status_code == 403
    assert "items" not in resp.json()
    assert "active_weights" not in resp.text


# ── User Story 1: edit, confirm, take effect ─────────────────────────────────

async def test_confirm_rejects_invalid_weight_sum(client) -> None:
    c, _app = client
    bad_weights = dict(_VALID_WEIGHTS, strategic_alignment=0.05)  # now sums to 0.95
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": bad_weights, "expected_version": 0, "confirmation_id": "C-1"},
    )
    assert resp.status_code == 422


async def test_confirm_rejects_missing_dimension(client) -> None:
    c, _app = client
    incomplete = dict(_VALID_WEIGHTS)
    del incomplete["evidence_measurability"]
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": incomplete, "expected_version": 0, "confirmation_id": "C-1"},
    )
    assert resp.status_code == 422


async def test_confirm_rejects_missing_confirmation_id(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": ""},
    )
    assert resp.status_code == 422


async def test_confirm_unknown_rubric_404(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/not_a_real_rubric/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "C-1"},
    )
    assert resp.status_code == 404


async def test_confirm_success_persists_and_attributes(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        headers={"X-Actor": "alice"},
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rubric_id"] == "business_value"
    assert body["active_weights"] == _VALID_WEIGHTS
    assert body["version"] == 1

    listing = (await c.get("/api/v1/admin/scoring-rubrics")).json()
    item = next(i for i in listing["items"] if i["rubric_id"] == "business_value")
    assert item["is_override"] is True
    assert item["version"] == 1
    assert item["active_weights"] == _VALID_WEIGHTS

    history = (
        await c.get("/api/v1/admin/scoring-rubrics/business_value/history")
    ).json()
    assert len(history["items"]) == 1
    entry = history["items"][0]
    assert entry["change_type"] == "edit"
    assert entry["new_weights"] == _VALID_WEIGHTS
    assert entry["actor"] == "alice"


async def test_confirm_version_conflict_returns_current_state(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "CONFIRM-A"},
    )
    other_weights = dict(_VALID_WEIGHTS, strategic_alignment=0.40, revenue_cost_impact=0.10)
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={
            "weights": other_weights, "expected_version": 0, "confirmation_id": "CONFIRM-B",
        },
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["current_active_weights"] == _VALID_WEIGHTS
    assert detail["current_version"] == 1


async def test_confirm_denied_without_manage_scoring_rubrics(client) -> None:
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "C-1"},
    )
    assert resp.status_code == 403


# ── User Story 2: history + restore ──────────────────────────────────────────

async def test_history_ordered_newest_first(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "C-1"},
    )
    second_weights = dict(_VALID_WEIGHTS, strategic_alignment=0.35, revenue_cost_impact=0.15)
    await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": second_weights, "expected_version": 1, "confirmation_id": "C-2"},
    )
    resp = await c.get("/api/v1/admin/scoring-rubrics/business_value/history")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["new_weights"] == second_weights
    assert items[1]["new_weights"] == _VALID_WEIGHTS


async def test_restore_requires_confirmation_id(client) -> None:
    c, _app = client
    confirm = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "C-1"},
    )
    history_id = (await c.get(
        "/api/v1/admin/scoring-rubrics/business_value/history"
    )).json()["items"][0]["id"]

    resp = await c.post(
        f"/api/v1/admin/scoring-rubrics/business_value/restore/{history_id}",
        json={"expected_version": confirm.json()["version"], "confirmation_id": ""},
    )
    assert resp.status_code == 422


async def test_restore_creates_new_history_entry_not_a_rewrite(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": _VALID_WEIGHTS, "expected_version": 0, "confirmation_id": "C-1"},
    )
    bad_weights = dict(_VALID_WEIGHTS, strategic_alignment=0.35, revenue_cost_impact=0.15)
    await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/confirm",
        json={"weights": bad_weights, "expected_version": 1, "confirmation_id": "C-2"},
    )
    history_items = (await c.get(
        "/api/v1/admin/scoring-rubrics/business_value/history"
    )).json()["items"]
    original_entry_id = next(
        i["id"] for i in history_items if i["new_weights"] == _VALID_WEIGHTS
    )

    resp = await c.post(
        f"/api/v1/admin/scoring-rubrics/business_value/restore/{original_entry_id}",
        json={"expected_version": 2, "confirmation_id": "CONFIRM-restore"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_weights"] == _VALID_WEIGHTS
    assert body["version"] == 3

    updated_history = (await c.get(
        "/api/v1/admin/scoring-rubrics/business_value/history"
    )).json()["items"]
    assert len(updated_history) == 3  # two edits + one restore, none rewritten
    assert updated_history[0]["change_type"] == "restore"
    assert updated_history[0]["new_weights"] == _VALID_WEIGHTS
    assert {i["change_type"] for i in updated_history[1:]} == {"edit"}


async def test_restore_404_for_unknown_history_id(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/restore/999999",
        json={"expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 404


async def test_restore_denied_without_manage_scoring_rubrics(client) -> None:
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.post(
        "/api/v1/admin/scoring-rubrics/business_value/restore/1",
        json={"expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 403
