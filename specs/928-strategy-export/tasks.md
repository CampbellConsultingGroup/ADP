# Tasks: Continuous Strategy Domain Export to Versioned Files

**Input**: Design documents from `/specs/928-strategy-export/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). Test tasks appear before their implementation counterparts and must
be written and verified to fail first.

**Organization**: One cohesive feature (unlike 925's two genuinely independent link types) — User
Story 1 is the entire export mechanism (themes/objectives/initiatives + every relationship +
the `business_arch.py` extension), since nothing in this domain is meaningfully shippable in a
smaller independent slice the way 927's create/read/remove split was. User Story 2 (reviewable
diffs) adds no new code of its own — it's verified through US1's own mechanism, so its tasks are
verification-only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2, per spec.md's priorities (P1/P2)

## Path Conventions

Single project, existing packages/files only, plus one new module:
- Backend: `src/adp/export/strategy.py` (new), `src/adp/export/business_arch.py` (extended),
  `src/adp/api/app.py` (extended — third background task)
- Backend tests: `tests/unit/export/test_strategy_export_serialize.py` (new),
  `tests/unit/export/test_strategy_export_reconciliation.py` (new),
  `tests/unit/export/test_business_arch_serialize.py` (extended — 2 existing tests updated),
  `tests/integration/test_strategy_export_cycle.py` (new)

---

## Phase 1: Foundational (Bulk-Fetch Scaffolding)

**Purpose**: The one shared snapshot type and its bulk queries every serialization function and
the reconciliation loop depend on.

**⚠️ CRITICAL**: No serialization/reconciliation work can begin until this phase is complete.

- [X] T001 Create `src/adp/export/strategy.py` with module docstring (mirrors `application_arch.py`'s own opening docstring shape) and imports: `adp.strategy.store as sstore`, `adp.strategy.initiatives as sinit`, `adp.business.store as bstore` (read-only, for the two design-link tables needed by T003's *sibling* task in `business_arch.py`, not by this module directly), `adp.export.common`'s helpers (`_cleanup_orphan_files`, `_safe_filename`, `_write_entity_file`, `start_background_sync`, `stop_background_sync`)
- [X] T002 [US1] Define `StrategyExportSnapshot` (frozen dataclass) in `strategy.py`: `themes: list[StrategicTheme]`, `objective_rows: list[Any]` (raw scalar rows), `initiatives: list[StrategyInitiative]`, plus `dict[str, list[str]]`/`dict[str, list[dict]]` fields for every objective relationship in research.md Decision 4 (`capability_ids_by_objective`, `value_stream_ids_by_objective`, `design_ids_by_objective`, `application_ids_by_objective`, `control_ids_by_objective`, `depends_on_by_objective`, `blocks_by_objective`, `initiative_ids_by_objective`, `objective_ids_by_initiative`, `progress_by_objective`)
- [X] T003 [US1] Implement `_fetch_all(session) -> StrategyExportSnapshot` in `strategy.py`: `sstore.list_themes(session)`; one raw `SELECT` on `sstore._objectives` for scalar fields (not `sstore.list_objectives`, which returns summaries only — research.md Decision 4); one bulk `GROUP BY`-style query per objective link table (`_objective_capabilities`, `_objective_value_streams`, `_objective_design_links`, `_objective_application_links`, `_objective_control_links`); one query on `_objective_dependencies` grouped both ways (`depends_on_by_objective`/`blocks_by_objective`); one query on `_initiative_objective_links` grouped both ways (`initiative_ids_by_objective`/`objective_ids_by_initiative`); one query on `_progress` grouped by `objective_id`, sorted by `as_of_date`; `sinit.list_initiatives(session)` for initiatives (accepted N+1 internally at this domain's scale — research.md Decision 4's own recorded deviation, not a fresh five-table dispatch reimplementation in this module)
- [X] T004 [P] [US1] Unit tests in `tests/unit/export/test_strategy_export_reconciliation.py` for T003: seed a SQLite fixture (mirrors `tests/unit/strategy/test_theme_framework_links.py`'s own `sstore._metadata.create_all()` setup, extended to also create `sinit`'s tables) with 2 themes, 2 objectives (one with every link type populated, one with none), 1 initiative linked to one objective and one control mapping; assert `_fetch_all()` returns correct, correctly-grouped dicts for every relationship, with an empty list (never a missing key) for the objective with no links

**Checkpoint**: `_fetch_all()` returns a complete, correctly-grouped snapshot; unit tests pass.

---

## Phase 2: User Story 1 - An AI tool or teammate reads current strategy execution straight from the repo (Priority: P1) 🎯 MVP

**Goal**: Every theme, objective (with computed status, full progress history, and every
cross-domain link), and initiative (with objective links and live compliance-mapping status) is
exported to a versioned JSON file tree, kept in sync by the existing background-export mechanism.

**Independent Test**: Create a theme/objective/initiative with every relationship type populated
through the existing API, let one reconciliation cycle run, and confirm each exported file exists
and is well-formed (quickstart.md Scenarios 1–3).

### Tests for User Story 1 (write first — ART-IV)

- [X] T005 [P] [US1] Unit tests in `tests/unit/export/test_strategy_export_serialize.py` for `_serialize_theme`: includes all `StrategicTheme` fields incl. `framework_ids`; empty `framework_ids` is `[]` not omitted
- [X] T006 [P] [US1] Unit tests in `tests/unit/export/test_strategy_export_serialize.py` for `_serialize_objective`: includes every scalar field, the computed `status`/`status_reason` passed in (not recomputed inside the serializer — a pure function per research.md's "no I/O in serializers" convention), every `*_ids` relationship array (empty case included), `depends_on_objective_ids`/`blocked_objective_ids`, `initiative_ids`, and `progress` (ordered, `actual_value` as a JSON string)
- [X] T007 [P] [US1] Unit tests in `tests/unit/export/test_strategy_export_serialize.py` for `_serialize_initiative`: includes all `StrategyInitiative` fields incl. `objective_ids` and `control_mappings` (each `ControlMappingRef` field, incl. the `target_id: None` organization-scope case)
- [X] T008 [P] [US1] Integration test in `tests/integration/test_strategy_export_cycle.py` (testcontainers-gated, Docker unavailable locally — same constraint every COMPLY-0x/927/704 suite this session has hit; written and will run in CI): one full reconciliation cycle against a real Postgres container covering every relationship type in FR-013/014/015/016, mirroring quickstart.md's scenarios end-to-end

### Implementation for User Story 1

- [X] T009 [US1] Implement pure `_serialize_theme(theme: StrategicTheme) -> dict` in `strategy.py` (depends on T001)
- [X] T010 [US1] Implement pure `_serialize_objective(objective_row, *, status, status_reason, capability_ids, value_stream_ids, design_ids, application_ids, control_ids, depends_on, blocks, initiative_ids, progress) -> dict` in `strategy.py` — `target_value` and each progress entry's `actual_value` rendered via `str(...)` (Decimal-as-string, matching `application_arch.py`'s own convention) (depends on T002)
- [X] T011 [US1] Implement pure `_serialize_initiative(initiative: StrategyInitiative) -> dict` in `strategy.py` — `control_mappings` entries serialized via each `ControlMappingRef`'s own fields (depends on T001)
- [X] T012 [US1] Implement `compute_status()`-in-memory status resolution in `strategy.py`: for each objective row from T003, call `sstore.compute_status(row.status, row.target_value, row.direction, progress_by_objective.get(row.id, []))` — zero additional I/O beyond T003's single bulk progress read (research.md Decision 4) (depends on T003)
- [X] T013 [US1] Implement `run_reconciliation_cycle(export_root, session)` in `strategy.py`: fetch via T003, compute status via T012, write `strategy/themes/<id>.json` (T009), `strategy/objectives/<id>.json` (T010), `strategy/initiatives/<id>.json` (T011) via `_write_entity_file`; orphan cleanup via `_cleanup_orphan_files` for all three (flat directories, no nested subtree needed — research.md Decision 3); wrap the whole cycle in try/except logging a warning on failure (FR-006), matching `application_arch.py`'s own `run_reconciliation_cycle` shape exactly (depends on T009, T010, T011, T012)
- [X] T014 [US1] Implement `start_background_sync(export_root, interval_seconds, session_factory)`/`stop_background_sync(task)` thin wrappers around `adp.export.common`'s generic lifecycle in `strategy.py`, matching `application_arch.py`'s own wrapper shape exactly (depends on T013)
- [X] T015 [US1] In `src/adp/api/app.py`: add `start_strategy_export()`/`stop_strategy_export()` (reusing `ADP_BUSINESS_ARCH_EXPORT_ROOT`/`ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS`, `sstore._get_session_factory()`), call both in `_lifespan`'s startup/shutdown alongside the two existing export tasks (depends on T014)

### Implementation for User Story 1 — Clarification Q2 extension to `business_arch.py`

- [X] T016 [P] [US1] In `src/adp/export/business_arch.py`: add `capability_design_links: dict[str, list[str]]` and `value_stream_design_links: dict[str, list[str]]` fields to `BusinessArchSnapshot`; in `_fetch_all()`, add one bulk `GROUP BY`-style query each against `bstore._cap_design_links`/`bstore._vs_design_links` (imported read-only from `adp.business.store`)
- [X] T017 [US1] In `business_arch.py`: add a `linked_designs: list[str]` parameter to `_serialize_capability`/`_serialize_value_stream`; update `run_reconciliation_cycle`'s two call sites to pass `snapshot.capability_design_links.get(cap.id, [])`/`snapshot.value_stream_design_links.get(vs.id, [])` (depends on T016)
- [X] T018 [US1] Update the two existing exact-equality tests in `tests/unit/export/test_business_arch_serialize.py` (`test_serialize_capability_includes_all_fields`, `test_serialize_value_stream`) to pass a `linked_designs` arg and expect it in the result dict; add one new test confirming an empty `linked_designs` list (not omitted) for an entity with no design link (depends on T017)
- [X] T019 Run the full pre-existing `tests/unit/export/test_business_arch_*.py` and `tests/integration/test_business_arch_export_cycle.py` suites and confirm they all still pass (aside from T018's intentional updates) — the regression safety net Complexity Tracking calls for (depends on T018)

**Checkpoint**: Every theme/objective/initiative and every relationship in FR-010–016 exports
correctly; the `business_arch.py` extension is regression-safe.

---

## Phase 3: User Story 2 - A reviewer sees exactly what changed in strategy execution as a readable diff (Priority: P2)

**Goal**: Confirm the change-detection/orphan-cleanup behavior US1 already implements (via
`adp.export.common`, reused unchanged) produces small, targeted diffs and correct cleanup for this
domain specifically — no new code, verification only.

**Independent Test**: Record a single progress entry, let one cycle run, confirm only that
objective's file changed; delete an objective, confirm its file and dependent link references are
removed (quickstart.md Scenario 4, 6).

### Tests for User Story 2

- [X] T020 [P] [US2] Unit test in `tests/unit/export/test_strategy_export_reconciliation.py`: recording one objective's progress entry, then re-running `run_reconciliation_cycle`, changes only that objective's file (mtime/content of every other file untouched)
- [X] T021 [P] [US2] Unit test in `tests/unit/export/test_strategy_export_reconciliation.py`: deleting an objective removes its own file via orphan cleanup, and a sibling objective's `depends_on_objective_ids`/`blocked_objective_ids` no longer references the deleted id on the next cycle
- [X] T022 [P] [US2] Unit test in `tests/unit/export/test_strategy_export_reconciliation.py`: re-running `run_reconciliation_cycle` with no underlying data change does not rewrite any file (content-diff-aware write, reused from `adp.export.common` unchanged)

**Checkpoint**: Diff-friendliness and orphan cleanup confirmed for this domain's own entity/link
shapes.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T023 [P] Run `ruff check src/adp/export/ src/adp/api/app.py` and `mypy src/adp/export/`; fix any issues
- [X] T024 Walk through every scenario in `quickstart.md` against a real local Postgres + running backend with `ADP_BUSINESS_ARCH_EXPORT_ROOT` set to a scratch directory; confirm each scenario's stated expectation holds, then clean up the scratch export directory afterward

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — BLOCKS User Story 1.
- **User Story 1 (Phase 2)**: Depends on Foundational. The `business_arch.py` extension (T016–T019) is independent of T009–T015 (different file) and can proceed in parallel once Phase 1 is done, but both must complete before Phase 2's checkpoint.
- **User Story 2 (Phase 3)**: Depends on User Story 1 (nothing to verify without the mechanism it verifies).
- **Polish (Phase 4)**: Depends on both user stories.

### Within Each User Story

- Tests MUST be written and FAIL before implementation.
- Bulk-fetch (T003) before serialization (T009–T011) before orchestration (T013) before lifecycle wiring (T015).

### Parallel Opportunities

- T005/T006/T007/T008 (all test-authoring, different describe blocks/files) can be written in parallel.
- T016 (business_arch.py snapshot/fetch) can proceed in parallel with T009–T012 (strategy.py serialization) — different files, no shared dependency.
- T020/T021/T022 (all read-only verification tests) can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Foundational (bulk-fetch scaffolding).
2. Complete Phase 2: User Story 1 (the entire export mechanism, incl. the `business_arch.py` extension).
3. **STOP and VALIDATE**: run quickstart.md Scenarios 1, 2, 3, 5 against a real local stack.

### Incremental Delivery

1. Foundational → foundation ready.
2. User Story 1 → the whole feature works → validate independently (this is the real deliverable; User Story 2 only confirms properties US1's own reused mechanism already guarantees).
3. User Story 2 → diff-friendliness/orphan-cleanup confirmed for this domain's own shapes → validate independently.
4. Polish → lint/type clean, full quickstart walkthrough.

## Notes

- `[Story]` label maps each task to its user story for traceability back to spec.md.
- Commit after each task or logical group; stop at any checkpoint to validate independently.
