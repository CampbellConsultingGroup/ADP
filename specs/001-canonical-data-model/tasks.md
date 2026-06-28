# Tasks: Canonical Data Model & Schema Generation

**Input**: Design documents from `/specs/001-canonical-data-model/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are MANDATORY for all ADP features (ART-IV). Test tasks MUST appear before their implementation counterparts in every user-story phase. Tests MUST be committed and verified to fail before any implementation begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on concurrent tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and tooling — no production code yet

- [x] T001 Create directory structure: `src/adp/`, `tests/unit/`, `tests/contract/`, `generated/`, `fixtures/` per plan.md Project Structure
- [x] T002 Create `pyproject.toml` with Python ≥3.11 requirement, dependencies (`pydantic>=2.0`, `jsonschema>=4.0`), dev dependencies (`pytest>=7`, `pytest-cov>=4`), and `[project.scripts]` entry point `adp-generate = "adp.generate:main"`
- [x] T003 Add ruff configuration to `pyproject.toml` (`select = ["E","W","F","I"]`, `line-length = 100`) and mypy configuration (`strict = true`, `ignore_missing_imports = false`)
- [x] T004 Add pytest configuration to `pyproject.toml` (`testpaths = ["tests"]`, `addopts = "--cov=src/adp --cov-report=term-missing"`, `required_plugins = ["pytest-cov"]`) and set coverage threshold to 85%
- [x] T005 [P] Create `src/adp/__init__.py` (export `__version__ = "0.1.0"`), `tests/unit/__init__.py` (empty), `tests/contract/__init__.py` (empty)
- [x] T006 Install package in editable mode (`pip install -e ".[dev]"`) and verify `adp-generate --help` resolves without import errors

**Checkpoint**: `pip install -e ".[dev]"` succeeds; `pytest` collects zero tests without errors; `adp-generate --help` prints usage

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core identifiers, enums, and base model config that every entity model depends on — MUST be complete before any user story begins

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Define all ID type aliases in `src/adp/models.py`: `RequirementId`, `ElementId`, `RelationshipId`, `OptionId`, `FindingId`, `VerdictId`, `AuditEntryId` — each as `Annotated[str, Field(pattern=r'^XXX-\d{3}$')]` using the prefixes from data-model.md
- [x] T008 Add `ElementKind` (Literal or StrEnum: `person`, `system`, `container`, `component`) and `VerdictStatus` (StrEnum: `pending`, `accepted`, `rejected`, `deferred`) to `src/adp/models.py`
- [x] T009 Define shared `_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=False)` constant in `src/adp/models.py`; apply it as `model_config` on a `_BaseModel(BaseModel)` that all entities inherit from
- [x] T010 Define `ArchitectureDescription` shell in `src/adp/models.py` with mandatory fields only (`schema_version: str`, `id: str`, `title: str`, `created_at: datetime`, `updated_at: datetime`) and all entity lists defaulting to `[]` — no validator yet, no entity models yet
- [x] T011 Create `src/adp/generate.py` with CLI argument parser (`argparse`: `--check`, `--validate PATH`), a `generate()` stub that returns `{}`, and `main()` that dispatches to `generate()` or `check()` stubs; entry point must be importable
- [x] T012 Create `src/adp/validate.py` with `build_id_index(description: ArchitectureDescription) -> dict[str, object]` stub and `validate_references(description: ArchitectureDescription) -> None` stub (both raise `NotImplementedError` for now)

**Checkpoint**: `python -c "from adp.models import ArchitectureDescription; print(ArchitectureDescription(schema_version='1.0.0', id='D-001', title='Test', created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z'))"` succeeds

---

## Phase 3: User Story 1 — Author a Valid Design (Priority: P1) 🎯 MVP

**Goal**: All eight typed entities exist; a full `ArchitectureDescription` serializes to JSON, validates against the published schema, and round-trips back to an identical model.

**Independent Test**: Construct an `ArchitectureDescription` with at least one of every entity type, serialize to JSON, deserialize, assert equality. Load `fixtures/example-adp.json` against `generated/architecture-description.schema.json` — both must pass without errors.

### Tests for User Story 1 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T013 [P] [US1] Write failing `test_round_trip_all_entities()` in `tests/unit/test_models.py` — import all entity classes, construct `ArchitectureDescription` with one of each, call `model_dump_json()`, call `model_validate_json(json_str)`, assert the result equals the original
- [x] T014 [P] [US1] Write failing `test_example_validates_against_schema()` in `tests/contract/test_schema.py` — load `fixtures/example-adp.json` with `json.load()`, load `generated/architecture-description.schema.json`, call `jsonschema.validate(instance, schema)`, assert no `ValidationError` raised

### Implementation for User Story 1

- [x] T015 [US1] Add `Requirement` model to `src/adp/models.py`: fields `id: RequirementId`, `title: str` (max 120), `description: str`, `priority: Literal["must","should","may"] | None = None`, `tags: list[str] = []`
- [x] T016 [US1] Add `Element` model to `src/adp/models.py`: fields `id: ElementId`, `name: str` (max 120), `kind: ElementKind`, `description: str | None = None`, `satisfies: list[RequirementId] = []`, `provenance: str | None = None`, `tags: list[str] = []`
- [x] T017 [US1] Add `Relationship` model to `src/adp/models.py`: fields `id: RelationshipId`, `source: ElementId`, `target: ElementId`, `label: str | None = None` (max 80), `technology: str | None = None` (max 80)
- [x] T018 [US1] Add `SolutionOption` model to `src/adp/models.py`: fields `id: OptionId`, `title: str` (max 120), `description: str`, `status: VerdictStatus`, `satisfies: list[RequirementId] = []`, `provenance: str | None = None`
- [x] T019 [US1] Add `Finding` model to `src/adp/models.py`: fields `id: FindingId`, `subject: ElementId | OptionId`, `summary: str` (max 240), `detail: str | None = None`, `severity: Literal["info","warning","critical"] = "info"`, `source: str | None = None`
- [x] T020 [US1] Add `Verdict` model to `src/adp/models.py`: fields `id: VerdictId`, `option_id: OptionId`, `status: VerdictStatus`, `rationale: str`, `decided_by: str`, `decided_at: datetime`, `provenance: str | None = None`
- [x] T021 [US1] Add `AuditEntry` model to `src/adp/models.py`: fields `id: AuditEntryId`, `actor: str`, `action: str`, `affected_entity: str`, `summary: str` (max 240), `timestamp: datetime`, `origin: Literal["human","ai"]`
- [x] T022 [US1] Update `ArchitectureDescription` in `src/adp/models.py` to type all entity list fields: `requirements: list[Requirement] = []`, `elements: list[Element] = []`, `relationships: list[Relationship] = []`, `options: list[SolutionOption] = []`, `findings: list[Finding] = []`, `verdicts: list[Verdict] = []`, `audit_log: list[AuditEntry] = []`; add `@field_validator("schema_version")` that enforces semver pattern `\d+\.\d+\.\d+`
- [x] T023 [US1] Implement `generate()` body in `src/adp/generate.py`: call `ArchitectureDescription.model_json_schema()`, inject top-level `$schema`, `$id`, `title`, and `schema_version` fields from the model's declared version constant (`"1.0.0"`), serialize with `json.dumps(schema, sort_keys=True, indent=2)`, write result with trailing newline to `generated/architecture-description.schema.json`; wrap the file write in try/except `OSError` and print a clear error message with `sys.exit(1)` if the path is not writable
- [x] T024 [US1] Run `adp-generate` to produce `generated/architecture-description.schema.json`; verify it contains `$schema`, `$id`, `title`, and `schema_version` at the top level
- [x] T025 [US1] Create `fixtures/example-adp.json` — a complete canonical instance with one `Requirement` (`REQ-001`), two `Element`s (`ELM-001`, `ELM-002`) that satisfy `REQ-001`, one `Relationship` (`REL-001`) from `ELM-001` to `ELM-002`, one `SolutionOption` (`OPT-001`) that satisfies `REQ-001`, one `Finding` (`FND-001`) on `ELM-001`, one `Verdict` (`VRD-001`) on `OPT-001`, and one `AuditEntry` (`AUD-001`)
- [x] T026 [US1] Verify `test_round_trip_all_entities` and `test_example_validates_against_schema` now pass; commit `src/adp/models.py`, `src/adp/generate.py`, `generated/architecture-description.schema.json`, `fixtures/example-adp.json`

**Checkpoint**: `pytest tests/unit/test_models.py tests/contract/test_schema.py` green; User Story 1 fully functional and independently testable

---

## Phase 4: User Story 2 — Reject Malformed Data (Priority: P1)

**Goal**: Every entity rejects unknown fields with a `ValidationError`; malformed ID formats (`REQ-ABC`, `REQ-1234`) are rejected at parse time with a pattern error. Zero silent acceptances.

**Independent Test**: Attempt to construct each entity with an extra field — assert `ValidationError`. Attempt to set an invalid ID — assert `ValidationError` with a pattern message. Both assertions must hold for every entity type.

### Tests for User Story 2 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (they will import-fail until Phase 3 models exist)**

- [x] T027 [P] [US2] Write failing `test_extra_field_rejected_on_every_entity()` in `tests/unit/test_validation.py` — for each of the seven entity types, attempt construction with an unknown field (e.g., `{"id":"REQ-001","title":"T","description":"D","extra_field":"x"}`), assert `pydantic.ValidationError` is raised with `extra inputs are not permitted` in the error message
- [x] T028 [P] [US2] Write failing `test_invalid_id_formats_rejected()` in `tests/unit/test_validation.py` — test: `REQ-ABC` (non-numeric), `REQ-1234` (four digits), `req-001` (lowercase), empty string, and no `id` field at all — each MUST raise `ValidationError` with a pattern-related message; test across `RequirementId`, `ElementId`, `OptionId` at minimum

### Implementation for User Story 2

- [x] T029 [US2] Audit `src/adp/models.py`: confirm `model_config = ConfigDict(extra="forbid")` is applied on every entity model class (`Requirement`, `Element`, `Relationship`, `SolutionOption`, `Finding`, `Verdict`, `AuditEntry`, `ArchitectureDescription`); if any entity inherits only from `BaseModel` without the config, fix it
- [x] T030 [US2] Add boundary-condition test cases to `tests/unit/test_validation.py`: empty `title` (should fail — non-empty constraint), `title` over 120 chars, `description` over 240 chars on `Finding` and `AuditEntry`, `severity` value `"fatal"` (not in enum) — assert each raises `ValidationError`
- [x] T031 [US2] Verify `test_extra_field_rejected_on_every_entity` and `test_invalid_id_formats_rejected` pass; confirm `pytest tests/unit/test_validation.py` is fully green

**Checkpoint**: `pytest tests/unit/test_validation.py` green; SC-002 (100% rejection of malformed input) verifiable

---

## Phase 5: User Story 3 — Detect Schema Drift in CI (Priority: P2)

**Goal**: `adp-generate --check` exits non-zero with a human-readable diff when the committed schema diverges from what the current `models.py` would produce. CI workflow fails the build on drift.

**Independent Test**: Run `adp-generate --check` against the current `generated/architecture-description.schema.json` — exit 0. Manually modify `generated/architecture-description.schema.json`, run again — exit non-zero with diff output. Restore, run again — exit 0.

### Tests for User Story 3 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T032 [P] [US3] Write failing `test_check_mode_no_drift()` in `tests/unit/test_generate.py` — generate schema, write to a `tmp_path` file, invoke `check(committed_path=tmp_path)` from `adp.generate`, assert it returns without raising and exit code is 0; also write `test_generator_determinism()` that calls `generate()` twice in the same process and asserts the two returned strings are identical
- [x] T033 [P] [US3] Write failing `test_check_mode_detects_drift()` in `tests/unit/test_generate.py` — write stale content `{"old": true}` to a `tmp_path` file, invoke `check(committed_path=tmp_path)`, assert it raises `SystemExit` with code 1 and that the string `"drift"` or the file path appears in captured stderr; also write `test_check_mode_file_not_found()` asserting that invoking `check(committed_path=tmp_path / "nonexistent.json")` raises a `FileNotFoundError` or `SystemExit` with a clear message — not an unhandled traceback

### Implementation for User Story 3

- [x] T033b [P] [US3] Write failing `test_validate_mode_valid_file()` and `test_validate_mode_invalid_file()` in `tests/unit/test_generate.py` — invoke `validate(path=tmp_path / "example.json")` with a valid `ArchitectureDescription` fixture and assert exit 0; invoke with an invalid JSON fragment and assert exit non-zero with a validation error message

- [x] T034 [US3] Implement `check(committed_path: Path) -> None` in `src/adp/generate.py`: call `generate()` to get the in-memory schema string, read the committed file, diff using `difflib.unified_diff`, if diff non-empty print the diff to stderr and call `sys.exit(1)` with message `"Schema drift detected — run adp-generate to regenerate"`
- [x] T035 [US3] Wire `--check` CLI flag in `src/adp/generate.py:main()` to call `check(committed_path=Path("generated/architecture-description.schema.json"))`; wire `--validate PATH` to load the file, parse it as `ArchitectureDescription`, and report success or validation errors
- [x] T036 [US3] Create `.github/workflows/drift-check.yml`: trigger on `push` and `pull_request` targeting `main`; steps: checkout, setup Python 3.11, `pip install -e ".[dev]"`, `adp-generate --check`; name the step "QG-02: Schema drift gate"
- [x] T037 [US3] Verify `test_check_mode_no_drift` and `test_check_mode_detects_drift` pass; manually run `adp-generate --check` and confirm exit 0; mutate `generated/architecture-description.schema.json`, rerun, confirm exit 1, restore

**Checkpoint**: `pytest tests/unit/test_generate.py` green; `adp-generate --check` exits correctly in both scenarios; CI workflow file present

---

## Phase 6: User Story 4 — Validate Cross-Entity References (Priority: P2)

**Goal**: Any `ArchitectureDescription` with a dangling reference — a `satisfies` pointing to a non-existent `RequirementId`, a `Relationship` with a non-existent `source`, a `Verdict` targeting a non-existent `OptionId` — is rejected at load time with an error naming the specific missing ID.

**Independent Test**: Load a description where `element.satisfies = ["REQ-999"]` and `requirements` contains only `REQ-001` — assert `ValidationError` and confirm `"REQ-999"` appears in the error string. Load the same description with `REQ-999` present — assert no error.

### Tests for User Story 4 (MANDATORY — ART-IV)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T038 [P] [US4] Write failing `test_valid_references_pass()` in `tests/unit/test_referential_integrity.py` — build a `ArchitectureDescription` where `ELM-001.satisfies = ["REQ-001"]`, `REL-001.source = "ELM-001"`, `REL-001.target = "ELM-002"`, `OPT-001.satisfies = ["REQ-001"]`, `FND-001.subject = "ELM-001"`, `VRD-001.option_id = "OPT-001"` and all referenced entities exist; assert construction succeeds
- [x] T039 [P] [US4] Write failing `test_dangling_requirement_reference()`, `test_dangling_element_source()`, `test_dangling_element_target()`, `test_dangling_finding_subject()`, `test_dangling_verdict_option()` in `tests/unit/test_referential_integrity.py` — each introduces exactly one missing reference; assert `ValidationError` is raised and the missing ID string appears in `str(exc_info.value)`

### Implementation for User Story 4

- [x] T040 [US4] Implement `build_id_index(description: ArchitectureDescription) -> dict[str, object]` in `src/adp/validate.py`: iterate all entity lists, add each entity's `id` as a key; collect all duplicate IDs across all entity lists before raising a single `ValueError` that names every duplicate — consistent with T041's collect-all strategy
- [x] T041 [US4] Implement `validate_references(description: ArchitectureDescription, index: dict[str, object]) -> None` in `src/adp/validate.py`: check `Element.satisfies` → `requirements` index, `Relationship.source`/`target` → `elements` index, `SolutionOption.satisfies` → `requirements` index, `Finding.subject` → `elements + options` index, `Verdict.option_id` → `options` index; raise `ValueError(f"Reference {missing_id!r} not found in {collection_name}")` for every missing reference, collecting all errors before raising
- [x] T042 [US4] Add `@model_validator(mode='after')` to `ArchitectureDescription` in `src/adp/models.py`: call `build_id_index(self)` and `validate_references(self, index)` from `adp.validate`; propagate `ValueError` as `PydanticCustomError` with the missing-ID message so it surfaces in `ValidationError.errors()`
- [x] T043 [US4] Verify all five dangling-reference tests fail before T040-T042 are implemented (confirm via `git stash` or test isolation); then implement and verify all tests in `tests/unit/test_referential_integrity.py` pass

**Checkpoint**: `pytest tests/unit/test_referential_integrity.py` green; SC-004 (dangling reference named in error) verifiable; ART-XI / QG-16 implemented

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Coverage, quality gates, documentation validation — ensures all constitutional gates pass

- [x] T044 [P] Run `pytest --cov=src/adp --cov-report=term-missing` and verify line coverage ≥ 85%; identify uncovered lines and add targeted unit tests in `tests/unit/` until threshold is met (QG-04)
- [x] T045 [P] Run `ruff check src/ tests/` and `mypy src/adp/` — fix all reported issues; verify both tools exit 0 (QG-06 prerequisite)
- [x] T046 [P] Run `adp-generate --validate fixtures/example-adp.json` end-to-end; confirm output confirms schema-valid and referentially intact — validates quickstart.md scenario (SC-005)
- [x] T047 [P] Add `bandit` (or enable ruff security rules `S*`) to dev dependencies and CI; run against `src/adp/`; fix any `HIGH` severity findings (QG-06)
- [x] T047b [P] Add `pip-audit>=2.0` to dev dependencies in `pyproject.toml`; add a `pip-audit --strict` step to `.github/workflows/drift-check.yml` after the existing dependency install step; verify no high/critical CVEs are reported (QG-07)
- [x] T048 Pin all dependency versions to exact specifiers in `pyproject.toml` (e.g., `pydantic==2.x.y`); run `pip install -e ".[dev]"` from scratch to verify reproducible install (NFR-001 / QG-18)
- [x] T049 Update `specs/001-canonical-data-model/checklists/requirements.md` — mark all previously failing items complete; replace the C4 code-level `[NEEDS CLARIFICATION]` marker in `specs/001-canonical-data-model/spec.md` with the resolved decision ("stops at component; `Element.kind` is a closed four-value enum")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup complete (T001–T006) — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational complete — 🎯 MVP; delivers the full entity model and schema generator
- **User Story 2 (Phase 4)**: Depends on Foundational complete; entity models from US1 must exist for tests to run — effectively depends on Phase 3 models
- **User Story 3 (Phase 5)**: Depends on US1 complete (schema generator must exist for drift testing)
- **User Story 4 (Phase 6)**: Depends on all entity models from US1 being in place
- **Polish (Phase 7)**: Depends on all desired user stories complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P1)**: Logically parallel with US1, but entity models must exist (from US1 Phase 3 T015–T022) for US2 tests to run; tests can be written in parallel
- **US3 (P2)**: Depends on US1 schema generator (T023); no dependency on US2 or US4
- **US4 (P2)**: Depends on US1 entity models (T015–T022); no dependency on US2 or US3

### Parallel Opportunities

- T005 (Setup) runs independently; T003 and T004 are sequential (same `pyproject.toml` file)
- T013, T014 (US1 tests) run in parallel — different test files
- T027, T028 (US2 tests) run in parallel
- T032, T033 (US3 tests) run in parallel
- T038, T039 (US4 tests) run in parallel
- T044, T045, T046, T047 (Polish) run in parallel

---

## Parallel Example: User Story 1

```bash
# Write tests in parallel (different files, no shared state):
Task T013: tests/unit/test_models.py
Task T014: tests/contract/test_schema.py

