"""Contract tests for export/import endpoints (T020, T024, T030)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": design_id,
        "title": "Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [{"id": "ELM-001", "name": "API", "kind": "container", "satisfies": [], "provenance": None}],  # noqa: E501
        "requirements": [],
        "relationships": [],
    })


@pytest.fixture()
def client(tmp_path):
    from adp.api.app import create_app
    from adp.api.routers import export_router as export_module

    design = _make_design()
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=design)

    app = create_app()

    async def _get_store():
        return mock_store

    if hasattr(export_module, "get_design_store"):
        app.dependency_overrides[export_module.get_design_store] = _get_store

    return TestClient(app, raise_server_exceptions=False), tmp_path


def test_export_without_confirmation_returns_422(client):
    c, _ = client
    resp = c.post("/api/v1/designs/D-001/export", json={"confirmation_id": "", "export_root": "/tmp/test"})  # noqa: E501
    assert resp.status_code == 422
    body = json.dumps(resp.json())
    assert "confirmation_id" in body.lower() or "consequential" in body.lower()


def test_export_without_confirmation_id_field_returns_422(client):
    c, _ = client
    resp = c.post("/api/v1/designs/D-001/export", json={"export_root": "/tmp/test"})
    assert resp.status_code == 422


def test_export_api_returns_audit_entry_id(client, tmp_path):
    c, tmp = client
    export_root = str(tmp)

    with patch("adp.export.bundle.ExportOrchestrator.export") as mock_export:
        from adp.export.models import ExportResult
        mock_export.return_value = ExportResult(
            design_id="D-001",
            model_version=1,
            export_path=f"{export_root}/exports/D-001/v1",
            artifacts=["model.json"],
            audit_entry_id="AUD-001",
        )
        resp = c.post(
            "/api/v1/designs/D-001/export",
            json={"confirmation_id": "CONF-TEST", "export_root": export_root},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "audit_entry_id" in body
    assert body["audit_entry_id"]


def test_import_api_returns_element_count(client):
    c, _ = client
    design = _make_design()
    model_json = design.model_dump_json()

    resp = c.post("/api/v1/designs/import", json={"model_json": model_json})
    assert resp.status_code == 200
    body = resp.json()
    assert "element_count" in body
    assert body["element_count"] == 1
    assert body["validation_warnings"] == []


def test_import_api_rejects_wrong_schema_version(client):
    c, _ = client
    data = {"schema_version": "99.0.0", "id": "D-001", "title": "T",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
    resp = c.post("/api/v1/designs/import", json={"model_json": json.dumps(data)})
    assert resp.status_code == 422
    body = json.dumps(resp.json())
    assert "99.0.0" in body or "schema" in body.lower()
