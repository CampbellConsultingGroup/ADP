"""Contract tests for the Element/Relationship CRUD API (ADP-SPEC-054).

Mirrors tests/contract/test_tags_api.py's exact AsyncMock(DesignStore) pattern --
these endpoints share the same store, not a separate SQLite-backed domain (unlike
tests/contract/test_diagrams_api_contract.py's adp.diagrams world).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, TechnologyMetadata


def _make_design(design_id: str = "DSN-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-05T00:00:00Z",
        "updated_at": "2026-07-05T00:00:00Z",
        "elements": [
            {
                "id": "ELM-001", "kind": "person", "name": "Customer",
                "description": "A real customer", "satisfies": [], "tags": ["vip"],
                "provenance": "REC-001",
            },
            {"id": "ELM-002", "kind": "system", "name": "Payments Service"},
        ],
        "relationships": [
            {"id": "REL-001", "source": "ELM-001", "target": "ELM-002", "label": "Uses"},
        ],
        "requirements": [],
    })


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import designs as designs_module
    from adp.api.routers import elements as elements_module

    design = _make_design()
    mock_store = AsyncMock()
    mock_store.get = AsyncMock(return_value=design)
    mock_store.save = AsyncMock()

    app = create_app()

    async def _fake_store():
        return mock_store

    app.dependency_overrides[elements_module._get_design_store] = _fake_store
    app.dependency_overrides[designs_module._get_design_store] = _fake_store

    return TestClient(app, raise_server_exceptions=False), mock_store, design


# ── POST /elements ────────────────────────────────────────────────────────────

def test_create_element_returns_201_with_new_id(client) -> None:
    c, mock_store, _ = client
    resp = c.post(
        "/api/v1/designs/DSN-001/elements",
        json={"kind": "container", "name": "API Gateway"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "ELM-003"
    assert body["kind"] == "container"
    assert body["name"] == "API Gateway"
    mock_store.save.assert_called_once()


def test_create_element_404_for_unknown_design(client) -> None:
    c, mock_store, _ = client
    from adp.store.store import DesignNotFoundError
    mock_store.get.side_effect = DesignNotFoundError("DSN-MISSING", "not found")
    resp = c.post("/api/v1/designs/DSN-MISSING/elements", json={"kind": "system", "name": "T"})
    assert resp.status_code == 404


def test_create_element_422_for_invalid_kind(client) -> None:
    c, _, _ = client
    resp = c.post("/api/v1/designs/DSN-001/elements", json={"kind": "database", "name": "T"})
    assert resp.status_code == 422


def test_create_element_422_for_blank_name(client) -> None:
    c, _, _ = client
    resp = c.post("/api/v1/designs/DSN-001/elements", json={"kind": "system", "name": ""})
    assert resp.status_code == 422


def test_create_element_writes_audit_entry(client) -> None:
    c, mock_store, _ = client
    c.post("/api/v1/designs/DSN-001/elements", json={"kind": "system", "name": "New Sys"})
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    entry = saved.audit_log[-1]
    assert entry.action == "create-element"
    assert entry.affected_entity == "ELM-003"


# ── PATCH /elements/{id} ──────────────────────────────────────────────────────

def test_update_element_renames_and_preserves_other_fields(client) -> None:
    c, mock_store, _ = client
    resp = c.patch("/api/v1/designs/DSN-001/elements/ELM-001", json={"name": "Renamed Customer"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed Customer"
    # FR-011: description/satisfies/provenance/tags/technology_metadata untouched.
    assert body["description"] == "A real customer"
    assert body["tags"] == ["vip"]
    assert body["provenance"] == "REC-001"
    mock_store.save.assert_called_once()


def test_update_element_404_for_unknown_element(client) -> None:
    c, _, _ = client
    resp = c.patch("/api/v1/designs/DSN-001/elements/ELM-MISSING", json={"name": "X"})
    assert resp.status_code == 404


def test_update_element_422_for_blank_name(client) -> None:
    c, _, _ = client
    resp = c.patch("/api/v1/designs/DSN-001/elements/ELM-001", json={"name": ""})
    assert resp.status_code == 422


def test_update_element_preserves_technology_metadata(client) -> None:
    c, mock_store, design = client
    design.elements[1].technology_metadata = TechnologyMetadata(technology="Kong")
    resp = c.patch("/api/v1/designs/DSN-001/elements/ELM-002", json={"name": "Payments API"})
    assert resp.status_code == 200
    assert resp.json()["technology_metadata"]["technology"] == "Kong"


# ── DELETE /elements/{id} ─────────────────────────────────────────────────────

def test_delete_element_cascades_relationships(client) -> None:
    c, mock_store, _ = client
    resp = c.delete("/api/v1/designs/DSN-001/elements/ELM-001")
    assert resp.status_code == 204
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert not any(e.id == "ELM-001" for e in saved.elements)
    # The relationship referencing ELM-001 must be gone too, or validate_references
    # would reject the save (a dangling relationship endpoint).
    assert not any(r.id == "REL-001" for r in saved.relationships)
    actions = [e.action for e in saved.audit_log]
    assert "delete-element" in actions
    assert "delete-relationship" in actions


def test_delete_element_404_for_unknown_element(client) -> None:
    c, _, _ = client
    resp = c.delete("/api/v1/designs/DSN-001/elements/ELM-MISSING")
    assert resp.status_code == 404


def test_delete_element_without_relationships_succeeds(client) -> None:
    c, mock_store, _ = client
    resp = c.delete("/api/v1/designs/DSN-001/elements/ELM-002")
    assert resp.status_code == 204
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    # ELM-002 deleted; its relationship (REL-001, target=ELM-002) cascades too.
    assert not any(e.id == "ELM-002" for e in saved.elements)
    assert not any(r.id == "REL-001" for r in saved.relationships)


# ── POST /relationships ───────────────────────────────────────────────────────

def test_create_relationship_returns_201(client) -> None:
    c, mock_store, _ = client
    resp = c.post(
        "/api/v1/designs/DSN-001/relationships",
        json={"source": "ELM-001", "target": "ELM-002", "label": "Calls"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "REL-002"
    assert body["source"] == "ELM-001"
    assert body["target"] == "ELM-002"
    assert body["label"] == "Calls"
    mock_store.save.assert_called_once()


def test_create_relationship_422_for_unknown_source(client) -> None:
    c, _, _ = client
    resp = c.post(
        "/api/v1/designs/DSN-001/relationships",
        json={"source": "ELM-MISSING", "target": "ELM-002"},
    )
    assert resp.status_code == 422


def test_create_relationship_422_for_unknown_target(client) -> None:
    c, _, _ = client
    resp = c.post(
        "/api/v1/designs/DSN-001/relationships",
        json={"source": "ELM-001", "target": "ELM-MISSING"},
    )
    assert resp.status_code == 422


def test_create_relationship_writes_audit_entry(client) -> None:
    c, mock_store, _ = client
    c.post("/api/v1/designs/DSN-001/relationships", json={"source": "ELM-001", "target": "ELM-002"})
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    entry = saved.audit_log[-1]
    assert entry.action == "create-relationship"
    assert entry.affected_entity == "REL-002"


# ── DELETE /relationships/{id} ────────────────────────────────────────────────

def test_delete_relationship_returns_204_and_leaves_elements_intact(client) -> None:
    c, mock_store, _ = client
    resp = c.delete("/api/v1/designs/DSN-001/relationships/REL-001")
    assert resp.status_code == 204
    saved: ArchitectureDescription = mock_store.save.call_args[0][0]
    assert not any(r.id == "REL-001" for r in saved.relationships)
    assert len(saved.elements) == 2  # both elements untouched


def test_delete_relationship_404_for_unknown_relationship(client) -> None:
    c, _, _ = client
    resp = c.delete("/api/v1/designs/DSN-001/relationships/REL-MISSING")
    assert resp.status_code == 404
