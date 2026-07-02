# Implementation Plan: Locked Visual Theme & Diagram Rendering

**Branch**: `010-locked-theme-rendering` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-locked-theme-rendering/spec.md`

## Summary

Build the locked visual theme system and diagram renderer for ADP. The theme (`c4-theme.json`) is a versioned, schema-validated JSON artifact that maps every C4 element type to a fixed fill/stroke/text color and shape. The renderer converts a canonical `ArchitectureDescription` into three outputs: Structurizr DSL source, an SVG image, and a PNG image — all styled exclusively by the locked theme. No per-element or per-diagram overrides are accepted. Rendering is exposed via `POST /api/v1/designs/{id}/render` and returns all three outputs in a single JSON response.

SVG is generated directly from Python (deterministic grid auto-layout); PNG is produced via `cairosvg` (no Java required). The theme schema is generated from a `LockedTheme` Pydantic v2 model and committed to the repository; CI verifies no drift (QG-18).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `cairosvg>=2.7` (SVG→PNG; new); `jsonschema>=4.10` (theme schema validation; already in project); `pydantic>=2.0` (typed models; already in project); `fastapi>=0.111` (render router; already in project)  
**Storage**: `src/adp/theme/c4-theme.json` (static authored artifact, git-versioned); `src/adp/theme/c4-theme.schema.json` (generated from `LockedTheme` Pydantic model via `adp-generate`)  
**Testing**: `pytest>=9.0` (existing); `pytest-asyncio` (existing); no Docker required  
**Target Platform**: Linux/WSL (WSL2 environment; no Java, no Docker); `libcairo` available via system package manager for `cairosvg`  
**Project Type**: Python library extension (new modules `adp.theme`, `adp.renderer`) + FastAPI router extension  
**Performance Goals**: Render ≤ 30s for 50 elements (SC-002); theme validation ≤ 2s (SC-003); target actual: < 2s render (pure Python SVG; no process spawning)  
**Constraints**: No style override inputs accepted (FR-002); deterministic output (SC-006); `adp-generate --check` must remain green (QG-18)  
**Scale/Scope**: Single-process in-memory rendering; v1 does not cache render results; on-demand only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references ADP-SPEC-010 task IDs | ✅ Will be enforced |
| QG-02 | ART-II, ART-XIV | `c4-theme.schema.json` regenerated from `LockedTheme` Pydantic model; drift test via `adp-generate --check` | ✅ Planned |
| QG-03 | ART-III, ART-XIII | Theme validates against published schema; `RenderRequest` uses Pydantic `extra="forbid"` | ✅ FR-004; typed models planned |
| QG-04 | ART-IV | Tests written before implementation; coverage ≥ 85% | ✅ TDD planned |
| QG-05 | ART-IV, ART-XIII | Contract tests for render API endpoint | ✅ Planned in `tests/contract/` |
| QG-06 | ART-V | `ruff check` clean | ✅ No new SAST surface |
| QG-07 | ART-V | `cairosvg` (new dep) has no known high/critical CVEs | ✅ Verify at `pip-audit` time |
| QG-08 | ART-V | No secrets in source, fixtures, or generated files | ✅ Rendering is read-only |
| QG-09 | ART-V, ART-VIII | Rendering is non-consequential (read-only); no confirmation gate needed | ✅ N/A for this feature |
| QG-10 | ART-VI | Render endpoint emits structured log with correlation ID and design_id | ✅ Planned |
| QG-11 | ART-VI | No AI orchestration steps — no spans required | ✅ N/A |
| QG-12 | ART-VII | No LLM component — no grounding requirement | ✅ N/A |
| QG-13 | ART-VIII, ART-IX | Rendering does NOT mutate the canonical model — no audit entry needed | ✅ N/A |
| QG-14 | ART-VIII | Rendering is a read-only operation — no confirmation gate | ✅ N/A |
| QG-15 | ART-X | No validation gating in this feature | ✅ N/A |
| QG-16 | ART-XI | Renderer reads existing model — does not introduce orphan elements | ✅ N/A |
| QG-17 | ART-XII | **This feature IS QG-17**: creates `c4-theme.json` and `c4-theme.schema.json`; renderer enforces locked theme | ✅ Core deliverable |
| QG-18 | ART-II, ART-XIV, ART-XV | `c4-theme.schema.json` is generated; `adp-generate --check` covers it; `c4-theme.json` is authored (not generated) but schema-validated at test time | ✅ Planned |

**Constitution Alignment**: ART-XII is the central article. The `LockedTheme.locked: Literal[True]` field makes it impossible at the Python type level to load a theme that isn't locked. `RenderRequest.extra="forbid"` makes it impossible at the API level to submit style overrides. Both enforce ART-XII in code, not just in tests.

## Project Structure

### Documentation (this feature)

```text
specs/010-locked-theme-rendering/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── render-api-contract.md       # POST /api/v1/designs/{id}/render
│   └── theme-artifact-contract.md   # c4-theme.json shape
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/adp/theme/
├── __init__.py
├── c4-theme.json          # Locked theme artifact (authored, versioned in git)
├── c4-theme.schema.json   # JSON Schema (generated from LockedTheme Pydantic model)
├── loader.py              # ThemeLoader: load() + validate() + load_and_validate()
├── contrast.py            # compute_contrast_ratio(fg, bg) → float; pure WCAG 2.1 math
└── models.py              # LockedTheme, ElementStyle, RelationshipStyle Pydantic models

src/adp/renderer/
├── __init__.py
├── dsl.py                 # design_to_dsl(design, level) → str (Structurizr DSL string)
├── svg.py                 # design_to_svg(design, theme, level, positions?) → str (SVG XML)
├── png.py                 # svg_to_png(svg_str) → bytes (via cairosvg)
└── orchestrator.py        # RenderOrchestrator: render(design_id, level) → RenderResult

src/adp/api/routers/
└── render.py              # POST /api/v1/designs/{design_id}/render

tests/
├── contract/
│   └── test_render_api.py          # Contract tests for render endpoint
├── unit/
│   ├── test_theme_loader.py        # ThemeLoader unit tests
│   ├── test_theme_contrast.py      # WCAG contrast ratio tests (including SC-005)
│   ├── test_dsl_generator.py       # DSL string generation tests
│   └── test_svg_generator.py       # SVG output tests (colors, structure)
└── integration/
    └── test_render_e2e.py          # End-to-end render test (no Docker; in-process)
```

**Structure Decision**: Two new Python packages (`adp.theme` and `adp.renderer`) plus one new FastAPI router. No new projects, no separate services. All existing test infrastructure reused.

## New Dependencies

| Package | Version | Purpose | Added to |
|---------|---------|---------|----------|
| `cairosvg` | `>=2.7` | SVG → PNG conversion | `pyproject.toml` dependencies |

`libcairo` must be installed on the system (`apt install libcairo2` on Debian/WSL). All other dependencies (`jsonschema`, `pydantic`, `fastapi`) are already pinned in `pyproject.toml`.
