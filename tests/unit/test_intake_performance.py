"""Performance timing tests for SC-001 and SC-006 (ADP-SPEC-014 T048)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _make_design() -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": "D-PERF",
        "title": "Performance Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [],
        "requirements": [],
        "relationships": [],
    })


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import intake as intake_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[intake_module._get_design_store] = _fake_store
    intake_module._intake_store.clear()

    return TestClient(app, raise_server_exceptions=False), intake_module


def test_sc001_submit_returns_operation_id_within_2s(client):
    """SC-001: POST /intake must return operation_id within 2 seconds.

    The endpoint returns immediately (extraction is a BackgroundTask),
    so 2s is very generous — expect ~10-100ms in practice.
    """
    c, _ = client
    t0 = time.perf_counter()
    resp = c.post("/api/v1/designs/D-PERF/intake", json={
        "mode": "bulk_text",
        "text": "The system must handle 10,000 concurrent users without degradation.",
    })
    elapsed = time.perf_counter() - t0

    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text[:100]}"
    assert elapsed <= 2.0, f"SC-001 violated: submit took {elapsed:.3f}s (limit 2s)"
    assert "operation_id" in resp.json()


def test_sc006_direct_add_requirement_within_2s(client):
    """SC-006: POST /requirements (structured form) must complete within 2 seconds."""
    c, _ = client
    t0 = time.perf_counter()
    resp = c.post("/api/v1/designs/D-PERF/requirements", json={
        "statement": "The API must be stateless and respond within 200ms at p99",
        "kind": "non_functional",
    })
    elapsed = time.perf_counter() - t0

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text[:100]}"
    assert elapsed <= 2.0, f"SC-006 violated: direct add took {elapsed:.3f}s (limit 2s)"
    assert resp.json()["requirement_id"].startswith("REQ-")
