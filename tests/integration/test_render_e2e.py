"""E2E render pipeline integration test — no database, no Docker (T033)."""

from __future__ import annotations

import base64
import time
from unittest.mock import MagicMock

from adp.models import ArchitectureDescription, Element, Relationship
from adp.renderer.orchestrator import RenderOrchestrator


def _make_full_design(num_elements: int = 4) -> ArchitectureDescription:
    elements = [
        Element.model_validate({"id": "ELM-001", "name": "User", "kind": "person", "satisfies": [], "provenance": None}),  # noqa: E501
        Element.model_validate({"id": "ELM-002", "name": "Web System", "kind": "system", "satisfies": [], "provenance": None}),  # noqa: E501
        Element.model_validate({"id": "ELM-003", "name": "API Gateway", "kind": "container", "satisfies": [], "provenance": None}),  # noqa: E501
        Element.model_validate({"id": "ELM-004", "name": "Auth Handler", "kind": "component", "satisfies": [], "provenance": None}),  # noqa: E501
    ][:num_elements]

    rels = [
        Relationship.model_validate({"id": "REL-001", "source": "ELM-001", "target": "ELM-002", "label": "uses"}),  # noqa: E501
        Relationship.model_validate({"id": "REL-002", "source": "ELM-002", "target": "ELM-003", "label": "routes to"}),  # noqa: E501
    ]

    return ArchitectureDescription.model_construct(
        schema_version="1.0.0",
        id="D-001",
        title="E2E Test Design",
        version=1,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
        elements=elements,
        relationships=[r for r in rels if r.source in {e.id for e in elements} and r.target in {e.id for e in elements}],  # noqa: E501
        requirements=[],
        audit_log=[],
    )


def _make_orchestrator(design: ArchitectureDescription) -> RenderOrchestrator:
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=design)
    return RenderOrchestrator(design_store=mock_store)


def test_full_render_pipeline():
    design = _make_full_design()
    orchestrator = _make_orchestrator(design)

    result = orchestrator.render("D-001", "container")

    # DSL assertions
    assert len(result.dsl) > 0
    assert "workspace" in result.dsl
    assert "API Gateway" in result.dsl  # container element visible at container level
    assert "Web System" in result.dsl   # system element visible at container level

    # SVG assertions
    assert result.svg.startswith("<svg")
    assert "#2874A6" in result.svg  # container fill color (locked theme)

    # PNG assertions
    png_bytes = base64.b64decode(result.png_base64)
    assert len(png_bytes) > 0
    assert png_bytes[:4] == b"\x89PNG"  # PNG magic bytes

    # Metadata
    assert result.design_id == "D-001"
    assert result.level == "container"


def test_render_is_deterministic():
    """SC-006: byte-identical DSL output for same model and theme."""
    design = _make_full_design()
    orchestrator = _make_orchestrator(design)

    result1 = orchestrator.render("D-001", "container")
    result2 = orchestrator.render("D-001", "container")

    assert result1.dsl == result2.dsl, "DSL must be byte-identical across renders"


def test_full_render_pipeline_sc002_timing():
    """SC-002: render of 50 elements must complete in ≤ 30 seconds."""
    elements = [
        Element.model_validate({
            "id": f"ELM-{i:03d}", "name": f"Service {i}", "kind": "container",
            "satisfies": [], "provenance": None,
        })
        for i in range(1, 51)
    ]
    design = ArchitectureDescription.model_construct(
        schema_version="1.0.0", id="D-PERF", title="Perf Test", version=1,
        created_at="2026-07-01T00:00:00Z", updated_at="2026-07-01T00:00:00Z",
        elements=elements, relationships=[], requirements=[], audit_log=[],
    )
    orchestrator = _make_orchestrator(design)

    t0 = time.perf_counter()
    result = orchestrator.render("D-PERF", "container")
    elapsed = time.perf_counter() - t0

    assert elapsed <= 30.0, f"SC-002 violated: render took {elapsed:.2f}s (limit 30s)"
    assert "#2874A6" in result.svg
