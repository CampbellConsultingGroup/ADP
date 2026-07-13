"""Contract tests for document/traceability/views endpoints (T008, T011, T012, T017)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from adp.models import ArchitectureDescription, Element, Requirement
from adp.theme.models import RenderResult


def _make_design(design_id: str = "D-001") -> ArchitectureDescription:
    return ArchitectureDescription.model_construct(
        schema_version="1.0.0",
        id=design_id,
        title="Test Design",
        created_at="2026-07-02T00:00:00Z",
        updated_at="2026-07-02T00:00:00Z",
        elements=[
            Element.model_validate({"id": "ELM-001", "name": "API Gateway", "kind": "container", "satisfies": ["REQ-001"], "provenance": "OPT-001"}),  # noqa: E501
            Element.model_validate({"id": "ELM-002", "name": "User", "kind": "person", "satisfies": [], "provenance": None}),  # noqa: E501
        ],
        requirements=[
            Requirement.model_validate({"id": "REQ-001", "title": "Stateless handling", "description": "Must be stateless."}),  # noqa: E501
        ],
        relationships=[],
    )


def _make_render_result(level: str) -> RenderResult:
    return RenderResult(
        design_id="D-001",
        level=level,  # type: ignore[arg-type]
        dsl="workspace { model { } views { } }",
        svg="<svg></svg>",
        png_base64="aGVsbG8=",
    )


@pytest.fixture()
def client():
    from adp.api.app import create_app
    from adp.api.routers import documents as docs_module

    design = _make_design()
    mock_store = MagicMock()

    async def _fake_get(did: str):
        if did == "D-001":
            return design
        return None

    mock_store.get = _fake_get

    app = create_app()

    async def _get_store():
        return mock_store

    async def _get_render_orch():
        from adp.renderer.orchestrator import RenderOrchestrator
        mock_render = MagicMock(spec=RenderOrchestrator)

        async def _fake_arender(did: str, level: str) -> RenderResult:
            return _make_render_result(level)

        mock_render.arender = _fake_arender
        return mock_render

    if hasattr(docs_module, "get_design_store"):
        app.dependency_overrides[docs_module.get_design_store] = _get_store
    if hasattr(docs_module, "get_render_orchestrator"):
        app.dependency_overrides[docs_module.get_render_orchestrator] = _get_render_orch

    return TestClient(app, raise_server_exceptions=False)


def test_document_api_returns_200_with_frontmatter(client):
    resp = client.get("/api/v1/designs/D-001/document")
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("---")
    ct = resp.headers.get("content-type", "")
    assert "text" in ct


def test_document_api_404_for_unknown_design(client):
    resp = client.get("/api/v1/designs/NONEXISTENT/document")
    assert resp.status_code == 404


def test_views_returns_all_three_levels(client):
    resp = client.get("/api/v1/designs/D-001/views")
    assert resp.status_code == 200
    body = resp.json()
    assert "design_id" in body
    assert "context" in body
    assert "container" in body
    assert "component" in body
    for level_key in ("context", "container", "component"):
        lvl = body[level_key]
        assert "dsl" in lvl
        assert "svg" in lvl
        assert "png_base64" in lvl


def test_views_calls_renderer_once_per_level(client):
    resp = client.get("/api/v1/designs/D-001/views")
    assert resp.status_code == 200
    body = resp.json()
    # Each level must have a different level field in the result
    assert body["context"]["level"] == "context"
    assert body["container"]["level"] == "container"
    assert body["component"]["level"] == "component"


def test_traceability_api_returns_200_with_orphan_count(client):
    resp = client.get("/api/v1/designs/D-001/traceability")
    assert resp.status_code == 200
    body = resp.json()
    assert "orphan_count" in body
    assert "total_elements" in body
    assert body["total_elements"] == 2  # design has 2 elements
    assert body["orphan_count"] == 1    # ELM-002 (User) has no satisfied requirements
