# Implementation Plan: Canonical Data Model & Schema Generation

**Branch**: `001-canonical-data-model` | **Date**: 2026-06-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-canonical-data-model/spec.md`

## Summary

Build the canonical Pydantic v2 data model for ADP architecture descriptions — eight typed entities (`Requirement`, `Element`, `Relationship`, `SolutionOption`, `Finding`, `Verdict`, `AuditEntry`, `ArchitectureDescription`) with strict unknown-field rejection, stable ID validation, and end-to-end traceability fields. A deterministic schema generator emits `architecture-description.schema.json` from the model and exposes a `--check` mode for CI drift detection. A canonical example fixture (`example-adp.json`) validates against the schema and serves as a permanent regression fixture (QG-05).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Pydantic v2 (entity definitions and schema emission), jsonschema 4.x (schema validation in tests)  
**Storage**: N/A — model artifacts are versioned files; persistence is out of scope (ADP-SPEC-002)  
**Testing**: pytest ≥ 7, pytest-cov; 85% line coverage threshold (ART-IV / QG-04)  
**Target Platform**: Python library within the ADP monorepo; consumed by all downstream specs  
**Project Type**: Python library + developer CLI tool  
**Performance Goals**: Schema generation completes deterministically in < 5 seconds from a clean checkout; no concurrent-user requirements  
**Constraints**: Byte-identical schema output on every run (NFR-001); no hand-editing of generated artifacts (ART-II / QG-18)  
**Scale/Scope**: Single-repo foundational dependency; all other ADP specs consume this model

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-001 |
| QG-02 | ART-II, ART-XIV | Schema regenerated from `models.py` equals committed file | ✅ FR-005 (`--check` mode) directly implements this gate |
| QG-03 | ART-III, ART-XIII, ART-XV | All artifacts validate against their published, versioned schemas | ✅ FR-004 (schema carries `$id`, `$schema`, version); FR-006 (example validates) |
| QG-04 | ART-IV | Tests present for all new behavior; ≥ 85% line coverage; non-regressing | ✅ Planned for every entity and generator code path |
| QG-05 | ART-IV, ART-XIII | Contract tests pass; `example-adp.json` validates against live schema | ✅ FR-006 is this gate's primary implementation |
| QG-06 | ART-V | Static analysis (SAST) clean | ✅ Pure model library; low risk; SAST configured in CI |
| QG-07 | ART-V | Dependency scan: no high/critical CVEs | ✅ Pydantic v2 and jsonschema are actively maintained |
| QG-08 | ART-V | Secret scan: no secrets in source, fixtures, generated files | ✅ No credentials required by this feature |
| QG-16 | ART-XI | Referential integrity holds; no orphan elements | ✅ FR-007 + User Story 4 (reference validation) implement this |
| QG-18 | ART-II, ART-XIV, ART-XV | Clean checkout regenerates with no diff; deps pinned | ✅ NFR-001 + FR-005 + locked dependency manifest |

**Post-Phase 0 re-check**: No violations anticipated; OQ-02 (C4 code level) resolved to component-level-only for v1 (see research.md).

**Constitution Alignment**: All sixteen articles reviewed. ART-VI (observability) and ART-VII (grounded AI) are **not in scope** for this spec — this feature produces no runtime service and no AI orchestration step. ART-XII (visual language) is also **not in scope** — no diagram rendering in this spec.

## Project Structure

### Documentation (this feature)

```text
specs/001-canonical-data-model/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — entity definitions and relationships
├── contracts/
│   └── schema-contract.md   # Phase 1 — published JSON Schema structure
├── quickstart.md        # Phase 1 — authoring a valid ArchitectureDescription
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py
    ├── models.py            # Pydantic v2 entity definitions (ART-II source of truth)
    ├── generate.py          # Schema generator CLI with --check mode (FR-004, FR-005)
    └── validate.py          # Reference integrity validator (FR-007)

tests/
├── unit/
│   ├── test_models.py                    # Entity validation, ID formats, extra-field rejection
│   ├── test_generate.py                  # Generator determinism, --check mode, drift detection
│   ├── test_validation.py                # Extra-field and ID-format rejection tests (US2)
│   └── test_referential_integrity.py     # Cross-entity reference validation tests (US4)
└── contract/
    └── test_schema.py       # Round-trip fidelity, example-adp.json validation (QG-05)

generated/
└── architecture-description.schema.json   # Generated from models.py — never hand-edited

fixtures/
└── example-adp.json         # Canonical example (FR-006, QG-05)

pyproject.toml               # Package definition, pinned dependencies, CLI entry point
```

**Structure Decision**: Single Python package (`src/adp/`) following the `src`-layout convention. The generator is a CLI entry point (`adp-generate`) defined in `pyproject.toml`. Generated artifacts live in `generated/` to make the generation target unambiguous. The canonical example lives in `fixtures/` alongside test data.
