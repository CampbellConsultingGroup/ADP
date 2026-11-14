# Implementation Plan: EA Pattern Metamodel & YAML Format (PATTERN-01)

**Branch**: `934-pattern-metamodel` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/934-pattern-metamodel/spec.md` (bead ADP-mmm.1, epic ADP-mmm; source `docs/PATTERN-01-metamodel-and-yaml.md` plus the `docs/PATTERN-00` addendum)

## Summary

This feature adds a new pure-library package, `adp.patterns`, containing:
- **A typed definition model.** A frozen Pydantic v2 `PatternDefinition` with roles, relationships, constraints, motivation, transition and relations.
- **A hardened YAML parser.** It rejects aliases and anchors, files over 256 KB and multi-document files, and accepts cardinality shorthand.
- **Cross-field validation.** Rules V1–V9 are checked, and every problem is reported as an issue rather than an exception.
- **CEL compile checks.** Run through Google's `cel-expr-python`, chosen by the spike in research.md D1, behind a replaceable `CelEngine` adapter.
- **Canonical forms.** Canonical JSON, a SHA-256 digest and canonical YAML, with a tested round-trip law.
- **A JSON Schema.** Generated through the existing `adp-generate` drift gate.

There is no database, no API and no UI. Spec 935 adds the first surface.

## Technical Context

**Language/Version**: Python 3.12 runtime, 3.11+ compatible.
**Primary Dependencies**: Pydantic v2 and `pyyaml>=6.0` (both existing). **One new runtime dependency:** `cel-expr-python==0.1.4`, pinned exactly (research D1). It ships cp311/cp312 manylinux_2_28 wheels and has no transitive dependencies.
**Storage**: N/A.
**Testing**: pytest unit tests in `tests/unit/patterns/`, driven by fixture YAML files, plus the `adp-generate --check` drift gate.
**Target Platform**: Linux server (WSL dev, ubuntu CI, `python:3.12-slim` image).
**Project Type**: library inside the existing `src/adp` backend.
**Performance Goals**: validating the reference fixture, including CEL compilation, takes under 100 ms (SC-004).
**Constraints**:
- No imports from other `adp.*` domain packages.
- `models.py` must not import the CEL engine, so schema generation stays engine-free.
- No function in `parse_pattern_yaml`/`validate_pattern` may let an exception escape (FR-012).
**Scale/Scope**: about 5 modules (around 900 lines), about 25 fixture files, and about 60 tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| ART-I Spec-driven / QG-01 | ✔ | spec.md, plus beads ADP-mmm.1 under epic ADP-mmm |
| ART-II Single source of truth | ✔ | One `PatternDefinition`; 935–937 consume it, never re-parse it |
| ART-III Machine-readable / QG-03 | ✔ | YAML in; canonical JSON and YAML out; published JSON Schema |
| ART-IV TDD / QG-04 (coverage ≥ 85%) | ✔ | Fixtures and failing tests are written before validators (tasks order); pure code makes high coverage easy |
| ART-V Security / QG-06, QG-07 | ✔ | Threat model in spec. Alias-bomb and size guards. Safe loader only. The new dependency goes through `pip-audit`, and bandit stays clean |
| ART-VII Grounded AI | n/a | No AI |
| ART-X Deterministic validation | ✔ | Pure, deterministic; digest stability is tested |
| ART-XIII Typed contracts | ✔ | Closed enums for every vocabulary; `extra="forbid"` everywhere |
| ART-XIV Drift-free builds / QG-02, QG-18 | ✔ | `generated/pattern.schema.json` is added to `adp-generate` and `--check`. The new dependency is pinned exactly |
| ART-XV Schema evolution | n/a | No database change |

No violations, so the Complexity Tracking section is empty. Re-checked after design: unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/934-pattern-metamodel/
├── plan.md
├── research.md          # D1 CEL spike evidence … D9 fixture selectors
├── data-model.md        # PatternDefinition and sub-models, enums, issue codes
├── quickstart.md
├── contracts/
│   └── python-api.md    # Public functions of adp.patterns (the contract 935–937 build on)
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
src/adp/patterns/
├── __init__.py          # Re-exports the public API (contracts/python-api.md)
├── models.py            # Enums, constrained string types, Cardinality, Role, RoleRelationship,
│                        #   RenderHint, Constraint, Motivation, Plateau, Transition, PatternRelation,
│                        #   PatternDefinition (+ V1–V6, V8, V9 collected in one after-validator), PatternIssue
├── cardinality.py       # Shorthand grammar: parse_cardinality() / format_cardinality()
├── cel.py               # CelEngine Protocol, CelError, GoogleCelEngine adapter, PATTERN_CEL_ENV declaration
└── parse.py             # SafeNoAliasLoader, parse_pattern_yaml(), validate_pattern() (adds V7),
                         #   to_canonical_json(), compute_digest(), to_canonical_yaml()
src/adp/generate.py      # + generate_pattern_schema(), wired into main() and check()
generated/pattern.schema.json   # generated, committed
pyproject.toml           # + "cel-expr-python==0.1.4"

tests/unit/patterns/
├── __init__.py
├── conftest.py          # fixture loader helpers
├── fixtures/valid/      # domain-event-backbone, point-to-point-mesh (anti-pattern),
│                        #   mesh-to-backbone (transition), one-sor-per-capability (portfolio-rule), longhand variant
├── fixtures/invalid/    # one file per code: V1…V9 (+ sub-codes), P1…P5, schema.extra_forbidden (lifecycle)
├── test_cardinality.py
├── test_models.py       # V1–V9 against invalid fixtures; valid fixtures produce zero errors
├── test_cel.py          # adapter contract: compile ok/err+position, undeclared, not_bool vs DYN, role()/bound() eval, missing key, budget
├── test_parse.py        # P1–P5, never-raises fuzz (random bytes / truncated docs), multi-issue aggregation
├── test_canonical.py    # round-trip law, digest equalities/inequalities (key order, longhand, role order)
└── test_schema.py       # generated schema validates the valid fixtures; generate_pattern_schema deterministic
tests/unit/test_generate.py  # extend (if present) so check() covers the pattern schema
```

