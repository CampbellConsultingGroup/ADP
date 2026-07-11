"""Contract tests for the Design Lifecycle API (ADP-SPEC-030).

T006–T011 (US1): PATCH /lifecycle transitions
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, LifecycleStatus


def _make_design(
    design_id: str = "DSN-001",
    lifecycle_status: LifecycleStatus = LifecycleStatus.DRAFT,
    proposed_date: datetime | None = None,
) -> ArchitectureDescription:
    design = ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-05T00:00:00Z",
        "updated_at": "2026-07-05T00:00:00Z",
        "elements": [],
        "relationships": [],
        "requirements": [],
    })
    design.lifecycle_status = lifecycle_status
    design.proposed_date = proposed_date
    return design


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import lifecycle as lifecycle_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[lifecycle_module._get_design_store] = _fake_store
    return TestClient(app, raise_server_exceptions=False), mock_store


# ── T006: draft → proposed returns 200 ───────────────────────────────────────

def test_patch_lifecycle_draft_to_proposed_returns_200(client):
    c, _ = client
    resp = c.patch("/api/v1/designs/DSN-001/lifecycle", json={"status": "proposed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["lifecycle_status"] == "proposed"
    assert body["proposed_date"] is not None


# ── T007: invalid transition returns 409 ─────────────────────────────────────

def test_patch_lifecycle_invalid_transition_returns_409(client):
    c, _ = client
    resp = c.patch("/api/v1/designs/DSN-001/lifecycle", json={"status": "decommissioned"})
    assert resp.status_code == 409
    body = resp.json()
    assert "proposed" in body["detail"].lower() or "valid" in body["detail"].lower()


# ── T008: transition writes audit entry ──────────────────────────────────────

def test_patch_lifecycle_writes_audit_entry(client):
    c, mock_store = client
    c.patch("/api/v1/designs/DSN-001/lifecycle", json={"status": "proposed"})
    mock_store.save.assert_called_once()
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert len(saved.audit_log) == 1
    entry = saved.audit_log[0]
    assert "draft" in entry.summary.lower() or "proposed" in entry.summary.lower()


# ── T009: date override respected ────────────────────────────────────────────

def test_patch_lifecycle_date_override_respected(client):
    c, _ = client
    override = "2026-01-01T00:00:00Z"
    resp = c.patch("/api/v1/designs/DSN-001/lifecycle", json={
        "status": "proposed",
        "proposed_date": override,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_date"].startswith("2026-01-01")


# ── T010: auto-date does not overwrite existing ───────────────────────────────

def test_patch_lifecycle_auto_date_does_not_overwrite_existing(client):
    from adp.api.app import create_app
    from adp.api.routers import lifecycle as lifecycle_module

    existing_date = datetime(2025, 6, 1, tzinfo=timezone.utc)
    design = _make_design(lifecycle_status=LifecycleStatus.PROPOSED, proposed_date=existing_date)
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()
    app.dependency_overrides[lifecycle_module._get_design_store] = lambda: mock_store

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.patch("/api/v1/designs/DSN-001/lifecycle", json={"status": "current"})
    assert resp.status_code == 200
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    # proposed_date must not have been changed
    assert saved.proposed_date == existing_date


# ── T011: note in audit entry ─────────────────────────────────────────────────

def test_patch_lifecycle_with_note_included_in_audit_entry(client):
    from adp.api.app import create_app
    from adp.api.routers import lifecycle as lifecycle_module

    design = _make_design(lifecycle_status=LifecycleStatus.CURRENT)
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()
    app.dependency_overrides[lifecycle_module._get_design_store] = lambda: mock_store

    c = TestClient(app, raise_server_exceptions=False)
    resp = c.patch("/api/v1/designs/DSN-001/lifecycle", json={
        "status": "deprecated",
        "note": "Superseded by DSN-042",
    })
    assert resp.status_code == 200
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert any("Superseded by DSN-042" in e.summary for e in saved.audit_log)
