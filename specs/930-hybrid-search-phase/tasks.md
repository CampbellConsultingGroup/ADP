# Tasks: Hybrid Search Phase 2 Completion

**Input**: Design documents from `/specs/930-hybrid-search-phase/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV) — and, per FR-009/SC-004, this feature's own central deliverable.

**Organization**: US1 (stage indexing, incl. the cascade-unindex fix) is the real new mechanism;
US2 (domain org_unit) is a one-line-per-call-site addition; US3 (backfill) is independent of both
and can proceed in parallel once the constant exists.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- `src/adp/search/index.py`, `src/adp/search/__init__.py`, `src/adp/search/backfill.py`,
  `src/adp/business/store.py`
- `tests/unit/business/test_search_indexing.py` (new), `tests/unit/search/test_backfill.py` (new),
  `tests/integration/test_search.py` (extended)

---

## Phase 1: Foundational (New Constant)

- [X] T001 Add `ENTITY_VALUE_STREAM_STAGE = "value_stream_stage"` to `src/adp/search/index.py`,
  alongside its five siblings; re-export from `src/adp/search/__init__.py`

**Checkpoint**: Constant importable from `adp.search`.

---

## Phase 2: User Story 1 — Stage indexing + cascade-unindex fix (Priority: P1)

### Tests (write first — ART-IV)

- [X] T002 [P] [US1] Unit tests in `tests/unit/business/test_search_indexing.py` (new file,
  monkeypatched `bstore.index_entity`/`unindex_entity`, SQLite-backed store fixture): `add_stage`
  indexes on create; `update_stage` re-indexes with new text; `delete_stage` unindexes;
  `reorder_stages` unindexes dropped stages and re-indexes renamed survivors;
  `delete_value_stream` unindexes every one of its stages (the cascade-unindex fix, FR-004) —
  including the zero-stages case (must not raise)
- [X] T003 [P] [US1] Docker-gated integration test in `tests/integration/test_search.py`
  (extended, `_FakeEmbedder` pattern): create a stage via `add_stage`, confirm a real hybrid search
  finds it, delete its parent value stream, confirm the search no longer finds it — the real SQL
  round-trip for T002's assertions

### Implementation

- [X] T004 [US1] Add `index_entity(ENTITY_VALUE_STREAM_STAGE, ...)` to `add_stage` and
  `update_stage` in `src/adp/business/store.py`, using `build_text(name, description)` (depends on
  T001; T002 must fail first)
- [X] T005 [US1] Add `unindex_entity(ENTITY_VALUE_STREAM_STAGE, ...)` to `delete_stage` on
  successful delete (depends on T001)
- [X] T006 [US1] Add unindex-dropped/reindex-renamed handling inline in `reorder_stages` (depends
  on T001)
- [X] T007 [US1] Fix `delete_value_stream`: query the value stream's stage ids *before* the
  cascading delete, unindex each after the value stream's own delete+unindex (depends on T001)

**Checkpoint**: T002/T003 pass; every existing business-registry test still passes unmodified.

---

## Phase 3: User Story 2 — Domain org_unit indexing (Priority: P2)

### Tests (write first — ART-IV)

- [X] T008 [P] [US2] Unit tests in `tests/unit/business/test_search_indexing.py`: `create_domain`
  and `update_domain` both index text including `org_unit` (monkeypatched, same pattern as T002) —
  also covers the pre-existing 041 wiring for `name`/`scope_statement`, closing that part of Ground-
  Truth Correction #6
- [X] T009 [P] [US2] Docker-gated integration test in `tests/integration/test_search.py`: a domain
  with only a distinctive `org_unit` (no matching name/scope text) is found by searching that value

### Implementation

- [X] T010 [US2] Add `org_unit` to `build_text(...)` in both `create_domain` and `update_domain`
  in `src/adp/business/store.py` (T008 must fail first)

**Checkpoint**: T008/T009 pass.

---

## Phase 4: User Story 3 — Backfill `reindex_all()` (Priority: P2)

### Tests (write first — ART-IV)

- [X] T011 [P] [US3] Unit tests in `tests/unit/search/test_backfill.py` (new file, monkeypatched
  `adp.search.backfill.default_index` returning a recording fake, SQLite-backed
  `bstore`/`astore` fixtures seeded with one of each entity type): `reindex_all()` upserts all 6
  entity types (business_capability, technical_capability, application, value_stream,
  value_stream_stage, business_domain) with correct text, and returns a per-type count dict
- [X] T012 [P] [US3] Docker-gated integration test in `tests/integration/test_search.py`: seed one
  of each of the 5 write-hooked entity types with the real index table pre-emptied, run
  `reindex_all()` against real Postgres, confirm every one is discoverable via `hybrid_search`
  afterward

### Implementation

- [X] T013 [US3] Implement `reindex_all(session) -> dict[str, int]` in
  `src/adp/search/backfill.py`: calls `reindex_capabilities()` for its two types, then indexes
  applications (`astore.list_applications`), value streams (`bstore.list_value_streams`), stages
  (direct `sa.select(bstore._stages)` — no existing bulk function, mirroring
  `adp.export.business_arch._fetch_all()`'s own precedent for this table), and domains
  (`bstore.list_domains_full`) (depends on T001; T011 must fail first)
- [X] T014 [US3] Update `main()` to call `reindex_all()` and print a per-type summary instead of
  `reindex_capabilities()`'s capability-only count (depends on T013)

**Checkpoint**: T011/T012 pass; `python -m adp.search.backfill` indexes all 5 entity types.

---

## Phase 5: Polish

- [X] T015 [P] Run `ruff check src/adp/search/ src/adp/business/store.py`, `mypy src/adp/`, and the
  full backend test suite (`pytest tests/ --ignore=tests/integration -q`) — confirm zero
  regressions
- [X] T016 Walk through every scenario in `quickstart.md` against a real local Postgres + running
  backend; confirm each scenario's stated expectation holds (including Scenario 4's cascade-fix,
  the one that would fail without T007), then clean up any created test data afterward

---

## Dependencies & Execution Order

- Phase 1 (T001) blocks Phases 2–4.
- Phases 2, 3, and 4 can proceed in parallel once Phase 1 is done (different call sites/files), but
  all three must complete before Phase 5.
- Within each phase: tests before implementation (ART-IV).

## Notes

- T002/T008 together close Ground-Truth Correction #6 for `adp.business.store`'s existing 041
  wiring, not just this feature's own new code — the bead's acceptance criteria ("tests cover the
  new entity types") is read here as covering the entity types this bead is about, all of which
  had zero tests before this feature regardless of when their write hooks were added.
