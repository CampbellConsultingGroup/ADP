"""Integration tests for ExportOrchestrator (T021-T023)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from adp.models import ArchitectureDescription
from adp.theme.models import RenderResult


@pytest.fixture(autouse=True)
def _clean_tables():
    """Override conftest.py's async autouse table-truncation fixture
    (ADP-isj) with a no-op: this file has no DB and mixes in plain (sync)
    test functions, which pytest-asyncio doesn't allow to depend on an
    async autouse fixture (confirmed by direct experiment)."""
    yield


def _make_design() -> ArchitectureDescription:
    return ArchitectureDescription.model_validate({
        "schema_version": "1.0.0",
        "id": "D-001",
        "title": "Integration Test Design",
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T00:00:00Z",
        "elements": [
            {"id": "ELM-001", "name": "API", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
        ],
        "requirements": [],
        "relationships": [],
    })


def _mock_render_result(level: str) -> RenderResult:
    return RenderResult(
        design_id="D-001",
        level=level,  # type: ignore[arg-type]
        dsl="workspace { }",
        svg="<svg></svg>",
        png_base64="aGVsbG8=",  # base64("hello")
    )


@pytest.fixture()
def mock_setup():
    design = _make_design()
    mock_store = MagicMock()
    mock_store.get = MagicMock(return_value=design)

    mock_render = MagicMock()
    mock_render.render = MagicMock(side_effect=lambda did, level: _mock_render_result(level))

    return mock_store, mock_render, design


def test_export_writes_all_artifacts(tmp_path, mock_setup):
    from adp.export.bundle import ExportOrchestrator

    mock_store, mock_render, _ = mock_setup
    orch = ExportOrchestrator(design_store=mock_store, render_orchestrator=mock_render)
    result = orch.export("D-001", str(tmp_path), confirmation_id="CONF-TEST", actor="test-actor")

    export_dir = Path(result.export_path)
    assert export_dir.exists()

    expected = [
        "model.json", "model.yaml", "traceability.json", "README.md",
        "context/diagram.dsl", "context/diagram.svg", "context/diagram.png",
        "container/diagram.dsl", "container/diagram.svg", "container/diagram.png",
        "component/diagram.dsl", "component/diagram.svg", "component/diagram.png",
    ]
    for artifact in expected:
        assert (export_dir / artifact).exists(), f"Missing artifact: {artifact}"

    assert result.audit_entry_id.startswith("AUD-")


def test_export_is_atomic_on_failure(tmp_path, mock_setup):
    from adp.export.bundle import ExportOrchestrator

    mock_store, mock_render, _ = mock_setup
    mock_render.render = MagicMock(side_effect=RuntimeError("render failed"))

    orch = ExportOrchestrator(design_store=mock_store, render_orchestrator=mock_render)
    with pytest.raises(RuntimeError):
        orch.export("D-001", str(tmp_path), confirmation_id="CONF-TEST", actor="test-actor")

    export_dir = tmp_path / "exports" / "D-001" / "v1"
    assert not export_dir.exists(), "Partial export directory must NOT exist after failure"


def test_export_rejects_if_directory_exists(tmp_path, mock_setup):
    from adp.export.bundle import ExportOrchestrator

    mock_store, mock_render, _ = mock_setup
    # Pre-create the export directory
    export_dir = tmp_path / "exports" / "D-001" / "v1"
    export_dir.mkdir(parents=True)

    orch = ExportOrchestrator(design_store=mock_store, render_orchestrator=mock_render)
    with pytest.raises(FileExistsError):
        orch.export("D-001", str(tmp_path), confirmation_id="CONF-TEST", actor="test-actor")


def test_export_model_json_contains_audit_entry(tmp_path, mock_setup):
    """The exported model.json must contain an audit entry for the export action."""
    import json as _json

    from adp.export.bundle import ExportOrchestrator

    mock_store, mock_render, _ = mock_setup
    orch = ExportOrchestrator(design_store=mock_store, render_orchestrator=mock_render)
    result = orch.export("D-001", str(tmp_path), confirmation_id="CONF-TEST", actor="test-actor")

    export_dir = Path(result.export_path)
    model_data = _json.loads((export_dir / "model.json").read_text())
    audit_log = model_data.get("audit_log", [])
    assert len(audit_log) >= 1
    actions = [e["action"] for e in audit_log]
    assert "export_design" in actions