# Entity model additions are sequential (single file: src/adp/models.py):
T015 → T016 → T017 → T018 → T019 → T020 → T021 → T022

# After entity models added:
Task T023: src/adp/generate.py (parallel with T025)
Task T025: fixtures/example-adp.json (parallel with T023)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T012) — CRITICAL: blocks everything
3. Write US1 tests T013, T014 — verify they fail
4. Complete Phase 3: T015–T026 — entity models, generator, canonical example
5. **STOP and VALIDATE**: `pytest tests/unit/test_models.py tests/contract/test_schema.py` green
6. `adp-generate --check` exits 0

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Add Phase 3 (US1) → schema published, round-trip verified (MVP)
3. Add Phase 4 (US2) → rejection guarantees confirmed
4. Add Phase 5 (US3) → CI drift gate active
5. Add Phase 6 (US4) → referential integrity enforced end-to-end
6. Phase 7 → all quality gates green; spec ready for implementation sign-off

### Single Developer Strategy

Phases 1 and 2 first, then work through user story phases strictly in order: US1 → US2 → US3 → US4. Within each phase, always write and commit tests first (observe failure), then implement, then verify green.

---

## Notes

- [P] tasks = different files or truly independent concerns; no dependency on concurrent tasks
- [Story] label maps each task to its user story for traceability back to spec.md acceptance criteria
- Tests MUST fail before implementation begins; commit the failing test first
- Each user story is independently completable and demonstrable
- Constitution gates relevant to this feature: QG-02, QG-03, QG-04, QG-05, QG-06, QG-16, QG-18
- The `generated/architecture-description.schema.json` file MUST be committed to the repo but MUST only ever be written by `adp-generate` (ART-II / QG-02)
- The `fixtures/example-adp.json` file is both a human-readable example and the QG-05 contract test fixture — keep it schema-valid at all times
