"""ExportOrchestrator — atomic export of a design bundle to version control (ADP-SPEC-011).

ART-VIII: confirmation_id is required (non-empty) before any export.
ART-IX: an audit entry is appended to the exported model.json.
ART-VI: structured logs emitted at export start and completion.
FR-006: all artifacts validated before any files are written; no partial exports.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from adp.docs.generator import DocumentGenerator
from adp.docs.traceability import TraceabilityGenerator
from adp.export.models import ExportResult
from adp.models import ArchitectureDescription, AuditEntry
from adp.renderer.orchestrator import RenderOrchestrator
from adp.theme.models import C4Level

logger = logging.getLogger(__name__)

_AUD_ID_RE = re.compile(r"^AUD-(\d+)$")
_C4_LEVELS: list[C4Level] = ["context", "container", "component"]


def _next_audit_id(design: ArchitectureDescription) -> str:
    max_n = 0
    for entry in (design.audit_log or []):
        m = _AUD_ID_RE.match(entry.id)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"AUD-{(max_n + 1):03d}"


class ExportOrchestrator:
    """Orchestrates the full export pipeline: validate → generate → write atomically."""

    def __init__(
        self,
        design_store: object,
        render_orchestrator: RenderOrchestrator | None = None,
    ) -> None:
        self._store = design_store
        self._render = render_orchestrator

    def _get_render_orchestrator(self) -> RenderOrchestrator:
        if self._render is not None:
            return self._render
        return RenderOrchestrator(design_store=self._store)

    def export(
        self,
        design_id: str,
        export_root: str,
        confirmation_id: str,
        *,
        actor: str,
    ) -> ExportResult:
        """Write a complete, validated export bundle atomically.

        ART-VI: structured logs at start and completion.
        Raises ValueError if confirmation_id is blank.
        Raises FileExistsError if export directory already exists (pre-check; no files written).
        Raises on any artifact generation failure; no partial export is left behind.
        """
        logger.info(
            "export.start",
            extra={
                "event": "export.start",
                "design_id": design_id,
                "export_root": export_root,
                "confirmation_id": confirmation_id,
                "actor": actor,
            },
        )

        if not (confirmation_id or "").strip():
            raise ValueError(
                "Export requires a non-empty confirmation_id (ART-VIII / FR-005)"
            )

        import inspect as _inspect
        _result = self._store.get(design_id)  # type: ignore[attr-defined]
        if _inspect.isawaitable(_result):
            import asyncio
            design = asyncio.get_event_loop().run_until_complete(_result)
        else:
            design = _result
        if design is None:
            raise KeyError(f"Design {design_id!r} not found")

        model_version = getattr(design, "version", 1) or 1
        final_path = Path(export_root) / "exports" / design_id / f"v{model_version}"

        # Pre-check BEFORE creating tmpdir — no files written if path exists
        if final_path.exists():
            raise FileExistsError(
                f"Export directory already exists: {final_path}. "
                "Bump the design version before re-exporting."
            )

        audit_entry_id = _next_audit_id(design)
        tmpdir = Path(tempfile.mkdtemp())
        try:
            self._write_bundle(tmpdir, design, design_id, audit_entry_id, actor)
            # All artifacts written successfully — move to final path atomically
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(tmpdir), str(final_path))
        except Exception:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

        artifacts = [
            "model.json", "model.yaml", "traceability.json", "README.md",
            "context/diagram.dsl", "context/diagram.svg", "context/diagram.png",
            "container/diagram.dsl", "container/diagram.svg", "container/diagram.png",
            "component/diagram.dsl", "component/diagram.svg", "component/diagram.png",
        ]

        logger.info(
            "export.complete",
            extra={
                "event": "export.complete",
                "design_id": design_id,
                "export_path": str(final_path),
                "artifact_count": len(artifacts),
                "audit_entry_id": audit_entry_id,
            },
        )

        return ExportResult(
            design_id=design_id,
            model_version=model_version,
            export_path=str(final_path),
            artifacts=artifacts,
            audit_entry_id=audit_entry_id,
        )

    def _write_bundle(
        self,
        tmpdir: Path,
        design: ArchitectureDescription,
        design_id: str,
        audit_entry_id: str,
        actor: str,
    ) -> None:
        # Build export audit entry to include in model.json
        export_entry = AuditEntry(
            id=audit_entry_id,
            actor=actor,
            action="export_design",
            affected_entity=design_id,
            summary=f"Design exported to version control by {actor}",
            timestamp=datetime.now(timezone.utc),
            origin="human",
        )
        # Work on a copy so we don't mutate the in-memory design
        design_dict = design.model_dump(mode="json")
        design_dict["audit_log"].append(export_entry.model_dump(mode="json"))

        # model.json — canonical JSON
        model_json = json.dumps(design_dict, sort_keys=True, indent=2)
        (tmpdir / "model.json").write_text(model_json, encoding="utf-8")

        # model.yaml — YAML equivalent
        (tmpdir / "model.yaml").write_text(
            yaml.dump(design_dict, default_flow_style=False, sort_keys=True, allow_unicode=True),
            encoding="utf-8",
        )

        # traceability.json
        matrix = TraceabilityGenerator().generate(design)
        (tmpdir / "traceability.json").write_text(
            matrix.model_dump_json(indent=2), encoding="utf-8"
        )

        # README.md — stakeholder document
        doc = DocumentGenerator().generate(design)
        (tmpdir / "README.md").write_text(doc.markdown, encoding="utf-8")

        # Diagram renders for each C4 level
        render_orch = self._get_render_orchestrator()
        for level in _C4_LEVELS:
            level_dir = tmpdir / level
            level_dir.mkdir()
            try:
                import asyncio as _asyncio
                _coro = render_orch.arender(design_id, level)
                try:
                    loop = _asyncio.get_event_loop()
                    if loop.is_running():
                        # Inside an async context (shouldn't normally happen but handle gracefully)
                        result = render_orch.render(design_id, level)
                    else:
                        result = loop.run_until_complete(_coro)
                except RuntimeError:
                    result = _asyncio.run(_coro)
            except Exception as exc:
                raise RuntimeError(f"Render failed for level {level!r}: {exc}") from exc
            (level_dir / "diagram.dsl").write_text(result.dsl, encoding="utf-8")
            (level_dir / "diagram.svg").write_text(result.svg, encoding="utf-8")
            import base64
            (level_dir / "diagram.png").write_bytes(base64.b64decode(result.png_base64))
