"""Contract tests for the CALM Export API (ADP-SPEC-021 T013-T015)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-03T00:00:00Z",
        "updated_at": "2026-07-03T00:00:00Z",
        "elements": [
            {"id": "ELM-001", "kind": "person", "name": "Alice", "description": "End user"},
            {"id": "ELM-002", "kind": "system", "name": "Payment API", "description": "Handles payments"},  # noqa: E501
        ],
        "requirements": [
            {"id": "REQ-001", "title": "Scalability", "description": "Handle 10k concurrent users"},
        ],
        "relationships": [
            {"id": "REL-001", "source": "ELM-001", "target": "ELM-002", "technology": "HTTPS"},
        ],
    })


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import calm as calm_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[calm_module._get_design_store_dep] = _fake_store
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def client_not_found():
    from adp.api.app import create_app
    from adp.api.routers import calm as calm_module
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    mock_store = AsyncMock()
    mock_store.get = AsyncMock(side_effect=DesignNotFoundError("D-MISSING", "not found"))
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[calm_module._get_design_store_dep] = _fake_store
    return TestClient(app, raise_server_exceptions=False)


# ── T013: 200 with valid CALM structure ──────────────────────────────────────

def test_export_calm_returns_200_with_valid_structure(client):
    resp = client.get("/api/v1/designs/D-001/export/calm")
    assert resp.status_code == 200

    body = resp.json()
    assert "nodes" in body
    assert "relationships" in body
    assert isinstance(body["nodes"], list)
    assert len(body["nodes"]) == 2

    node = body["nodes"][0]
    assert "unique-id" in node
    assert "node-type" in node
    assert "name" in node
    assert "description" in node


def test_export_calm_maps_element_kinds(client):
    body = client.get("/api/v1/designs/D-001/export/calm").json()
    node_types = {n["unique-id"]: n["node-type"] for n in body["nodes"]}
    assert node_types["ELM-001"] == "actor"   # person → actor
    assert node_types["ELM-002"] == "system"  # system → system


def test_export_calm_includes_relationship(client):
    body = client.get("/api/v1/designs/D-001/export/calm").json()
    assert len(body["relationships"]) == 1
    rel = body["relationships"][0]
    assert rel["relationship-type"] == "connects"
    assert rel["connects"]["source-node"] == "ELM-001"
    assert rel["connects"]["destination-node"] == "ELM-002"


def test_export_calm_includes_controls_from_requirements(client):
    body = client.get("/api/v1/designs/D-001/export/calm").json()
    assert "controls" in body
    ctrl = body["controls"][0]
    assert ctrl["control-requirement-url"] == "urn:adp:requirement:REQ-001"
    assert "10k concurrent users" in ctrl["description"]


def test_export_calm_metadata_carries_provenance(client):
    body = client.get("/api/v1/designs/D-001/export/calm").json()
    assert "metadata" in body
    meta = {list(m.keys())[0]: list(m.values())[0] for m in body["metadata"]}
    assert meta["source"] == "adp"
    assert meta["design-id"] == "D-001"


# ── T014: 404 for missing design ─────────────────────────────────────────────

def test_export_calm_not_found_returns_404(client_not_found):
    resp = client_not_found.get("/api/v1/designs/D-MISSING/export/calm")
    assert resp.status_code == 404


# ── T015: Content-Disposition header ─────────────────────────────────────────

def test_export_calm_content_disposition_header(client):
    resp = client.get("/api/v1/designs/D-001/export/calm")
    assert resp.status_code == 200
    cd = resp.headers.get("content-disposition", "")
    assert "filename=" in cd
    assert ".json" in cd
    assert "D-001" in cd
