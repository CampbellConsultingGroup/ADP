# Tasks: EA Pattern Metamodel & YAML Format (PATTERN-01)

**Input**: Design documents from `/specs/934-pattern-metamodel/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓ (D1 spike done), data-model.md ✓, contracts/python-api.md ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). In every phase, test tasks come before their implementation and must be seen to fail first.

**Organization**:
- **US1**: author and validate with precise issues (P1, the MVP).
- **US2**: canonical form and digest (P2).
- **US3**: published JSON Schema (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

---

## Phase 1: Setup

- [x] T001 Add `"cel-expr-python==0.1.4"` to `pyproject.toml` dependencies, then `pip install -e ".[dev]"`. Confirm that `pip-audit` reports no high or critical issues for it.
- [x] T002 [P] Create the package skeleton: `src/adp/patterns/__init__.py` (empty for now), `tests/unit/patterns/__init__.py`, and `tests/unit/patterns/conftest.py` (a `load_fixture(name)` helper over `fixtures/valid` and `fixtures/invalid`).

## Phase 2: Foundational (blocks all stories)

- [x] T003 [P] Write `tests/unit/patterns/test_cardinality.py`. Table-driven valid forms: `"1"`, `"0..1"`, `"2..*"`, `"1 per capability"`, `"1..3 per x"`, and the longhand mapping. Invalid forms: `"*..1"`, `"1 per"`, `"0"`, `"3..2"`, `"-1"`, `"a"`. Also check that `format_cardinality` round-trips.
- [x] T004 Implement `src/adp/patterns/cardinality.py` (`parse_cardinality`, `format_cardinality`) and make T003 pass.
- [x] T005 [P] Write `tests/unit/patterns/test_cel.py`, the adapter contract (contracts/python-api.md):
  - `compile_check` returns `[]` for the research-D9 expressions;
  - a syntax error yields a `CelError` with code `compile` and a column;
  - an undeclared variable is rejected;
  - `'abc'` yields `not_bool`, while `it.name` (DYN) passes;
  - `evaluate` with `role`/`bound` implementations returns the expected booleans;
  - a missing map key returns `CelResult(error="missing_key")`;
  - a 200×200 nested comprehension returns `budget_exceeded`;
  - no method raises.
- [x] T006 Implement `src/adp/patterns/cel.py`:
  - `CelError`, `CelResult`, the `CelEngine` Protocol and `PATTERN_CEL_VARIABLES`;
  - `GoogleCelEngine`: a `NewEnv` with typed `FunctionDecl`s, where `bound` takes `map<string,dyn>`. Map `ERROR` values and `RuntimeError`s to `CelResult` error kinds by message prefix (`NOT_FOUND` → `missing_key`, `Iteration budget exceeded` → `budget_exceeded`, `No matching overloads` → `type_error`). Parse `<input>:L:C` positions;
  - `default_engine()` as a cached singleton.

  Make T005 pass.

## Phase 3: User Story 1 — Author and validate with precise issues (P1) 🎯 MVP

**Goal**: `parse_pattern_yaml` returns a typed definition or every issue, with path and code, and never raises.
**Independent test**: valid fixtures produce zero errors; each invalid fixture produces exactly its code and path.

- [x] T007 [P] [US1] Write the valid fixtures in `tests/unit/patterns/fixtures/valid/`:
  - `ea.integration.domain-event-backbone@1.0.0.yaml`, using research-D9 selectors only;
  - `ea.integration.point-to-point-mesh@1.0.0.yaml` (anti-pattern, all constraints `detect`);
  - `ea.integration.mesh-to-backbone@1.0.0.yaml` (transition, strangler, PL1 ⊂ PL2 cumulative);
  - `ea.data.one-sor-per-capability@1.0.0.yaml` (portfolio-rule, with a `"1 per capability"` cardinality linked by `serves`).
- [x] T008 [P] [US1] Write the invalid fixtures in `tests/unit/patterns/fixtures/invalid/`. Name each file after its expected code, with the expected path in a leading comment:
  - `V1.reserved_role`
  - `V2.unknown_role` (relationship target, `for_each`, `per`, `render_hint`)
  - `V3.duplicate_id`
  - `V4.transition_required`, `V4.transition_forbidden`, `V4.unknown_criterion`, `V4.not_cumulative`
  - `V5.per_unlinked`
  - `V6.polarity`, `V6.antipattern_transition`, `V6.antipattern_replaces`
  - `V7.compile`, `V7.not_bool`
  - `V8.self_relation`, `V8.duplicate_relation`
  - `V9.owner_role`
  - `schema.extra_forbidden` (a top-level `lifecycle: current`)
  - `P2.alias`, `P3.multi_document`, `P4.not_mapping`, `P5.yaml_syntax`
- [x] T009 [P] [US1] Write `tests/unit/patterns/test_models.py`:
  - every valid fixture constructs with no issues;
  - each `V1`–`V6`/`V8`/`V9` invalid fixture yields exactly its code at its path;
  - a fixture with three independent V-rule breaks reports all three (US1-5);
  - self-loop relationships are allowed.
- [x] T010 [P] [US1] Write `tests/unit/patterns/test_parse.py`:
  - P1 (a 256 KB + 1 byte document);
  - P2–P5 with line and column where applicable;
  - a V7 path such as `constraints[0].expr`, carrying the CEL column;
  - V7 does not run when the structure is invalid;
  - a never-raises fuzz test: 200 random byte strings, 50 truncations of the reference fixture, plus `None`-like and empty inputs, all yielding `ok == False` with no exception, or a valid result;
  - the SC-004 timing check: reference-fixture validation under 100 ms (median of 5).
- [x] T011 [US1] Implement `src/adp/patterns/models.py` (data-model.md):
  - the constrained types and enums;
  - every sub-model with `extra="forbid", frozen=True`, and the cardinality `BeforeValidator`;
  - a `PatternDefinition` after-validator that **collects** V1–V6, V8 and V9 violations and raises one `PydanticCustomError("pattern_rules", …, {"issues": [...]})`;
  - `PatternIssue` and `ParseResult`.

  No import from `cel.py`.
- [x] T012 [US1] Implement `parse_pattern_yaml` and `validate_pattern` in `src/adp/patterns/parse.py`:
  - the size guard;
  - `SafeNoAliasLoader` (reject `AliasEvent` and anchored nodes in `compose_node`);
  - `compose_all` for the multi-document check;
  - the mapping check;
  - Pydantic `ValidationError` → issues (`loc` → `a.b[1].c` path; `pattern_rules` context expanded);
  - V7 through `engine.compile_check` on every selector and expression;
  - a top-level `except Exception` that becomes a `P0.internal` issue, as the last line of defence for FR-012.

  Make T009 and T010 pass.
- [x] T013 [US1] Re-export the public API from `src/adp/patterns/__init__.py`, exactly as listed in contracts/python-api.md.

**Checkpoint**: the US1 MVP is complete. Quickstart steps 1–3 work.

## Phase 4: User Story 2 — Canonical form and digest (P2)

**Goal**: a stable content identity for idempotent import in 935.
**Independent test**: round-trip law plus the digest equality and inequality matrix.

- [x] T014 [P] [US2] Write `tests/unit/patterns/test_canonical.py`:
  - the round-trip law for every valid fixture;
  - digest equal under mapping-key shuffle and under longhand vs shorthand cardinality (add the fixture `valid/…domain-event-backbone-longhand.yaml`);
  - digest different under role reorder, plateau reorder, constraint reorder, and a one-character value change;
  - the digest is 64 lowercase hex characters;
  - canonical YAML contains no `&`/`*` aliases and writes cardinality as shorthand.
- [x] T015 [US2] Implement `to_canonical_json` (roles encoded as ordered `[key, role]` pairs, research D5), `compute_digest` and `to_canonical_yaml` (research D6) in `src/adp/patterns/parse.py`. Make T014 pass.

**Checkpoint**: quickstart step 4 works.

## Phase 5: User Story 3 — Published JSON Schema (P3)

**Goal**: editor autocomplete from a schema that can never drift from the enforced model.

- [x] T016 [P] [US3] Write `tests/unit/patterns/test_schema.py`: `generate_pattern_schema()` is deterministic (called twice, byte-equal); every valid fixture, loaded as plain data, validates against it with `jsonschema` (already a dependency); `$id` and title are present. Extend the existing generate test, if there is one (`tests/unit/test_generate*.py`), so `check()` covers the pattern schema.
- [x] T017 [US3] Add `generate_pattern_schema()` to `src/adp/generate.py`, mirroring `generate_theme_schema()`. Write it to `generated/pattern.schema.json` and wire it into `main()` and `check()`. Run `adp-generate` and commit the output. Make T016 pass and `adp-generate --check` exit 0.

## Phase 6: Polish & cross-cutting

- [x] T018 Quality gates:
  - `pytest tests/ --ignore=tests/integration -q` (full suite, no regressions);
  - coverage of `src/adp/patterns` ≥ 85%;
  - `ruff check src/`, `mypy src/`, `bandit -r src/adp/patterns`, `adp-generate --check`.
- [x] T019 [P] Run every quickstart.md snippet as written and fix any drift in the doc.
- [x] T020 [P] Update `CLAUDE.md` "Recent Changes" with the implemented summary. Note the new `cel-expr-python` dependency and the fact that its iteration budget is fixed.
- [x] T021 Run GitNexus `detect_changes` (expected: new symbols only, plus `adp.generate.main`/`check`). Close bead ADP-mmm.1 once merged.

---

## Dependencies & execution order

- Setup (T001–T002) → Foundational (T003–T006) → US1 (T007–T013) → US2 (T014–T015) → US3 (T016–T017) → Polish.
- T011 (models) blocks T012 (parse). T012 blocks T015 (canonical YAML round-trips through the parser).
- US3 depends only on T011 and could run in parallel with US2.
- **[P] groups**: T003 ∥ T005; T007 ∥ T008 ∥ T009 ∥ T010; T014 ∥ T016; T019 ∥ T020.

## MVP

Phases 1–3 (T001–T013) deliver US1: a usable validator with precise issues. 935 needs US2 as well (the digest). US3 is authoring convenience.
