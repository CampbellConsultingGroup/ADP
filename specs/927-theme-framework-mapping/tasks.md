# Tasks: Theme–Framework Mapping

**Input**: Design documents from `/specs/927-theme-framework-mapping/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV, per `.specify/templates/tasks-template.md`). Test tasks appear before their
implementation counterparts in every user-story phase and must be written and verified to fail first.

**Organization**: Tasks grouped by user story (US1 = tag creation, P1; US2 = read both directions — the
feature's actual point, P1; US3 = tag removal, P2). All three share one table (`theme_framework_links`)
and one low-level helper (`list_framework_ids_for_theme`, Foundational phase) rather than disjoint tables
per story — unlike `925-strategy-compliance-linkage`'s two link types, this feature is a single simple
link, so genuine per-story file disjointness isn't the goal; independent *testability* is, and each story
below is independently verifiable via its own contract test without depending on a sibling story's route.

**Scope note**: data-model-and-API-only (Clarifications, spec.md, 2026-08-26) — no `web/` file is touched
by any task below; UI surfacing is out of scope for this tasks.md (tracked separately as ADP-0md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3, per spec.md's priorities (P1/P1/P2)

## Path Conventions

Single project, existing packages/files only — no new package (plan.md Structure Decision):
- Backend: `src/adp/strategy/{models,store,router}.py` (all exist, extended); `src/adp/compliance/router.py`
  (exists, extended; its `_get_strategy_session()` dependency already exists from 925 — reused, not
  recreated); one new migration
- Backend tests: `tests/unit/strategy/test_theme_framework_links.py` (new),
  `tests/contract/test_theme_framework_links_api.py` (new), `tests/integration/test_theme_framework_links_api.py` (new)

---

## Phase 1: Setup (Migration)

**Purpose**: Database schema every user story depends on.

- [X] T001 Create Alembic migration in `src/adp/store/migrations/versions/037_theme_framework_links.py` (`revision = "037"`, `down_revision = "036"`): one table `theme_framework_links` per data-model.md — `theme_id` VARCHAR(36) FK→`strategic_themes.id` ON DELETE CASCADE (part of composite PK), `framework_id` VARCHAR(36) FK→`regulatory_frameworks.id` ON DELETE CASCADE (part of composite PK), `created_at` TIMESTAMPTZ NOT NULL; `downgrade()` drops the table

**Checkpoint**: Migration applies cleanly (`alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The read-only mirror of `regulatory_frameworks`, the new link table object, and the one
low-level helper all three user stories call.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] In `src/adp/strategy/store.py` (extends the existing `_designs`/`_applications` mirror-table idiom, ADP-d8u.2/925): `_regulatory_frameworks` read-only mirror `sa.Table("regulatory_frameworks", ...)` with columns `id`, `name`; `framework_exists(framework_id: str, session: AsyncSession) -> bool`
- [X] T003 [P] In `src/adp/strategy/store.py`: `_theme_framework_links` DML-only `sa.Table("theme_framework_links", ...)` (columns `theme_id`, `framework_id`, `created_at` — no PK/FK in Python, matching this package's existing convention, constraints live in T001's migration); `list_framework_ids_for_theme(theme_id: str, session: AsyncSession) -> list[str]` — `SELECT framework_id FROM theme_framework_links WHERE theme_id = ? ORDER BY framework_id`, returns the bare id list
- [X] T004 [P] Unit tests in `tests/unit/strategy/test_theme_framework_links.py` for T002/T003, against a seeded SQLite fixture (mirrors `test_control_links.py`'s own `sstore._metadata.create_all()`-style setup, extended to also create the new mirror + link tables): `framework_exists()` returns `True`/`False` correctly; `list_framework_ids_for_theme()` returns `[]` for a theme with no links

**Checkpoint**: Mirror table, link table object, and the shared read helper available; unit tests pass.

---

## Phase 3: User Story 1 - Tag a strategic theme against the regulatory frameworks it touches (Priority: P1) 🎯 MVP

**Goal**: An authorized user can tag an existing Strategic Theme against an existing Regulatory Framework,
with duplicate and missing-target attempts correctly rejected.

**Independent Test**: Tag an existing Theme against an existing Framework via the API and confirm the
POST response reflects it, independent of any GET route (spec.md US1 Acceptance Scenarios; quickstart.md
Scenarios 1 (create half), 2, 3).

### Tests for User Story 1 (write first — ART-IV)

- [X] T005 [P] [US1] Unit tests in `tests/unit/strategy/test_theme_framework_links.py`: `link_theme_framework()` succeeds against a seeded theme/framework pair and the row appears via `list_framework_ids_for_theme()`; raises `DuplicateLinkError` (existing exception, `adp.strategy.store`) on a repeat call for the same pair
- [X] T006 [P] [US1] Contract tests in `tests/contract/test_theme_framework_links_api.py` (SQLite fixture wiring `sstore._metadata` + `cstore`'s `regulatory_frameworks` table together, mirroring `test_strategy_compliance_links_api.py`'s own two-domain fixture precedent): `POST /api/v1/strategy/themes/{theme_id}/frameworks` with a valid `framework_id` → 201, body is `list[str]` containing the linked `framework_id`; repeat POST for the same pair → 409; POST with a nonexistent `framework_id` → 404; POST against a nonexistent `theme_id` → 404

### Implementation for User Story 1

- [X] T007 [P] [US1] In `src/adp/strategy/models.py`: `ThemeFrameworkLinkCreate` model (`framework_id: str`, `extra="forbid"`), mirroring `ObjectiveControlLinkCreate`'s exact shape
- [X] T008 [US1] In `src/adp/strategy/store.py`: `link_theme_framework(theme_id: str, framework_id: str, session: AsyncSession) -> None` — plain `INSERT` into `_theme_framework_links` (T003); catches a unique-violation → raises `DuplicateLinkError` (existing exception, mirrors `link_objective_control`'s exact catch shape) (depends on T003)
- [X] T009 [US1] In `src/adp/strategy/router.py`: `POST /themes/{theme_id}/frameworks` — 404 if `sstore.theme_exists(theme_id, session)` is `False` (existing helper) or `sstore.framework_exists(framework_id, session)` (T002) is `False`; calls `sstore.link_theme_framework` (T008); `DuplicateLinkError` → 409; on success returns `await sstore.list_framework_ids_for_theme(theme_id, session)` (T003) as the response body; under the existing `WRITE_BUSINESS_ARCH` prefix rule (no `enforcement.py` change) (depends on T002, T003, T007, T008)

**Checkpoint**: User Story 1 is fully functional and testable independently — tagging works, with correct 409/404 handling, confirmed by the POST response alone.

---

## Phase 4: User Story 2 - See which frameworks a theme touches, and which themes a framework carries (Priority: P1)

**Goal**: The tag created in User Story 1 is durably visible from both the Theme's own read and a
dedicated reverse lookup from the Framework's side — the actual portfolio-reporting value this feature
exists to deliver.

**Independent Test**: Seed a link directly (fixture or via US1's own endpoint) and confirm it is visible
both from `GET /api/v1/strategy/themes/{theme_id}` and from
`GET /api/v1/compliance/frameworks/{framework_id}/themes`, including the empty-list case for an untagged
theme or framework (spec.md US2 Acceptance Scenarios; quickstart.md Scenarios 1 (read half), 4, 5).

### Tests for User Story 2 (write first — ART-IV)

- [X] T010 [P] [US2] Unit tests in `tests/unit/strategy/test_theme_framework_links.py`: `list_themes_for_framework()` returns the correct `StrategicTheme` set (including one Theme tagged onto multiple Frameworks appearing correctly for each); returns an empty `StrategicThemeListResponse` for a Framework with no tags
- [X] T011 [P] [US2] Contract tests in `tests/contract/test_theme_framework_links_api.py`: after seeding a link, `GET /api/v1/strategy/themes/{theme_id}` response includes `framework_id` in `framework_ids`; `GET /api/v1/strategy/themes` list response reflects it too; `GET /api/v1/compliance/frameworks/{framework_id}/themes` → 200 `StrategicThemeListResponse` containing the theme; a Theme/Framework with zero links returns `framework_ids: []` / `{"items": [], "total": 0}` respectively, not an error; `GET /api/v1/compliance/frameworks/{framework_id}/themes` against a nonexistent `framework_id` → 404

### Implementation for User Story 2

- [X] T012 [US2] In `src/adp/strategy/models.py`: `StrategicTheme` gains `framework_ids: list[str] = []`, mirroring `StrategicObjective.control_ids` exactly (`extra="forbid"` already set, unchanged)
- [X] T013 [US2] In `src/adp/strategy/store.py`: `_row_to_theme` becomes `async def _row_to_theme(row: Any, session: AsyncSession) -> StrategicTheme`, adding `framework_ids=await list_framework_ids_for_theme(row.id, session)` (T003) to its returned object; update its two callers — `list_themes()`'s list comprehension becomes an explicit loop awaiting each call, and `get_theme()`'s `return _row_to_theme(row) if row is not None else None` becomes `return await _row_to_theme(row, session) if row is not None else None`; `create_theme()`'s own manual inline `StrategicTheme(...)` construction gets `framework_ids=[]` added directly (a brand-new theme has no links yet — no query needed); `update_theme()` needs no direct change, it already delegates to `get_theme()` (depends on T003)
- [X] T014 [US2] In `src/adp/strategy/store.py`: `list_themes_for_framework(framework_id: str, session: AsyncSession) -> StrategicThemeListResponse` — reverse lookup (called from `adp.compliance.router`), joins `_theme_framework_links` → `_themes`, mirrors `list_objectives_for_control`'s exact shape (depends on T002, T003, T012)
- [X] T015 [US2] In `src/adp/compliance/router.py`: `GET /frameworks/{framework_id}/themes` — 404 if `sstore.framework_exists(framework_id, strategy_session)` (T002) is `False` via the existing `_get_strategy_session` dependency (925, unchanged); else calls `sstore.list_themes_for_framework` (T014); ungated beyond general platform read access (research.md D4) (depends on T002, T014)

**Checkpoint**: User Stories 1 AND 2 both work independently — a tag can be created and is durably readable from both sides.

---

## Phase 5: User Story 3 - Remove a tag that no longer applies (Priority: P2)

**Goal**: An authorized user can remove an existing tag without affecting the Theme or Framework it
referenced, with a missing-link attempt correctly rejected.

**Independent Test**: Seed a link, remove it via the API, and confirm it disappears from both read
directions established in User Story 2, while the Theme and Framework themselves remain unchanged
(spec.md US3 Acceptance Scenarios; quickstart.md Scenarios 6, 7).

### Tests for User Story 3 (write first — ART-IV)

- [X] T016 [P] [US3] Unit tests in `tests/unit/strategy/test_theme_framework_links.py`: `unlink_theme_framework()` removes an existing link and it no longer appears via `list_framework_ids_for_theme()`; raises `LinkNotFoundError` (existing exception) when the pair isn't linked
- [X] T017 [P] [US3] Contract tests in `tests/contract/test_theme_framework_links_api.py`: after seeding a link, `DELETE /api/v1/strategy/themes/{theme_id}/frameworks/{framework_id}` → 204; repeat `DELETE` for the same pair → 404; after removal, `GET` on both the Theme side and the Framework-side reverse lookup no longer include each other

### Implementation for User Story 3

- [X] T018 [US3] In `src/adp/strategy/store.py`: `unlink_theme_framework(theme_id: str, framework_id: str, session: AsyncSession) -> None` — `DELETE FROM theme_framework_links WHERE theme_id = ? AND framework_id = ?`; raises `LinkNotFoundError` (existing exception) if zero rows affected (depends on T003)
- [X] T019 [US3] In `src/adp/strategy/router.py`: `DELETE /themes/{theme_id}/frameworks/{framework_id}` — calls `sstore.unlink_theme_framework` (T018); `LinkNotFoundError` → 404; on success, bare 204 (no body, mirrors `unlink_objective_control`'s exact response shape); under the existing `WRITE_BUSINESS_ARCH` prefix rule (depends on T018)

**Checkpoint**: All three user stories are independently functional — create, read both directions, and remove.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification that only makes sense once every story above is complete.

- [X] T020 [P] Integration tests (testcontainers PostgreSQL, Docker-gated like every prior COMPLY-0x spec on this branch) in `tests/integration/test_theme_framework_links_api.py`: deleting a linked Strategic Theme cascades to remove the link row without failing the delete or leaving an orphan (quickstart.md Scenario 8); deleting a linked Regulatory Framework does the same from the other side
- [X] T021 Run `ruff check src/adp/strategy/ src/adp/compliance/` and `mypy src/adp/strategy/ src/adp/compliance/`; fix any issues
- [X] T022 Walk through every scenario in `quickstart.md` against a real local Postgres + running backend; confirm each `curl` sequence's stated expectation holds, then clean up any test Theme/Framework/link created during the walkthrough

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational phase completion.
  - US1 (Phase 3) has no dependency on US2/US3.
  - US2 (Phase 4) can be built and tested with a link seeded directly by a fixture, independent of US1's
    own route existing — but in practice ships after US1 since both are P1 and the natural build order is
    create-then-read.
  - US3 (Phase 5) removes what US1 creates; independently testable via a fixture-seeded link, same as US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation.
- Store-layer functions before router endpoints.
- Story complete before moving to the next priority.

### Parallel Opportunities

- T002 and T003 (Phase 2) touch the same file (`store.py`) but different, non-overlapping additions —
  safe to treat as parallel authoring, sequential commit.
- Within each story, the two test tasks (unit + contract) are marked `[P]` — different files, no
  dependency on each other.
- T007 (`models.py`) is `[P]` relative to T008/T009 (`store.py`/`router.py`) within US1.

---

## Parallel Example: User Story 1

```bash
# Launch both test tasks for User Story 1 together:
Task: "Unit tests for link_theme_framework in tests/unit/strategy/test_theme_framework_links.py"
Task: "Contract tests for POST /themes/{id}/frameworks in tests/contract/test_theme_framework_links_api.py"

# ThemeFrameworkLinkCreate (models.py) can be authored alongside link_theme_framework (store.py):
Task: "Add ThemeFrameworkLinkCreate in src/adp/strategy/models.py"
Task: "Add link_theme_framework in src/adp/strategy/store.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (migration).
2. Complete Phase 2: Foundational (mirror table, link table, shared helper).
3. Complete Phase 3: User Story 1 (tag creation).
4. **STOP and VALIDATE**: confirm tagging works end-to-end via the POST route alone.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → tag creation works → validate independently.
3. User Story 2 → both read directions durable → validate independently (this is the point at which the
   feature delivers its actual "coarse portfolio rollup" value).
4. User Story 3 → removal works → validate independently.
5. Polish → cascade-delete integration coverage, lint/type clean, full quickstart walkthrough.

## Notes

- No `[P]` conflicts within a story touch the same lines of the same file — verify before marking a pair
  `[P]` if this task list is revised.
- `[Story]` label maps each task to its user story for traceability back to spec.md.
- Commit after each task or logical group; stop at any checkpoint to validate a story independently.
