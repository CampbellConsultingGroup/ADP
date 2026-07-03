"""Contract tests for the Architecture Recommendation API (ADP-SPEC-018).

T007-T009 (US1): POST /recommend, GET /recommend/{op_id}, validation
T016-T019 (US2): POST /accept, confirmation gate, advisory gate, 409
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, Requirement
from adp.recommendation.models import (
    ProposedElement,
    RecommendationState,
    SolutionOption,
    TradeOffEntry,
    TradeOffStance,
)
from adp.models import ElementKind


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [],
        "requirements": [
            {"id": "REQ-001", "title": "Scalability", "description": "Handle 10k users"},
        ],
        "relationships": [],
    })


def _make_pending_option(option_id: str = "OPT-001", advisory: bool = False) -> SolutionOption:
    opt = SolutionOption(
        option_id=option_id,
        operation_id="OP-TEST-001",
        rank=1,
        title="Microservices with API Gateway",
        rationale="Addresses scalability via horizontal scaling.",
        advisory=advisory,
        satisfies=["REQ-001"],
        trade_offs=[TradeOffEntry(criterion="Scalability", stance=TradeOffStance.MEETS, rationale="...")],
        proposed_elements=[
            ProposedElement(name="API Gateway", kind=ElementKind.CONTAINER, satisfies=["REQ-001"])
        ],
        ranking_score=0.85,
    )
    opt.status = "pending"
    return opt


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import recommend as rec_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[rec_module._get_design_store_dep] = _fake_store
    rec_module._recommend_store.clear()

    return TestClient(app, raise_server_exceptions=False), mock_store, rec_module


# ── US1 tests ─────────────────────────────────────────────────────────────────

def test_recommend_returns_202(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/recommend", json={"requirement_ids": ["REQ-001"]})
    assert resp.status_code == 202
    body = resp.json()
    assert "operation_id" in body and body["operation_id"]
    assert body["status"] == "pending"
    assert body["options"] == []


def test_recommend_status_returns_200(client):
    c, _, _ = client
    sub = c.post("/api/v1/designs/D-001/recommend", json={"requirement_ids": ["REQ-001"]})
    op_id = sub.json()["operation_id"]

    resp = c.get(f"/api/v1/designs/D-001/recommend/{op_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert body["status"] in ("pending", "running", "completed", "failed")
    assert isinstance(body["options"], list)


def test_recommend_empty_requirement_ids_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/recommend", json={"requirement_ids": []})
    assert resp.status_code == 422


def test_recommend_status_nonexistent_operation_returns_404(client):
    c, _, _ = client
    resp = c.get("/api/v1/designs/D-001/recommend/nonexistent-id-xyz")
    assert resp.status_code == 404


# ── US2 tests ─────────────────────────────────────────────────────────────────

def _seed_operation(module, option_id: str = "OPT-001", advisory: bool = False, already_accepted: bool = False) -> str:
    op_id = "OP-TEST-001"
    option = _make_pending_option(option_id=option_id, advisory=advisory)
    if already_accepted:
        option.status = "accepted"
    module._recommend_store[op_id] = {
        "status": "completed",
        "design_id": "D-001",
        "requirement_ids": ["REQ-001"],
        "options": {option_id: option},
        "result_summary": "1 option generated",
        "error_description": None,
        "created_at": datetime.now(timezone.utc),
    }
    return op_id


def test_accept_option_returns_200(client):
    c, mock_store, module = client
    op_id = _seed_operation(module)

    resp = c.post(
        f"/api/v1/designs/D-001/recommend/{op_id}/options/OPT-001/accept",
        json={"confirmation_id": "CONF-TEST", "advisory_acknowledged": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "elements_created" in body
    assert isinstance(body["elements_created"], list)
    assert "audit_entry_id" in body
    assert body["option_id"] == "OPT-001"
    mock_store.save.assert_called()


def test_accept_blank_confirmation_id_returns_422(client):
    c, _, module = client
    op_id = _seed_operation(module)
    resp = c.post(
        f"/api/v1/designs/D-001/recommend/{op_id}/options/OPT-001/accept",
        json={"confirmation_id": "", "advisory_acknowledged": False},
    )
    assert resp.status_code == 422


def test_accept_already_accepted_returns_409(client):
    c, _, module = client
    op_id = _seed_operation(module, already_accepted=True)
    resp = c.post(
        f"/api/v1/designs/D-001/recommend/{op_id}/options/OPT-001/accept",
        json={"confirmation_id": "CONF-TEST", "advisory_acknowledged": False},
    )
    assert resp.status_code == 409


def test_accept_advisory_without_acknowledged_returns_422(client):
    c, _, module = client
    op_id = _seed_operation(module, advisory=True)
    resp = c.post(
        f"/api/v1/designs/D-001/recommend/{op_id}/options/OPT-001/accept",
        json={"confirmation_id": "CONF-TEST", "advisory_acknowledged": False},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "advisory" in body.get("detail", "").lower()
