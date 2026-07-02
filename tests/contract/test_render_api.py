"""Contract tests for POST /api/v1/designs/{id}/render (T012, T018, T019, T026 — RED)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, Element


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_construct(
        schema_version="1.0.0",
        id=design_id,
        title="Test Design",
        version=1,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
        elements=[
            Element.model_validate({
                "id": "ELM-001", "name": "API Gateway", "kind": "container",
                "satisfies": [], "provenance": None,
            }),
        ],
        relationships=[],
        requirements=[],
        audit_log=[],
    )


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.renderer.orchestrator import RenderOrchestrator

    design = _make_design()
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=design)

    app = create_app()

    async def _mock_get_render_orchestrator():
        return RenderOrchestrator(design_store=mock_store)

    from adp.api.routers import render as render_module
    app.dependency_overrides[render_module.get_render_orchestrator] = _mock_get_render_orchestrator

    return TestClient(app, raise_server_exceptions=False)


def test_render_endpoint_returns_all_three_outputs(client):
    """US1: render produces dsl + svg + png_base64."""
    resp = client.post("/api/v1/designs/D-001/render", json={"level": "container"})
    assert resp.status_code == 200
    body = resp.json()
    assert "dsl" in body and len(body["dsl"]) > 0
    assert "svg" in body and body["svg"].startswith("<svg")
    assert "png_base64" in body and len(body["png_base64"]) > 0
    # verify it decodes to valid bytes
    png_bytes = base64.b64decode(body["png_base64"])
    assert len(png_bytes) > 0


def test_render_rejects_extra_style_fields(client):
    """US2 / FR-002: extra style fields cause 422 before renderer is called."""
    resp = client.post(
        "/api/v1/designs/D-001/render",
        json={"level": "container", "fill": "#FF0000"},
    )
    assert resp.status_code == 422
    body = resp.json()
    detail_str = json.dumps(body)
    assert "fill" in detail_str or "extra" in detail_str.lower()


def test_render_rejects_per_diagram_override(client):
    """US2: any unknown field is rejected — color_scheme, override_theme, etc."""
    resp = client.post(
        "/api/v1/designs/D-001/render",
        json={"level": "container", "color_scheme": "dark", "override_theme": True},
    )
    assert resp.status_code == 422


def test_render_missing_level_returns_422(client):
    resp = client.post("/api/v1/designs/D-001/render", json={})
    assert resp.status_code == 422


def test_render_invalid_level_returns_422(client):
    resp = client.post("/api/v1/designs/D-001/render", json={"level": "invalid"})
    assert resp.status_code == 422


def test_render_endpoint_returns_422_on_bad_theme(client):
    """US3: ThemeValidationError from loader → 422 response."""
    from adp.theme.models import ThemeValidationError

    with patch("adp.theme.loader.ThemeLoader.load_and_validate") as mock_load:
        mock_load.side_effect = ThemeValidationError("Theme invalid: missing container", "required")
        resp = client.post("/api/v1/designs/D-001/render", json={"level": "container"})

    assert resp.status_code == 422
    body = resp.json()
    assert "Theme" in json.dumps(body)
