# Contract: Published JSON Schema

**Artifact**: `generated/architecture-description.schema.json`  
**Generated from**: `src/adp/models.py` via `src/adp/generate.py`  
**Consumer**: Every downstream ADP spec and any external tool that validates architecture descriptions  
**Date**: 2026-06-27

---

## Contract Identity

The published schema MUST carry the following top-level fields:

| Field | Value / Pattern | Notes |
|---|---|---|
| `$schema` | `"https://json-schema.org/draft/2020-12/schema"` | JSON Schema Draft 2020-12 |
| `$id` | `"https://adp.example.org/schemas/architecture-description.schema.json"` | Canonical URI; update to actual domain on deployment |
| `title` | `"Architecture Description"` | Human-readable schema title |
| `schema_version` | `"1.0.0"` (semver) | Embedded version — ART-XV |
| `type` | `"object"` | Root type is the `ArchitectureDescription` aggregate |

---

## Versioning Rules (ART-XV)

| Change Type | Version Bump | Additional Requirements |
|---|---|---|
| New optional field added | Minor (`1.x.0`) | Existing artifacts remain valid |
| Field renamed or removed | Major (`2.0.0`) | Migration script + ADR required |
| New required field added | Major (`2.0.0`) | Migration script + ADR required |
| Enum value added | Minor (`1.x.0`) | Old enum values remain valid |
| Enum value removed | Major (`2.0.0`) | Migration script + ADR required |
| Clarification / description fix | Patch (`1.0.x`) | No behavior change |

Every conforming `ArchitectureDescription` artifact MUST embed the `schema_version` it was authored against. Validators MUST reject artifacts missing `schema_version`.

---

## Generator Contract

The generator (`src/adp/generate.py`) provides the following guarantees:

1. **Sole writer**: No other process or human may write `architecture-description.schema.json`. Attempts to commit hand-edited versions are blocked by QG-02 / QG-18.

2. **Deterministic output**: Given identical `models.py`, every run produces byte-identical JSON. Keys are sorted; indentation is 2 spaces; file ends with a single newline.

3. **Check mode**: `adp-generate --check` reads the committed schema, regenerates in memory, diffs, and exits non-zero with a human-readable drift report if any difference is found. Used by QG-02 in CI.

4. **Version embedding**: The generator writes `schema_version` into the emitted schema from the model's declared version constant.

---

## Validation Contract

Consumers of `architecture-description.schema.json` MUST:

- Validate loaded artifacts against the schema before use
- Reject artifacts whose `schema_version` does not match the current schema's version (or apply a registered migration)
- Treat schema validation errors as fatal, not warnings

The canonical example (`fixtures/example-adp.json`) is the reference implementation of a conforming artifact and serves as the primary contract test (QG-05).

---

## Referential Integrity

The JSON Schema alone cannot enforce cross-instance referential integrity. Referential integrity (that every ID referenced in `satisfies`, `source`, `target`, `subject`, `option_id` resolves to an existing entity within the same description) is enforced by the Pydantic model validator at load time. Downstream consumers using only the JSON Schema for validation MUST be aware that schema-valid artifacts may still fail referential integrity checks when loaded through the Python model.
