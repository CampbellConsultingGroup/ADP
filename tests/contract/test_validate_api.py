"""Contract tests for the LLM-as-Judge Validation API (ADP-SPEC-008 / ADP-3ei).

First-ever HTTP contract tests for this pipeline — previously it had no route
at all. Covers: start+poll (US1-ish), override happy path, override guards
(empty justification, overriding a non-FAIL verdict), 404s, and durable
capture (ADP-3ei).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription
from adp.validation.models import (
    CriticOutput,
    Finding,
    FindingSeverity,
    GatingThreshold,
    Verdict,
    VerdictStatus,
)
from adp.validation.serde import verdict_to_dict


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [],
        "requirements": [],
        "relationships": [],
    })


def _make_verdict(status: VerdictStatus = VerdictStatus.FAIL) -> Verdict:
    return Verdict(
        verdict_id="VRD-001",
        operation_id="OP-TEST-001",
        design_id="D-001",
        design_version=2,
        status=status,
        composite_score=0.4,
        findings=[
            Finding(
                finding_id="FIND-001",
                operation_id="OP-TEST-001",
                critic_name="standards",
                severity=FindingSeverity.CRITICAL,
                description="Missing TLS citation",
                element_id="ELM-001",
                citation=None,
                score=0.1,
            ),
        ],
        thresholds_snapshot=GatingThreshold(),
        critic_outputs=[
            CriticOutput(critic_name="standards", score=0.4, input_tokens=100, output_tokens=50),
        ],
        citations_present=False,
    )


class _StatefulOpStore:
    """Async double whose update() is reflected in later get() calls — needed
    for override tests, since the route re-fetches the operation after calling
    orchestrator.override_verdict() to build its response. A plain AsyncMock's
    static return_value wouldn't reflect that write."""

    def __init__(self, initial: dict[str, dict] | None = None) -> None:
        self._rows: dict[str, dict] = {k: dict(v) for k, v in (initial or {}).items()}
        self.create = AsyncMock(side_effect=self._create)
        self.update_option_status = AsyncMock(return_value=True)

    async def _create(self, op_id, op_type, design_id, actor, initial_payload) -> None:
        self._rows[op_id] = {
            "id": op_id, "status": "pending", "design_id": design_id, "actor": actor,
            **initial_payload,
        }

    async def get(self, op_id: str) -> dict | None:
        return self._rows.get(op_id)

    async def update(
        self, op_id: str, *, status: str | None = None,
        payload_patch: dict | None = None, error: str | None = None,
    ) -> None:
        row = self._rows.setdefault(op_id, {"id": op_id, "design_id": "D-001"})
        if payload_patch:
            row.update(payload_patch)
        if status is not None:
            row["status"] = status
        if error is not None:
            row["error"] = error

    def seed(self, op_id: str, row: dict) -> None:
        self._rows[op_id] = row


def _make_mock_capture():
    from adp.store.ai_capture import ValidationCaptureStore

    mock_capture = AsyncMock(spec=ValidationCaptureStore)
    mock_capture.record_verdict = AsyncMock(return_value=None)
    mock_capture.record_override = AsyncMock(return_value=True)
    return mock_capture


def _build_client(with_capture: bool = False):
    from adp.api.app import create_app
    from adp.api.routers import validate as validate_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    mock_op_store = _StatefulOpStore()

    mock_capture = _make_mock_capture()

    app = create_app()

    async def _fake_store():
        return mock_store

    async def _fake_op_store():
        return mock_op_store

    async def _fake_capture():
        return mock_capture

    app.dependency_overrides[validate_module._get_design_store_dep] = _fake_store
    app.dependency_overrides[validate_module._get_op_store_dep] = _fake_op_store
    app.dependency_overrides[validate_module._get_validation_capture] = _fake_capture

    client = TestClient(app, raise_server_exceptions=False)
    if with_capture:
        return client, mock_store, mock_op_store, mock_capture
    return client, mock_store, mock_op_store


@pytest.fixture()
def client():
    return _build_client()


@pytest.fixture()
def client_with_capture():
    return _build_client(with_capture=True)


