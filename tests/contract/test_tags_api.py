"""Contract tests for the Element Technology Tags API (ADP-SPEC-029).

T006–T011 (US1): PUT /tags endpoint
T015–T017 (US2): Free-form tags validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _make_design(design_id: str = "DSN-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-05T00:00:00Z",
        "updated_at": "2026-07-05T00:00:00Z",
        "elements": [
            {
                "id": "ELM-001", "kind": "container",
                "name": "API Gateway", "description": "Entry point",
            },
        ],
        "relationships": [],
        "requirements": [],
    })


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module
    from adp.api.routers import intake as intake_module
    from adp.api.routers import tags as tags_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[tags_module._get_design_store] = _fake_store
    app.dependency_overrides[designs_module._get_design_store] = _fake_store
    app.dependency_overrides[intake_module._get_design_store] = _fake_store

    return TestClient(app, raise_server_exceptions=False), mock_store


# ── T006: PUT returns 200 with all structured fields ──────────────────────────

def test_put_tags_returns_200(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={
        "technology": "Kong",
        "vendor": "Kong Inc.",
        "platform": "AWS EKS",
        "version": "3.4",
        "owner_team": "Platform Engineering",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["technology"] == "Kong"
    assert body["vendor"] == "Kong Inc."
    assert body["platform"] == "AWS EKS"
    assert body["version"] == "3.4"
    assert body["owner_team"] == "Platform Engineering"


# ── T007: PUT to nonexistent element returns 404 ─────────────────────────────

def test_put_tags_missing_element_returns_404(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-MISSING/tags", json={
        "technology": "Kafka",
    })
    assert resp.status_code == 404


# ── T008: PUT with field too long returns 422 ─────────────────────────────────

def test_put_tags_field_too_long_returns_422(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={
        "technology": "x" * 201,
    })
    assert resp.status_code == 422


# ── T009: PUT empty body clears all fields ────────────────────────────────────

def test_put_tags_clears_on_empty_body(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["technology"] is None
    assert body["vendor"] is None
    assert body["platform"] is None
    assert body["version"] is None
    assert body["owner_team"] is None


# ── T010: PUT writes audit entry ──────────────────────────────────────────────

def test_put_tags_writes_audit_entry(client):
    c, mock_store = client
    c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={"technology": "Kafka"})
    mock_store.save.assert_called_once()
    saved_design: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert len(saved_design.audit_log) == 1
    audit_entry = saved_design.audit_log[0]
    assert "ELM-001" in audit_entry.affected_entity
    assert "technology" in audit_entry.summary.lower()


# ── T011: GET design includes technology_metadata ────────────────────────────

def test_get_design_includes_technology_metadata(client):
    from adp.models import TechnologyMetadata
    c, mock_store = client
    design = _make_design()
    design.elements[0].technology_metadata = TechnologyMetadata(
        technology="Kong", platform="AWS EKS"
    )
    mock_store.get = AsyncMock(return_value=design)

    resp = c.get("/api/v1/designs/DSN-001")
    assert resp.status_code == 200
    body = resp.json()
    el = next(e for e in body["elements"] if e["id"] == "ELM-001")
    assert el["technology_metadata"]["technology"] == "Kong"
    assert el["technology_metadata"]["platform"] == "AWS EKS"
    assert el["technology_metadata"]["vendor"] is None


# ── T015: Free-form tags persisted ────────────────────────────────────────────

def test_put_tags_free_form_tags_persisted(client):
    c, mock_store = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={
        "tags": ["legacy", "needs-migration"],
    })
    assert resp.status_code == 200
    mock_store.save.assert_called_once()
    saved_design: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert "legacy" in saved_design.elements[0].tags
    assert "needs-migration" in saved_design.elements[0].tags


# ── T016: Blank tag returns 422 ──────────────────────────────────────────────

def test_put_tags_blank_tag_returns_422(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={
        "tags": ["valid", ""],
    })
    assert resp.status_code == 422


# ── T017: Tag too long returns 422 ───────────────────────────────────────────

def test_put_tags_tag_too_long_returns_422(client):
    c, _ = client
    resp = c.put("/api/v1/designs/DSN-001/elements/ELM-001/tags", json={
        "tags": ["a" * 51],
    })
    assert resp.status_code == 422
