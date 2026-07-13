# Data Model: Document, View & Export Generation

**Branch**: `011-document-export` | **Date**: 2026-07-02
**Sources**: `spec.md`, `research.md`

---

## Python Entities (Pydantic v2, `extra="forbid"`)

### `DocumentMetadata`

Typed frontmatter carried in every generated Markdown document. Written as the YAML `---` block at the top of the file.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | The design this document was generated from |
| `schema_version` | `str` | `ArchitectureDescription.schema_version` at generation time |
| `generated_at` | `str` | ISO 8601 UTC timestamp of generation |
| `generator` | `str` | Constant `"ADP-SPEC-011"` |
| `level` | `C4Level \| None` | C4 level if this is a view-specific document; `None` for full stakeholder docs |

### `GeneratedDocument`

Return value from `DocumentGenerator.generate()`.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Source design |
| `markdown` | `str` | Complete Markdown string including YAML frontmatter |
| `metadata` | `DocumentMetadata` | Structured copy of the frontmatter (parsed back for programmatic access) |

### `TraceabilityEntry`

One row in the traceability matrix — one element and its full thread.

| Field | Type | Notes |
|---|---|---|
| `element_id` | `str` | Element ID (e.g., `ELM-001`) |
| `element_name` | `str` | Human-readable name |
| `element_kind` | `str` | ElementKind enum value |
| `satisfied_requirements` | `list[str]` | Requirement IDs this element satisfies (may be empty for orphans) |
| `provenance` | `str \| None` | Recommendation/option ID if AI-derived; `None` if manually placed |
| `verdict_ids` | `list[str]` | Verdict IDs that evaluated a design version containing this element |
| `is_orphan` | `bool` | `True` if `satisfied_requirements` is empty |

### `TraceabilityMatrix`

Root entity for the machine-readable traceability artifact.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Source design |
| `schema_version` | `str` | Schema version at generation time |
| `generated_at` | `str` | ISO 8601 UTC |
| `entries` | `list[TraceabilityEntry]` | One entry per element; sorted by element ID for determinism |
| `orphan_count` | `int` | Count of elements with empty `satisfied_requirements` |
| `total_elements` | `int` | Total element count |

### `ViewBundle`

All three C4 level renders for one design in one response.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Source design |
| `context` | `RenderResult` | Context-level DSL + SVG + PNG (from ADP-SPEC-010) |
| `container` | `RenderResult` | Container-level DSL + SVG + PNG |
| `component` | `RenderResult` | Component-level DSL + SVG + PNG |

### `ExportRequest`

Request body for `POST /api/v1/designs/{id}/export`. Carries the confirmation ID (ART-VIII).

| Field | Type | Notes |
|---|---|---|
| `confirmation_id` | `str` | Required; obtained from the confirmation flow (ART-VIII / QG-14) |
| `export_root` | `str` | Absolute path to the configured VCS repository root |

### `ExportResult`

Return value after a successful export.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | Exported design |
| `model_version` | `int` | Design model version that was exported |
| `export_path` | `str` | Absolute path of the created export bundle directory |
| `artifacts` | `list[str]` | Relative paths of all written files (relative to `export_path`) |
| `audit_entry_id` | `str` | ID of the audit entry recording this export |

### `ImportRequest`

Request body for `POST /api/v1/designs/import`.

| Field | Type | Notes |
|---|---|---|
| `model_json` | `str` | Raw JSON string of the canonical model to import |

### `ImportResult`

Return value after a successful import.

| Field | Type | Notes |
|---|---|---|
| `design_id` | `str` | ID of the reconstructed design |
| `schema_version` | `str` | Schema version of the imported model |
| `element_count` | `int` | Number of elements in the reconstructed model |
| `relationship_count` | `int` | Number of relationships |
| `validation_warnings` | `list[str]` | Non-fatal warnings (e.g., deprecated fields); empty if clean |

---

## Export Bundle Directory Structure

```
{export_root}/
└── exports/
    └── {design_id}/
        └── v{model_version}/
            ├── model.json          # Canonical ArchitectureDescription (sorted keys, schema-valid)
            ├── model.yaml          # Same model as YAML (stable sort for diffability)
            ├── traceability.json   # TraceabilityMatrix (machine-readable)
            ├── README.md           # Stakeholder document (Markdown + YAML frontmatter)
            ├── context/
            │   ├── diagram.dsl     # Structurizr DSL for context level
            │   ├── diagram.svg     # SVG render of context level
            │   └── diagram.png     # PNG render of context level
            ├── container/
            │   ├── diagram.dsl
            │   ├── diagram.svg
            │   └── diagram.png
            └── component/
                ├── diagram.dsl
                ├── diagram.svg
                └── diagram.png
```

**Invariant**: This directory path never exists before export (design ID + version is unique); existing directories at this path cause the export to abort with an error.

---

## Generated Document Structure

```markdown
---
design_id: DESIGN-001
schema_version: "1.0.0"
generated_at: "2026-07-02T12:34:56Z"
generator: ADP-SPEC-011
level: null
---

# {design.title}

**Design ID**: DESIGN-001
**Model Version**: 3
**Generated**: 2026-07-02T12:34:56Z

## Summary

{design description or first paragraph derived from elements}

## Elements

### ELM-001 — API Gateway (container)

{element.description}

**Satisfies**: REQ-001 (Stateless handling), REQ-003 (Auth at gateway)
**Provenance**: Accepted from recommendation OPT-001

...

## Requirements

| ID | Title | Satisfied By |
|---|---|---|
| REQ-001 | Stateless handling | ELM-001 |

## Traceability Summary

{Markdown rendering of the traceability matrix}
```

---

## Relationships to Existing Entities

| New Concept | Source Entity (ADP-SPEC-001) | Notes |
|---|---|---|
| `TraceabilityEntry.element_id` | `Element.id` | Direct reference |
| `TraceabilityEntry.satisfied_requirements` | `Element.satisfies` | List of Requirement IDs |
| `TraceabilityEntry.provenance` | `Element.provenance` | Option/recommendation ID |
| `ExportResult.audit_entry_id` | `AuditEntry.id` | Recorded via ADP-SPEC-004 writer |
| `DocumentMetadata.schema_version` | `ArchitectureDescription.schema_version` | Copied at generation time |
| `ViewBundle.context/container/component` | `RenderResult` (ADP-SPEC-010) | Consumed from ADP-SPEC-010 renderer |