**Structure Decision**:
- A new sibling package under the existing backend. Nothing else is named `patterns`.
- `adp.knowledge` keeps the prose patterns; 935 adds the projection bridge.
- Tests follow ADP's `tests/unit/<pkg>/` convention (research D8).

## Key design points (details in research.md / data-model.md)

1. **Two-stage validation.**
   - `parse_pattern_yaml(text)` = YAML guards → Pydantic model, with V1–V6, V8 and V9 collected into issues.
   - `validate_pattern(defn, engine)` adds V7, the CEL compile step.
   - `parse_pattern_yaml(text, engine=default_engine())` runs both stages and returns `ParseResult(definition, issues)`.
   - The definition is `None` only when a structural error makes the model unconstructable. V7 failures still return the definition, so 935 can show the draft.
2. **Collected model issues.**
   - The after-validator gathers every V-rule failure and raises one `PydanticCustomError` whose context carries the list.
   - `parse.py` turns that into individual `PatternIssue`s, so all problems surface together (US1-5).
3. **CEL environment** (`PATTERN_CEL_ENV`):
   - variables `it: dyn`, `bindings: map<string, list<dyn>>`, `scope: map<string, list<dyn>>`;
   - functions `role(string) → list<string>` and `bound(map<string,dyn>, string) → bool`.
   - The compile-time implementations are stubs. 936 supplies real implementations per evaluation through the adapter's `evaluate(program, activation, functions)`.
   - V7.not_bool fires only for a definite non-bool return type; `DYN` passes.
4. **Digest.** The canonical JSON encodes `roles` as an ordered list of `[key, role]` pairs, so `sort_keys` cannot erase the declared role order (research D5).

## Complexity Tracking

None.
