# Implementation Plan: Document, View & Export Generation

**Branch**: `011-document-export` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-document-export/spec.md`

## Summary

Build the document generation, traceability matrix, and durable export pipeline for ADP. Every human-readable artifact (stakeholder Markdown doc, traceability matrix, per-persona C4 views) is generated from the canonical model. Export to version control is a consequential action requiring explicit human confirmation (ART-VIII) and writes an audit entry (ART-IX). The export bundle contains the canonical model as JSON + YAML, Structurizr DSL + SVG + PNG for all three C4 levels, and the stakeholder document. Round-trip import re-validates an exported `model.json` against the current schema.

**Key architectural principle**: ART-II — the canonical model is the source; documents are projections. Nothing in this feature authors primary content; it only reads the model and writes derived artifacts.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pyyaml>=6.0` (new, for `model.yaml` export); `python-frontmatter>=1.1` (already in project, for Markdown frontmatter); `pydantic>=2.0` (existing); `fastapi>=0.111` (existing); `cairosvg` (via ADP-SPEC-010 renderer, already installed)
**Storage**: Export bundles written to filesystem (configured `export_root` path); no new database tables; existing audit store (`adp.store`) records export audit entries
**Testing**: `pytest` (existing); no Docker required; export tests use `tmp_path` fixtures for filesystem writes
**Target Platform**: Linux/WSL (same as existing stack)
**Project Type**: Python library extension (new packages `adp.docs`, `adp.export`) + two new FastAPI routers
**Performance Goals**: Document generation ≤ 60s for 50-element design (SC-001); full export bundle ≤ 120s (SC-004)
**Constraints**: No partial exports (atomicity via temp-then-rename); confirmation required for export (ART-VIII); generated docs byte-identical for same model version (ART-XIV)
**Scale/Scope**: v1 export to local filesystem (no direct git push); v1 import of current schema version only (no migration framework)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references ADP-SPEC-011 task IDs | ✅ Will be enforced |
| QG-03 | ART-III, ART-XIII | Exported model.json validates against architecture-description schema; all typed Pydantic models; all exported artifacts schema-valid before writing | ✅ FR-006 |
| QG-04 | ART-IV | Tests written before implementation; ≥ 85% coverage | ✅ TDD planned |
| QG-05 | ART-IV, ART-XIII | Contract tests for document, views, export, and import endpoints | ✅ Planned in `tests/contract/` |
| QG-06 | ART-V | `ruff check` clean; no new SAST surface | ✅ Read-only generation + controlled file write |
| QG-08 | ART-V | No secrets in generated documents or exports | ✅ Design IP but no auth tokens/credentials in output |
| QG-09 | ART-V, ART-VIII | Export is consequential; confirmation_id required | ✅ FR-005, ART-VIII pattern |
| QG-10 | ART-VI | Export endpoint emits structured log with correlation_id, design_id, export_path | ✅ Planned |
| QG-13 | ART-VIII, ART-IX | Export records audit entry: actor, design_id, version, export_path, timestamp | ✅ FR-005, ART-IX |
| QG-14 | ART-VIII | Per-export human confirmation via confirmation_id; no blanket approval | ✅ FR-005 |
| QG-18 | ART-II, ART-XIV | Generated documents deterministic; adp-generate --check unaffected (no new generated schemas) | ✅ No new schema artifacts |

**Constitution Alignment**: ART-II is dominant — every generated artifact is a projection. ART-VIII enforced at API level via `confirmation_id`. ART-XIV enforced by deterministic string builders (no template engines, no random IDs in generated content).

**N/A gates**: QG-11, QG-12, QG-15, QG-16 — no AI orchestration, no LLM, no validation gating, no new model elements introduced.

## Project Structure

### Documentation (this feature)

```text
specs/011-document-export/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── document-api-contract.md   # GET /document, /traceability, /views
│   └── export-api-contract.md     # POST /export, /import
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code

```text
src/adp/docs/
├── __init__.py
├── models.py           # DocumentMetadata, GeneratedDocument, TraceabilityEntry, TraceabilityMatrix, ViewBundle, ExportRequest, ExportResult, ImportRequest, ImportResult
├── generator.py        # DocumentGenerator.generate(design) → GeneratedDocument
└── traceability.py     # TraceabilityGenerator.generate(design) → TraceabilityMatrix

src/adp/export/
├── __init__.py
├── bundle.py           # ExportOrchestrator.export(...) → ExportResult; atomic temp-then-rename
└── importer.py         # DesignImporter.import_from_json(json_str) → ArchitectureDescription

src/adp/api/routers/
├── documents.py        # GET /api/v1/designs/{id}/document, /traceability, /views
└── export_router.py    # POST /api/v1/designs/{id}/export, POST /api/v1/designs/import

tests/
├── contract/
│   ├── test_document_api.py      # Contract tests for GET document/traceability/views
│   └── test_export_api.py        # Contract tests for POST export + import
├── unit/
│   ├── test_document_generator.py  # DocumentGenerator unit tests
│   ├── test_traceability.py        # TraceabilityGenerator unit tests
│   └── test_importer.py            # DesignImporter unit tests
└── integration/
    └── test_export_bundle.py       # End-to-end export bundle (tmp_path; no Docker)
```

**Structure Decision**: Two new Python packages in the existing monorepo. No new projects or services. Follows the same pattern as `adp.theme` (ADP-SPEC-010): thin domain packages with FastAPI routers wired into existing `create_app()` in `src/adp/api/app.py`.

## New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `pyyaml` | `>=6.0` | YAML serialization for `model.yaml` in export bundle | `pyproject.toml` dependencies |

Note: `python-frontmatter` (already in project) transitively depends on PyYAML. Explicit `pyyaml` pin makes the dependency visible and version-controlled.
