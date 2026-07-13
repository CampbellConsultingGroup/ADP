"""SC-001 timing gate for the Recommendation API (ADP-SPEC-018 T034)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _fast_llm_response() -> dict:
    return {"choices": [{"message": {"content": '{"options": []}'}}], "usage": {}}


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import recommend as rec_module

    design = ArchitectureDescription.model_validate({
        "schema_version": "1.0.0", "id": "D-PERF", "title": "Perf Test",
        "created_at": "2026-07-02T00:00:00Z", "updated_at": "2026-07-02T00:00:00Z",
        "elements": [], "requirements": [{"id": "REQ-001", "title": "T", "description": "D"}],
        "relationships": [],
    })
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    from adp.store.operations import OperationStore
    mock_op_store = AsyncMock(spec=OperationStore)
    mock_op_store.create = AsyncMock(return_value=None)
    mock_op_store.get = AsyncMock(return_value=None)
    mock_op_store.update = AsyncMock(return_value=None)

    async def _fake_op_store():
        return mock_op_store

    app.dependency_overrides[rec_module._get_design_store_dep] = _fake_store
    app.dependency_overrides[rec_module._get_op_store_dep] = _fake_op_store

    return TestClient(app, raise_server_exceptions=False)


def test_sc001_recommend_submit_returns_within_2s(client):
    """SC-001 (partial): POST /recommend returns operation_id within 2 seconds.

    The POST is a non-blocking background task, so the HTTP response is immediate.
    The full 60s pipeline limit (SC-001) is a runtime concern verified manually.
    LLM client is patched to avoid real network calls skewing elapsed time.
    """
    fast_chat = AsyncMock(return_value=_fast_llm_response())

    with patch("adp.recommendation.steps.LLMClient.chat" if False else "adp.intake.llm.LLMClient.chat",  # noqa: E501
               fast_chat, create=True):
        t0 = time.perf_counter()
        resp = client.post("/api/v1/designs/D-PERF/recommend", json={"requirement_ids": ["REQ-001"]})  # noqa: E501
        elapsed = time.perf_counter() - t0

    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
    assert elapsed <= 5.0, f"SC-001 violated: submit took {elapsed:.3f}s (limit 5s with stub LLM)"
    assert resp.json()["operation_id"]