def _seed_operation_with_verdict(mock_op_store, status: VerdictStatus = VerdictStatus.FAIL) -> str:
    op_id = "OP-TEST-001"
    verdict = _make_verdict(status=status)
    mock_op_store.seed(op_id, {
        "id": op_id,
        "status": "completed",
        "design_id": "D-001",
        "verdict": verdict_to_dict(verdict),
        "result_summary": "FAIL — 1 blocking findings",
        "error_description": None,
    })
    return op_id


# ── Start + poll ──────────────────────────────────────────────────────────────

def test_start_validation_returns_202(client):
    c, _, _ = client
    resp = c.post("/api/v1/designs/D-001/validate", json={})
    assert resp.status_code == 202
    body = resp.json()
    assert "operation_id" in body and body["operation_id"]
    assert body["design_id"] == "D-001"
    assert body["status"] == "pending"
    assert body["verdict"] is None


def test_start_validation_nonexistent_design_returns_404(client):
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    c, mock_store, _ = client
    mock_store.get = AsyncMock(side_effect=DesignNotFoundError("D-999", "not found"))
    resp = c.post("/api/v1/designs/D-999/validate", json={})
    assert resp.status_code == 404


def test_get_validation_status_returns_200(client):
    c, _, op_store = client
    op_store.seed("OP-TEST-001", {
        "id": "OP-TEST-001", "status": "running", "design_id": "D-001",
        "verdict": None, "result_summary": None, "error_description": None,
    })
    resp = c.get("/api/v1/designs/D-001/validate/OP-TEST-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["verdict"] is None


def test_get_validation_status_with_verdict_returns_findings(client):
    c, _, op_store = client
    op_id = _seed_operation_with_verdict(op_store)
    resp = c.get(f"/api/v1/designs/D-001/validate/{op_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"]["status"] == "fail"
    assert len(body["verdict"]["findings"]) == 1
    assert body["verdict"]["findings"][0]["severity"] == "critical"


def test_get_validation_status_nonexistent_operation_returns_404(client):
    c, _, _ = client
    resp = c.get("/api/v1/designs/D-001/validate/nonexistent-id-xyz")
    assert resp.status_code == 404


# ── Override ──────────────────────────────────────────────────────────────────

def test_override_verdict_happy_path(client):
    c, mock_store, op_store = client
    op_id = _seed_operation_with_verdict(op_store, status=VerdictStatus.FAIL)

    resp = c.post(
        f"/api/v1/designs/D-001/validate/{op_id}/override",
        json={"justification": "Exception EXC-001 applies; see ADR-042"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"]["status"] == "overridden"
    assert body["verdict"]["overridden_by"]
    mock_store.save.assert_called_once()
    saved_design = mock_store.save.call_args.args[0]
    assert saved_design.audit_log[-1].action == "override-validation-verdict"


def test_override_empty_justification_returns_422(client):
    c, _, op_store = client
    op_id = _seed_operation_with_verdict(op_store)
    resp = c.post(
        f"/api/v1/designs/D-001/validate/{op_id}/override",
        json={"justification": "   "},
    )
    assert resp.status_code == 422


def test_override_non_fail_verdict_returns_422(client):
    c, _, op_store = client
    op_id = _seed_operation_with_verdict(op_store, status=VerdictStatus.PASS)
    resp = c.post(
        f"/api/v1/designs/D-001/validate/{op_id}/override",
        json={"justification": "Trying to override a pass"},
    )
    assert resp.status_code == 422


def test_override_nonexistent_operation_returns_404(client):
    c, _, _ = client
    resp = c.post(
        "/api/v1/designs/D-001/validate/nonexistent-id-xyz/override",
        json={"justification": "n/a"},
    )
    assert resp.status_code == 404


# ── ADP-3ei: durable AI process capture ───────────────────────────────────────

def test_override_verdict_writes_durable_capture(client_with_capture):
    c, _, op_store, mock_capture = client_with_capture
    op_id = _seed_operation_with_verdict(op_store, status=VerdictStatus.FAIL)

    resp = c.post(
        f"/api/v1/designs/D-001/validate/{op_id}/override",
        json={"justification": "Exception applies"},
    )
    assert resp.status_code == 200
    mock_capture.record_override.assert_awaited_once()
    kwargs = mock_capture.record_override.await_args.kwargs
    assert kwargs["justification"] == "Exception applies"
