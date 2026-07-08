"""Contract tests for the Reasoning API (ADP-SPEC-027 T011-T013)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.api.deps import get_reasoning_store


def _make_record(step_name: str, option_id: str | None = "OPT-001") -> dict:
    return {
        "id": f"uuid-{step_name}",
        "operation_id": "OP-001",
        "option_id": option_id,
        "step_name": step_name,
        "model_id": "claude-sonnet-4-6",
        "reasoning_text": f"Reasoning for {step_name} step.",
        "truncated": False,
        "prompt_hash": "abc123def456" * 4,  # 48 chars, would be 64 in real usage
        "input_tokens": 100,
        "output_tokens": 50,
        "created_at": datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import reasoning as reasoning_module

    app = create_app()

    mock_store = AsyncMock()
    mock_store.list_for_operation = AsyncMock(return_value=[
        _make_record("generate"),
        _make_record("analyze_tradeoffs"),
    ])

    async def _fake_store():
        return mock_store

    app.dependency_overrides[get_reasoning_store] = _fake_store
    # Also override the local _get_reasoning_store in the router
    app.dependency_overrides[reasoning_module._get_reasoning_store] = _fake_store

    return TestClient(app, raise_server_exceptions=True), mock_store


# ── T011: 200 with records, prompt_hash excluded ──────────────────────────────

def test_list_reasoning_returns_200_with_records(client):
    c, _ = client
    resp = c.get("/api/v1/reasoning?operation_id=OP-001")
    assert resp.status_code == 200
    body = resp.json()
    assert "records" in body
    assert len(body["records"]) == 2

    rec = body["records"][0]
    assert "step_name" in rec
    assert "reasoning_text" in rec
    assert "model_id" in rec
    assert "created_at" in rec
    # prompt_hash MUST NOT be in the response
    assert "prompt_hash" not in rec


# ── T012: empty list returns 200 not 404 ─────────────────────────────────────

def test_list_reasoning_empty_returns_empty_list(client):
    c, mock_store = client
    mock_store.list_for_operation = AsyncMock(return_value=[])
    resp = c.get("/api/v1/reasoning?operation_id=MISSING-OP")
    assert resp.status_code == 200
    assert resp.json() == {"records": []}


# ── T013: option_id filter is passed to store ─────────────────────────────────

def test_list_reasoning_filters_by_option_id(client):
    c, mock_store = client
    mock_store.list_for_operation = AsyncMock(return_value=[_make_record("generate")])
    resp = c.get("/api/v1/reasoning?operation_id=OP-001&option_id=OPT-001")
    assert resp.status_code == 200
    # Verify the store was called with option_id
    mock_store.list_for_operation.assert_called_once_with("OP-001", option_id="OPT-001")


# ── Additional: operation_id is required ──────────────────────────────────────

def test_list_reasoning_missing_operation_id_returns_422(client):
    c, _ = client
    resp = c.get("/api/v1/reasoning")
    assert resp.status_code == 422
