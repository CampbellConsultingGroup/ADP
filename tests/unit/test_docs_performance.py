"""Performance timing tests for SC-001 and SC-004 (T038)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from adp.models import ArchitectureDescription, Element
from adp.theme.models import RenderResult


def _make_large_design(num_elements: int = 50) -> ArchitectureDescription:
    elements = [
        Element.model_validate({
            "id": f"ELM-{i:03d}",
            "name": f"Service {i}",
            "kind": "container",
            "satisfies": [],
            "provenance": None,
        })
        for i in range(1, num_elements + 1)
    ]
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": "D-PERF",
        "title": "Performance Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [e.model_dump() for e in elements],
        "requirements": [],
        "relationships": [],
    })


def test_sc001_document_generation_under_60s():
    """SC-001: stakeholder document for 50-element design generated in ≤ 60 seconds."""
    from adp.docs.generator import DocumentGenerator

    design = _make_large_design(50)
    t0 = time.perf_counter()
    DocumentGenerator().generate(design)
    elapsed = time.perf_counter() - t0

    assert elapsed <= 60.0, f"SC-001 violated: document generation took {elapsed:.2f}s (limit 60s)"


def test_sc004_export_bundle_under_120s(tmp_path):
    """SC-004: export bundle for 50-element design completes in ≤ 120 seconds."""
    from adp.export.bundle import ExportOrchestrator

    design = _make_large_design(50)
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=design)

    _mock_result = RenderResult(
        design_id="D-PERF",
        level="container",  # type: ignore[arg-type]
        dsl="workspace {}",
        svg="<svg></svg>",
        png_base64="aGVsbG8=",
    )
    mock_render = MagicMock()
    mock_render.render = MagicMock(return_value=_mock_result)

    # arender must be a coroutine function so bundle.py's async path works
    async def _async_render(did: str, level: str) -> RenderResult:
        return _mock_result

    mock_render.arender = _async_render

    orchestrator = ExportOrchestrator(design_store=mock_store, render_orchestrator=mock_render)

    t0 = time.perf_counter()
    orchestrator.export("D-PERF", str(tmp_path), confirmation_id="CONF-PERF", actor="test")
    elapsed = time.perf_counter() - t0

    assert elapsed <= 120.0, f"SC-004 violated: export took {elapsed:.2f}s (limit 120s)"
