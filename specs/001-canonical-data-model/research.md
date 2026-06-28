# Research: Canonical Data Model & Schema Generation

**Branch**: `001-canonical-data-model` | **Date**: 2026-06-27  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: C4 Model Depth (OQ-02)

**Decision**: The `Element` entity supports three C4 levels in v1: Person, System, Container, Component. The code level (classes, functions, modules) is excluded from v1 scope.

**Rationale**: C4's first three levels are sufficient to describe the architectural concerns ADP governs. Code-level elements belong in source control and IDE tooling, not in an architecture description. Adding a fourth level in v1 would expand the model surface, require defining new identifier patterns, and complicate referential integrity rules — all before the model has been validated in practice. The `Element.kind` field is typed as a string enum; extending to code-level in a future minor version is backward-compatible.

**Alternatives considered**:
- Include code level in v1 — rejected: premature; no consuming spec requires it
- Reserve extension point now (open enum) — rejected: conflicts with ART-XIII (typed contracts everywhere); `extra="forbid"` ethos extends to enums

**Resolution of NEEDS CLARIFICATION in spec.md**: The Assumptions section marker `[NEEDS CLARIFICATION: C4 code level]` resolves to **stop at component**. `Element.kind` will be a closed enum: `{"person", "system", "container", "component"}`.

---

## Decision 2: JSON Schema Draft Version

**Decision**: Emit JSON Schema Draft 2020-12 (`$schema: "https://json-schema.org/draft/2020-12/schema"`).

**Rationale**: Pydantic v2's `model_json_schema()` produces Draft 2020-12 output by default. Using the library's native output avoids manual schema translation and ensures forward compatibility. Draft 2020-12 is the current stable draft and is widely supported.

**Alternatives considered**:
- Draft 7 — rejected: older, requires Pydantic schema customization, no significant benefit for this use case
- OpenAPI 3.1 Schema Object — rejected: a superset designed for API docs, not a standalone schema artifact; would add unnecessary coupling

---

## Decision 3: Identifier Validation Strategy

**Decision**: Use Pydantic `Annotated` types with `Field(pattern=...)` for ID validation. Pattern: `^[A-Z]+-\d{3}$` as the base regex, with entity-specific prefixes enforced by type aliases.

**Examples**:
- `RequirementId = Annotated[str, Field(pattern=r'^REQ-\d{3}$')]`
- `OptionId = Annotated[str, Field(pattern=r'^OPT-\d{3}$')]`
- `ElementId = Annotated[str, Field(pattern=r'^ELM-\d{3}$')]`
- `RelationshipId = Annotated[str, Field(pattern=r'^REL-\d{3}$')]`
- `FindingId = Annotated[str, Field(pattern=r'^FND-\d{3}$')]`
- `VerdictId = Annotated[str, Field(pattern=r'^VRD-\d{3}$')]`
- `AuditEntryId = Annotated[str, Field(pattern=r'^AUD-\d{3}$')]`

**Rationale**: Inline pattern validation is enforced at parse time without a separate registry. Three-digit zero-padded integers allow up to 999 entities per type in a single description — sufficient for realistic architecture descriptions.

**Alternatives considered**:
- UUID — rejected: not human-readable; breaks the traceability readability goal
- Arbitrary string with a prefix convention — rejected: cannot be enforced without explicit validation
- Four-digit IDs — deferred: can be a backward-compatible change if 999 proves insufficient

---

## Decision 4: Schema Generator Determinism Strategy

**Decision**: The generator serializes the Pydantic model to JSON Schema using `model.model_json_schema()`, then serializes to JSON with `json.dumps(..., sort_keys=True, indent=2)` and writes with a trailing newline. The `--check` mode reads the committed file, regenerates, and diffs; non-empty diff exits non-zero.

**Rationale**: `sort_keys=True` eliminates key-ordering non-determinism. Fixed 2-space indent and a trailing newline are standard and produce stable git diffs. Pydantic v2's schema generation is itself deterministic given identical model source.

**Alternatives considered**:
- Hash-based check (compare SHA256) — equally valid but less debuggable; text diff is more useful in CI output
- Streaming JSON — rejected: no benefit for schema files which are always small

---

## Decision 5: Referential Integrity Validation Approach

**Decision**: Implement referential integrity as a Pydantic v2 `@model_validator(mode='after')` on `ArchitectureDescription`. The validator builds index sets of all entity IDs, then checks every reference field (`satisfies`, `provenance`, relationship endpoints, finding targets, verdict subjects).

**Rationale**: Running integrity checks inside the model validator means that any load path (direct construction, JSON deserialization, or programmatic assembly) gets the same guarantees. No separate validation step can be forgotten.

**Alternatives considered**:
- Standalone `validate()` function — rejected: can be bypassed; breaks the "loading MUST fail" acceptance scenario
- Database foreign-key style (deferred check) — rejected: there is no database in this spec
- JSON Schema `$ref` cross-referencing — partial fit but JSON Schema cannot enforce referential integrity across instances; Pydantic validator is the right layer

---

## Decision 6: Package Layout

**Decision**: Use the `src`-layout (`src/adp/`) with a `pyproject.toml` defining the package and CLI entry point. Generated artifacts go in `generated/`; the canonical example goes in `fixtures/`.

**Rationale**: The `src`-layout prevents accidental imports of the package from the repo root without installation, which can mask import errors. Separating `generated/` from `src/` makes the generation target unambiguous and prevents accidental hand-edits.

**Alternatives considered**:
- Flat layout (`adp/` at root) — rejected: can mask import errors during development
- Placing generated artifacts in `src/adp/` — rejected: mixing source and generated files in the same directory contradicts ART-II (generated artifacts MUST NOT be edited)
