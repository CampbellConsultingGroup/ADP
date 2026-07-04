"""Contract tests for the Requirements Intake API (ADP-SPEC-014).

Tests T007-T010 (US1), T017-T020 (US2), T027-T029 (US3), T034-T035 (US4).
Uses TestClient with mocked DesignStore — no database required.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.intake.models import (
    ExtractedProposal,
    ProposalStatus,
    RequirementKind,
    VerificationStatus,
)
from adp.models import ArchitectureDescription


def _make_design(design_id: str = "D-001", requirements: list | None = None) -> ArchitectureDescription:  # noqa: E501
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [],
        "requirements": requirements or [],
        "relationships": [],
    })


def _make_proposal(proposal_id: str = "PROP-001", status: ProposalStatus = ProposalStatus.PENDING) -> ExtractedProposal:  # noqa: E501
    return ExtractedProposal(
        proposal_id=proposal_id,
        operation_id="OP-001",
        submission_id="SUB-001",
        draft_statement="The system MUST handle 10,000 concurrent users without degradation",
        kind=RequirementKind.NON_FUNCTIONAL,
        source_excerpt="must handle 10,000 concurrent users",
        verification_status=VerificationStatus.VERIFIED,
        confidence=0.92,
        status=status,
    )


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import intake as intake_module
    from adp.store.operations import OperationStore

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock(return_value=None)

    # Mock OperationStore — all methods are async no-ops by default
    mock_op_store = AsyncMock(spec=OperationStore)
    mock_op_store.get = AsyncMock(return_value=None)
    mock_op_store.create = AsyncMock(return_value=None)
    mock_op_store.update = AsyncMock(return_value=None)
    mock_op_store.update_option_status = AsyncMock(return_value=True)

    app = create_app()

    async def _fake_store():
        return mock_store

    async def _fake_op_store():
        return mock_op_store

    app.dependency_overrides[intake_module._get_design_store] = _fake_store
    app.dependency_overrides[intake_module._get_op_store] = _fake_op_store

    return TestClient(app, raise_server_exceptions=False), mock_store, mock_op_store


# ── US1: Submit + poll ────────────────────────────────────────────────────────

def test_submit_intake_bulk_text_returns_202(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/intake", json={
        "mode": "bulk_text",
        "text": "The system must handle 10,000 concurrent users without degradation.",
    })
    assert resp.status_code == 202
    body = resp.json()
    assert "operation_id" in body
    assert len(body["operation_id"]) > 0
    assert body["status"] == "pending"
    assert body["design_id"] == "D-001"


def test_get_intake_status_returns_200(client):
    from unittest.mock import AsyncMock
    c, _, op_store = client
    # Submit to create an operation
    submit_resp = c.post("/api/v1/designs/D-001/intake", json={
        "mode": "bulk_text",
        "text": "The system must handle 10,000 concurrent users.",
    })
    op_id = submit_resp.json()["operation_id"]

    # Configure mock to return a pending operation for the given op_id
    op_store.get = AsyncMock(return_value={
        "id": op_id, "status": "pending", "design_id": "D-001",
        "proposals": {}, "result_summary": None, "error_description": None,
    })

    resp = c.get(f"/api/v1/designs/D-001/intake/{op_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert body["status"] in ("pending", "running", "completed", "failed")
    assert "proposals" in body


def test_submit_short_text_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/intake", json={
        "mode": "bulk_text",
        "text": "too short",
    })
    assert resp.status_code == 422
    assert "20" in json.dumps(resp.json()).lower() or "short" in json.dumps(resp.json()).lower()


def test_get_nonexistent_operation_returns_404(client):
    c, _, _ = client
    resp = c.get("/api/v1/designs/D-001/intake/nonexistent-id-xyz")
    assert resp.status_code == 404


# ── US2: Confirm / Reject ─────────────────────────────────────────────────────

def _seed_operation(
    mock_op_store,
    proposal_id: str = "PROP-001",
    status: ProposalStatus = ProposalStatus.PENDING,
) -> str:
    """Configure the mock OperationStore to return a test operation with one proposal."""
    op_id = "OP-TEST-001"
    proposal = _make_proposal(proposal_id=proposal_id, status=status)
    # Proposals stored as serialized dicts in the persistent store
    mock_op_store.get = AsyncMock(return_value={
        "id": op_id,
        "status": "completed",
        "design_id": "D-001",
        "proposals": {proposal_id: {
            "proposal_id": proposal.proposal_id,
            "operation_id": proposal.operation_id,
            "submission_id": proposal.submission_id,
            "draft_statement": proposal.draft_statement,
            "kind": proposal.kind.value,
            "source_excerpt": proposal.source_excerpt,
            "verification_status": proposal.verification_status.value,
            "confidence": proposal.confidence,
            "status": proposal.status.value,
            "confirmed_statement": proposal.confirmed_statement,
        }},
        "result_summary": "1 requirement extracted",
        "error_description": None,
    })
    return op_id


def test_confirm_proposal_creates_requirement(client):
    c, mock_store, op_store = client
    op_id = _seed_operation(op_store)

    resp = c.post(f"/api/v1/designs/D-001/intake/{op_id}/proposals/PROP-001/confirm",
                  json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "requirement_id" in body
    assert body["requirement_id"].startswith("REQ-")
    assert body["proposal_id"] == "PROP-001"
    # Verify design was saved
    mock_store.save.assert_called_once()


def test_reject_proposal_returns_200_no_requirement(client):
    c, mock_store, op_store = client
    op_id = _seed_operation(op_store)

    resp = c.post(f"/api/v1/designs/D-001/intake/{op_id}/proposals/PROP-001/reject",
                  json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["proposal_id"] == "PROP-001"


def test_confirm_already_confirmed_returns_409(client):
    c, _, op_store = client
    op_id = _seed_operation(op_store, status=ProposalStatus.CONFIRMED)

    resp = c.post(f"/api/v1/designs/D-001/intake/{op_id}/proposals/PROP-001/confirm",
                  json={})
    assert resp.status_code == 409


def test_confirm_with_edited_statement(client):
    c, mock_store, op_store = client
    op_id = _seed_operation(op_store)

    edited = "The system MUST handle 10,000 concurrent users with p99 latency < 200ms"
    resp = c.post(
        f"/api/v1/designs/D-001/intake/{op_id}/proposals/PROP-001/confirm",
        json={"edited_statement": edited},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == edited


# ── US3: Direct requirement add ───────────────────────────────────────────────

def test_add_requirement_direct_returns_201(client):
    c, mock_store, _ = client
    resp = c.post("/api/v1/designs/D-001/requirements", json={
        "statement": "The API must be stateless and handle 100 requests per second",
        "kind": "non_functional",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["requirement_id"].startswith("REQ-")
    assert body["proposal_id"] is None  # I1 fix verified
    mock_store.save.assert_called_once()


def test_add_requirement_missing_statement_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/requirements", json={"kind": "functional"})
    assert resp.status_code == 422


def test_add_requirement_short_statement_returns_422(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/requirements", json={
        "statement": "too short",
        "kind": "functional",
    })
    assert resp.status_code == 422


# ── US4: List requirements ────────────────────────────────────────────────────

def test_list_requirements_returns_200(client):
    c, mock_store, _ = client
    design = _make_design(requirements=[
        {"id": "REQ-001", "title": "Stateless API", "description": "The API must be stateless"},
    ])
    mock_store.get = AsyncMock(return_value=design)

    resp = c.get("/api/v1/designs/D-001/requirements")
    assert resp.status_code == 200
    body = resp.json()
    assert "requirements" in body
    assert "total" in body
    assert "design_id" in body
    assert body["total"] == 1


def test_list_requirements_empty_design_returns_empty(client):
    c, _, _ = client
    resp = c.get("/api/v1/designs/D-001/requirements")
    assert resp.status_code == 200
    body = resp.json()
    assert body["requirements"] == []
    assert body["total"] == 0
