# Research: Locked Visual Theme & Diagram Rendering

**Branch**: `010-locked-theme-rendering` | **Date**: 2026-07-01

---

## Decision 1: SVG/PNG Generation Strategy (no Java in WSL)

**Decision**: Generate SVG directly from Python (pure geometry over the model + theme) rather than through the Structurizr CLI; convert SVG → PNG using `cairosvg`.

**Rationale**: The Structurizr CLI is a Java binary — unavailable in the WSL environment (same constraint as Docker for the DB layer). Two options were evaluated:
- Option A: Generate SVG directly from Python, using the model data + theme. The C4 diagram geometry is simple (boxes, arrows, labels). No Java or external process needed. `cairosvg>=2.7` converts SVG → PNG in Python.
- Option B: Require the Java CLI at deploy time, skip image tests in CI (same pattern as DB integration tests). This makes local development impossible without Java.

Option A is chosen: the DSL string is generated for machine-readability (FR-003); the SVG is generated from the same model data that the DSL represents. The SVG layout algorithm is a simple row-grid auto-layout (not a force-directed graph). SC-002 (30 seconds) is easily met by pure-Python SVG generation (target: < 2 seconds for 50 elements).

**Alternatives considered**:
- `structurizr-cli` subprocess — requires Java, unavailable
- PlantUML — also Java-based
- Mermaid (Node.js) — available (Node.js v24 present), but generates markdown syntax not SVG directly without `@mermaid-js/mermaid-cli`; adds a second external dependency
- Pure Python SVG + `cairosvg` — **chosen** (zero external process, pure Python)

---

## Decision 2: Theme Schema Validation

**Decision**: Use `jsonschema>=4.10` (already in `pyproject.toml`) to validate `c4-theme.json` against `c4-theme.schema.json`. The schema is generated from a `ThemeDefinition` Pydantic v2 model (consistent with ART-II and QG-18).

**Rationale**: `jsonschema` is already a project dependency. Pydantic v2's `model_json_schema()` method generates a JSON Schema from the Python model, making `c4-theme.schema.json` a generated artifact (same pattern as `architecture-description.schema.json`). This keeps `adp-generate --check` as the single gate for schema drift (QG-18).

**Alternatives considered**:
- Pydantic-native validation only — would make `c4-theme.schema.json` redundant; the spec requires the schema as a published, versioned artifact (FR-004)
- Hand-authored JSON Schema — violates ART-II (generated artifacts MUST derive from model); rejected

---

## Decision 3: WCAG Contrast Ratio Check

**Decision**: Implement `compute_contrast_ratio(fg: str, bg: str) -> float` as a pure Python function using the WCAG 2.1 relative luminance formula. No external library.

**Rationale**: The formula is four lines: convert hex → sRGB, linearize, compute luminance, divide. Adding a library dependency (`wcag-contrast-ratio`, `colour-science`) is not justified for four lines of deterministic math. This function is also used as a **theme build-time check** (run during schema generation to assert SC-005 at theme publication time).

**Formula** (WCAG 2.1 relative luminance):
```
For each sRGB channel c:
  if c <= 0.04045: linear = c / 12.92
  else: linear = ((c + 0.055) / 1.055) ^ 2.4

L = 0.2126 * R_linear + 0.7152 * G_linear + 0.0722 * B_linear
contrast_ratio(L1, L2) = (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)
```

**Alternatives considered**:
- `wcag-contrast-ratio` PyPI package — only 150 LOC; would add a dep for trivial math; rejected
- Skip contrast check at validation time — violates SC-005 and ART-XII's intent; rejected

---

## Decision 4: Structurizr DSL Format

**Decision**: Generate valid Structurizr DSL using a Python string builder. The DSL is whitespace-significant indentation; the generator emits a `workspace` block with `model` and `views` sections. The C4 level parameter determines which elements are included in the `view`.

**Rationale**: The Structurizr DSL spec is public and stable. The grammar is straightforward enough to generate as formatted strings. No parsing is required — output only. The resulting DSL can be consumed by any Structurizr tooling if available, making it a genuine interoperability artifact.

**DSL structure for C4 container view** (example):
```
workspace "Design Title" {
    model {
        person "User" "A user of the system"
        softwareSystem "Web App" "The web application" {
            container "API Gateway" "Routes requests"
        }
    }
    views {
        container softwareSystem "Container View" {
            include *
            autolayout lr
        }
        styles {
            element "Person" {
                background #08427B
                color #ffffff
                shape Person
            }
        }
    }
}
```

**Alternatives considered**:
- `structurizr-python` PyPI package — last updated 2021, unmaintained; rejected in favor of direct string generation
- YAML/JSON Structurizr format — less human-readable; Structurizr DSL is the canonical text format

---

## Decision 5: Python SVG Generation Layout

**Decision**: Use a simple **auto-layout grid**: elements arranged left-to-right in rows of N columns (default: 4), with fixed cell size (200×120px per element). No force-directed physics. Relationships rendered as straight-line arrows between element center points.

**Rationale**: The spec requires consistent, deterministic layout (SC-006: byte-identical output for the same input). Force-directed layout is non-deterministic without seeding. A fixed grid layout:
- Is deterministic (given sorted element order)
- Is fast (< 1ms for 50 elements)
- Produces a readable auto-layout baseline until ADP-SPEC-009's user-positioned layout data is available
- Optionally accepts position hints from the layout API (ADP-SPEC-009) for precise placement

**Alternatives considered**:
- `graphviz` (Python bindings) — adds a C library dependency and requires `graphviz` system package; non-deterministic without seed; rejected
- `networkx` + spring layout — non-deterministic; rejected
- Fixed grid — **chosen** (deterministic, no deps, fast)

---

## Decision 6: cairosvg for PNG Conversion

**Decision**: `cairosvg>=2.7` (Python library, pip-installable, no Java) for SVG → PNG conversion.

**Rationale**: `cairosvg` is a pure-Python bridge to libcairo (a C library) that converts SVG to PNG, PDF, or PS. It handles basic SVG geometry (rects, lines, text) correctly. The libcairo C library is typically pre-installed on Linux/WSL.

**Alternatives considered**:
- `Pillow` — cannot render SVG; would require intermediate rasterization step; rejected
- `svglib` + `reportlab` — heavier stack; `reportlab` adds license considerations; rejected
- Inkscape subprocess — requires Inkscape installation; rejected
- `cairosvg` — **chosen** (pip-installable, no Java, straightforward SVG→PNG)

---

## Decision 7: Render API Location

**Decision**: Add `POST /api/v1/designs/{design_id}/render` as a new route in `src/adp/api/routers/render.py`; register in `src/adp/api/app.py`.

**Rationale**: Follows the established router pattern from ADP-SPEC-003 (layouts.py, theme.py). A POST is appropriate because rendering is a computational operation (not idempotent read) — it consumes resources and returns a response body rather than a persistable resource.

**Response format**: DSL as a plain string field; SVG as a string; PNG as base64-encoded string — all in a single JSON response body. This avoids multi-part responses for v1.

---

## Summary of New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `cairosvg` | `>=2.7` | SVG → PNG conversion (no Java required) |

All other requirements use existing `jsonschema`, `pydantic`, and `fastapi` deps already pinned in `pyproject.toml`. No new dev dependencies needed (testing uses existing `pytest`).
