# Tasks: Diagram Types Beyond C4

**Feature**: ADP-SPEC-046 | **Branch**: `046-diagram-type-support`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md) · **Data model**: [data-model.md](./data-model.md) · **Contracts**: [contracts/diagrams-api.md](./contracts/diagrams-api.md) · **Quickstart**: [quickstart.md](./quickstart.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]** = parallelizable (distinct file, no dependency on an incomplete task).
- **[US#]** = user-story phase task. Setup / Foundational / Polish carry no story label.
- Tests are **MANDATORY** (ART-IV): each phase's tests precede its implementation, written to fail first — including for the vendored code (Foundational T003/T004): the *tests* are translated from the sibling project's own existing suite, but they must still be confirmed failing against ADP's own (not-yet-populated) `web/src/diagrams/core/` before the vendored source lands, exactly like any other new code in this codebase.

## Path Conventions

New backend package `src/adp/diagrams/` (models.py, store.py, router.py) + one migration. New frontend module `web/src/diagrams/`, split into `core/` (vendored, low-diff copy of `/home/jmuir/projects/canvas/packages/diagram-core/src/`) and `editor/` (vendored+adapted from `canvas/apps/web/src/canvas/`), plus two new ADP-authored pages and an API client. Tests in `tests/unit/diagrams/`, `tests/authz/test_diagram_permissions.py`, `tests/contract/test_diagrams_api_contract.py`, and `web/src/diagrams/**/*.test.ts(x)`.

> **Vendoring note**: T004 and T013 copy externally-authored source verbatim (adjusting only relative import paths) — they are not "write new code" tasks in the usual sense. Do not refactor, rename, or restyle the vendored files during these tasks; keeping them a faithful, low-diff mirror of the upstream source is the explicit point (research.md Decision 6), so a future re-sync from `/home/jmuir/projects/canvas` stays tractable. Any ADP-specific adaptation happens in the *new* files around the vendored core (`DiagramEditorPage.tsx`, `api.ts`, `ExportAction.tsx`), never inside the vendored files themselves.

> **File-contention note**: `src/adp/diagrams/router.py` grows across all three user-story phases (US1 adds create/read/update, US2 adds export, US3 adds list/delete) — sequential within that file across phases, not `[P]`. The three user stories are otherwise independent of each other (each adds distinct endpoints/pages) and can be built in any order after Foundational, though P1→P2→P3 is the natural sequence since it matches the spec's own priority ordering and MVP framing.

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Create the `adp.diagrams` package skeleton (docstring only, referencing spec.md/data-model.md) in src/adp/diagrams/__init__.py
- [x] T002 [P] Create web/src/diagrams/README.md flagging `core/` as vendored, low-diff source from `/home/jmuir/projects/canvas/packages/diagram-core` (research.md Decision 1/6) — do not hand-edit without a documented reason; explains where `editor/` came from and what was deliberately excluded (ViolationsPanel.tsx, ExportMenu.tsx's backend-coupled fetch)

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — all three stories build on the vendored diagram-core library, the `diagrams` table, and RBAC existing first.

- [x] T003 [P] Unit test: vendored DSL parse/serialize roundtrip for all 5 registered families (flowchart, sequence, erd, uml, architecture) + `escapeXml` safety in the SVG renderer for node/edge/container labels containing markup-like text, translated from `/home/jmuir/projects/canvas/packages/diagram-core`'s own existing test suite — in web/src/diagrams/core/dsl/families.test.ts — confirmed failing (`Failed to resolve import "./flowchart-parser"`) then passing (9/9)
- [x] T004 Vendored `packages/diagram-core/src/` (`model/`, `dsl/`, `libraries/`, `render/`, `standards/`) unmodified into web/src/diagrams/core/ — import paths needed no adjustment (ADP's `moduleResolution: "bundler"` + `allowImportingTsExtensions` already tolerates the vendored `.js`-suffixed relative imports as-is); added `@dagrejs/dagre` and `yaml` to web/package.json as new runtime dependencies. `tsc --noEmit` clean on first attempt — in web/src/diagrams/core/, web/package.json
- [x] T005 [P] Unit test: Pydantic model validation — blank `title` rejected, `dsl_source` over 50,000 characters rejected, `diagram_type` restricted to the 5 supported literal values, `DiagramSummary` omits `dsl_source` — in tests/unit/diagrams/test_diagrams_models.py — confirmed failing (`ModuleNotFoundError`) then passing (16/16)
- [x] T006 Implemented `Diagram`, `DiagramCreate`, `DiagramUpdate`, `DiagramSummary`, `DiagramListResponse` (data-model.md §2) — in src/adp/diagrams/models.py
- [x] T007 [P] Unit test: store CRUD (create/get/list/update/delete) against a SQLite-backed `adp.diagrams.store`, explicitly asserting no `design_id` column/FK exists on the table (FR-011) — in tests/unit/diagrams/test_diagrams_store.py — confirmed failing (`ImportError`) then passing (10/10)
- [x] T008 Alembic migration 024 (`diagrams` table, data-model.md §1, `down_revision = "023"`) + implemented store.py CRUD functions — in src/adp/store/migrations/versions/024_diagrams.py, src/adp/diagrams/store.py. Verified applying cleanly against real dev Postgres (`alembic upgrade head` → `024 (head)`). `ruff`/`mypy` clean.
- [x] T009 [P] Unit test: `WRITE_DIAGRAM` is granted to Solution/Technical/Enterprise Architect and Platform Admin, denied to Reviewer; `requires_confirmation(WRITE_DIAGRAM) == False`. **Deviation from the original task path**: `tests/authz/test_permissions.py` turned out to have hard completeness gates (`test_permission_table_covers_all_roles_and_actions`, `test_requires_confirmation_covers_all_actions`) asserting *every* `ActionType` is enumerated — a new isolated test file would have left those gates broken. Extended the existing `_EXPECTED`/`_CONFIRMATION_EXPECTED` tables and the `PERMISSIONS_VERSION` assertion in place instead — in tests/authz/test_permissions.py — confirmed failing (`AttributeError: ActionType has no attribute WRITE_DIAGRAM`) then passing (181/181 across the whole authz suite)
- [x] T010 Added `ActionType.WRITE_DIAGRAM`; granted explicitly to `SOLUTION_ARCHITECT`/`TECHNICAL_ARCHITECT` (mirroring exactly how `WRITE_APPLICATION` is granted); confirmed `ENTERPRISE_ARCHITECT`/`PLATFORM_ADMIN` receive it automatically via their existing wildcard grants (`frozenset(ActionType) - {...}` / `frozenset(ActionType)`), no code change needed for either; `PERMISSIONS_VERSION` `1.7.0` → `1.8.0` — in src/adp/authz/roles.py, src/adp/authz/permissions.py. `ruff`/`mypy` clean.

**Checkpoint**: the vendored library, the data model, and RBAC all exist and are directly testable; nothing is wired to HTTP yet.

---

## Phase 3: User Story 1 - An architect creates a non-C4 diagram (Priority: P1) 🎯 MVP

**Goal**: An architect can create a diagram of any of the 5 supported types, author its content interactively, save it, and reopen it later with content intact.
**Independent Test**: create a diagram of each type, author content, save, reopen, and confirm the content matches what was last saved.

### Tests for User Story 1 (MANDATORY — ART-IV)

- [x] T011 [US1] Contract test: `POST /api/v1/diagrams` creates and persists a diagram for each of the 5 types; `GET /api/v1/diagrams/{id}` retrieves it with content intact; `PUT /api/v1/diagrams/{id}` updates `title`/`dsl_source` (partial update, `diagram_type` immutable); `422` on blank title, oversized `dsl_source`, or an unsupported `diagram_type` — in tests/contract/test_diagrams_api_contract.py — confirmed failing (`ImportError`) then passing (12/12)

### Implementation for User Story 1

- [x] T012 [US1] Implemented `POST`/`GET (single)`/`PUT` endpoints in router.py; registered the router in `adp.api.app`; added the `/api/v1/diagrams` prefix rule to `adp.authz.enforcement`'s route→action map (WRITE_DIAGRAM for all mutating methods, reads ungated) — in src/adp/diagrams/router.py, src/adp/api/app.py, src/adp/authz/enforcement.py. Route-completeness gate (tests/authz/test_enforcement.py) confirmed passing with the new router registered (32/32). `ruff`/`mypy` clean.
- [x] T013 [US1] Vendored+adapted the editor components (`Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`) from `canvas/apps/web/src/canvas/` into web/src/diagrams/editor/, plus two small portable UI dependencies (`ui/Icon.tsx`, `ui/Modal.tsx`) discovered during vendoring — explicitly excluding `ViolationsPanel.tsx` (Standards system, deferred per FR-009) and `ExportMenu.tsx`'s backend-coupled fetch (rebuilt separately in US2, T019). **Real adaptation beyond import-path rewriting**: `Canvas.tsx` imported `api.getLibraryIcons()` from the sibling project's own Fastify-backend-coupled client (fetches admin-uploaded icon libraries over the network) — replaced with a new local `icon-libraries.ts` that resolves icons from the already-vendored static manifests (AWS/Azure/generic) via `loadLibrary()`, since ADP has no admin-icon-library-upload surface in v1. `@canvas/diagram-core` package-alias imports rewritten to relative `../core/index.js`. **Known follow-up, not blocking**: the sibling project's 4-file design-token CSS system (`tokens.css`/`base.css`/`components.css`/`layout.css`) was NOT vendored — `Canvas.tsx` will render functionally but not with matching visual polish until that's addressed in a follow-up. `tsc --noEmit` clean on first attempt after adjustments.
- [x] T014 [US1] Built `DiagramEditorPage.tsx` (type picker for new diagrams → `Canvas`/`DslPanel` → save) and `api.ts` (typed client, reusing the shared `apiGet`/`apiMutation` helpers from `web/src/api/client.ts` — deliberately not a raw `fetch()`, exactly the bug class documented in this project's own history, ADP-cm9). Along the way, corrected an assumption about `DslPanel`'s actual props (`{dsl, parseErrors, onApply}`, consuming `useDslSync`'s output directly, not `{model, onModelChange}` as first guessed) — in web/src/diagrams/DiagramEditorPage.tsx, web/src/diagrams/api.ts
- [x] T015 [US1] Component test: create → author → save, and reopen with content intact → update (not create), through `DiagramEditorPage` — in web/src/diagrams/DiagramEditorPage.test.tsx — confirmed failing then passing (3/3; one test's first attempt used `userEvent.type()` with a `{Enter}` key sequence into the DSL textarea, which didn't compose reliably — switched to a direct `fireEvent.change` value-set, not a change to the underlying implementation, which T003 already proved correct). `tsc --noEmit` clean.
- [x] T016 [US1] Manually ran quickstart.md Scenarios 1–3 against a real local dev stack (restarted the backend, real dev Postgres): created an empty flowchart diagram, confirmed `dsl_source == ""`; authored a 5-node flowchart via `PUT`, confirmed content persisted through a subsequent `GET`; created one diagram of each remaining type (sequence, erd, uml, architecture), all succeeded. Verification data left in place (no delete endpoint until US3/T022).

**Checkpoint**: MVP — an architect can create, author, save, and reopen a diagram of any of the 5 supported types, entirely within ADP.

---

## Phase 4: User Story 2 - An architect renders a diagram to share or embed (Priority: P2)

**Goal**: A saved diagram can be rendered to a static image (SVG client-side, PNG via a new backend endpoint) that reflects its current content.
**Independent Test**: create a diagram, request a rendering, confirm the output visually matches current content; edit and re-render, confirm the output updates (not stale).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [x] T017 [US2] Contract test: `POST /api/v1/diagrams/{id}/export` converts a submitted SVG string to PNG via `cairosvg` (research.md Decision 3, verified via the real PNG magic-byte header); `404` for a nonexistent diagram id; `422` for a malformed SVG string — in tests/contract/test_diagrams_api_contract.py — passed immediately (3/3; the export endpoint was already implemented in T012 as part of writing router.py's full file, not deferred) — 15/15 across the whole contract file

### Implementation for User Story 2

- [x] T018 [US2] Export endpoint (accepts `{"svg": "..."}`, returns `image/png` bytes) — already implemented as part of T012's router.py — in src/adp/diagrams/router.py
- [x] T019 [US2] Built `ExportAction.tsx` (new, ADP-authored — NOT a port of the sibling's `ExportMenu.tsx`): renders the current model via the vendored `svg-renderer.ts` client-side (SVG download, zero network call), and POSTs the rendered SVG to the new export endpoint for PNG. Wired into `DiagramEditorPage.tsx` via a new `savedId` state (distinct from the `diagramId` prop) so export becomes available immediately after a brand-new diagram's first save, without a page navigation — in web/src/diagrams/editor/ExportAction.tsx, web/src/diagrams/DiagramEditorPage.tsx. `tsc --noEmit` clean; all 12 frontend diagrams tests still passing.
- [x] T020 [US2] Manually ran quickstart.md Scenario 6 against the real local dev stack: `POST /api/v1/diagrams/{id}/export` with a hand-written SVG returned real PNG bytes (`file` confirmed "PNG image data, 100 x 100").

**Checkpoint**: both authoring (US1) and rendering (US2) work independently and together.

---

## Phase 5: User Story 3 - An architect finds a previously created diagram (Priority: P3)

**Goal**: All diagrams a user has access to are browsable in one listing (title, type, last-updated) and reopenable into the editor; a diagram can be deleted (FR-007).
**Independent Test**: create several diagrams of different types, confirm all appear in the listing, reopen one from it, then delete one and confirm it's gone from both the listing and direct lookup.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [x] T021 [US3] Contract test: `GET /api/v1/diagrams` lists all diagrams across every type in the `DiagramSummary` shape (no `dsl_source`); `DELETE /api/v1/diagrams/{id}` removes a diagram (`204`), and a subsequent `GET`/list confirms it's gone (`404` / absent from the listing) — in tests/contract/test_diagrams_api_contract.py — passed immediately (5/5; list and delete were already implemented in T012 as part of writing router.py's full file) — 18/18 across the whole contract file

### Implementation for User Story 3

- [x] T022 [US3] `GET (list)` and `DELETE` endpoints — already implemented as part of T012's router.py — in src/adp/diagrams/router.py
- [x] T023 [US3] Built `DiagramListPage.tsx` (listing with title/type/last-updated, reopen via an `onOpen(id)` callback, delete action with reload) — in web/src/diagrams/DiagramListPage.tsx
- [x] T024 [US3] Component test: `DiagramListPage` renders items across all 3 sampled types, `onOpen` called with the correct id on reopen, delete removes an item from the list, empty state renders with none — in web/src/diagrams/DiagramListPage.test.tsx — confirmed failing (`Invalid Chai property: toBeInTheDocument` — `@testing-library/jest-dom` isn't a project dependency, discovered here and fixed by using vanilla `getByText`-throws-if-missing / `queryByText(...) === null` assertions instead of introducing a new dependency) then passing (4/4) — 16/16 across the whole diagrams frontend suite. `tsc --noEmit` clean.
- [x] T025 [US3] Manually ran quickstart.md Scenarios 5 and 7 against the real local dev stack: `GET /api/v1/diagrams` listed all 5 previously-created diagrams across every type; `DELETE` returned 204 and a subsequent `GET` returned 404. All verification data (from T016/T025) cleaned up afterward — 0 diagrams remaining.

**Checkpoint**: all three user stories independently functional — create/author/save, render, and browse/delete.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T026 [P] Added a "Diagram types beyond C4" section to RUNBOOK.md: API usage examples, RBAC note, the vendored-code re-sync process (manual, on-demand — per research.md Decision 1, points at `web/src/diagrams/README.md`), and the known CSS-polish follow-up — in RUNBOOK.md
- [x] T027 Full regression: `pytest tests/ --ignore=tests/integration -q` → **1136 passed** (was 1086; +50 new tests: 16 model + 10 store + 18 contract + 6 authz-table additions); `ruff check src/ tests/` → clean; `mypy src/` → clean; `cd web && npm run test:run` → **124 passed across 21 files** (was ~108 before this feature); `cd web && npm run tsc` → clean. **Found and documented a real pre-existing gap, not caused by this feature**: `npm run lint` fails project-wide — `web/` has no `eslint.config.js` at all (confirmed via empty git history for that path); skipped as out of scope, `tsc`+tests are this feature's available frontend quality gates. **Also found and fixed a real inaccuracy in quickstart.md's own Scenario 8**: `web/src/canvas/` (C4) has no dedicated test files at all to filter to — corrected the scenario to run the full suites rather than a non-existent filtered subset.
- [x] T028 Confirmed no `adp-generate` schema drift — `adp-generate --check` exits 0
- [x] T029 [P] Updated CLAUDE.md's Recent Changes entry and AGENTS.md's status blurb for 046 to reflect implementation (all three user stories, vendoring approach, both pre-existing/inaccuracy findings, verification results) — in CLAUDE.md, AGENTS.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Ph1)** → **Foundational (Ph2)** → **User Stories (Ph3–5)** → **Polish (Ph6)**.
- Foundational (T003–T010) blocks all three stories — none has anything to build on without the vendored library, the `diagrams` table, or RBAC.
- **User Stories 1, 2, and 3 are independent of each other** (each adds distinct router endpoints and distinct frontend pages) — unlike some prior features in this codebase, no story here strictly requires a previous one's *implementation* to exist first, though P1 → P2 → P3 is the natural build order matching the spec's own priorities and this plan's MVP framing (US2's `ExportAction` and US3's `DiagramListPage` are more useful with US1's `DiagramEditorPage` already in place to link to/from, even though nothing technically blocks building them first).
- No dependency on any other in-flight feature; no change to any existing table or router.

### Parallel opportunities

- Setup: T001 and T002 are both `[P]` (distinct files).
- Foundational: T003 (own file tree) is `[P]` relative to T005/T007/T009 (their own files) — all four test-writing tasks can proceed in parallel; T004/T006/T008/T010 (implementation) are each sequential to their own preceding test, but independent *of each other* across the vendoring/models/store+migration/RBAC tracks.
- User Story 1: T011 (contract test, own file) precedes T012; T013 (vendoring, own files) is `[P]` relative to T012 (backend); T014 depends on both T012 and T013 existing.
- User Story 2: T017 (own file, though shared with US1/US3's contract test file — sequential to T011/T021 within that file) precedes T018; T019 depends on T018.
- User Story 3: T021 (shared contract test file — sequential to T011/T017) precedes T022; T023 depends on T022.
- Polish: T026 and T029 are `[P]` (distinct files, no dependency on T027/T028's outcome to be written, though T027/T028 should still run before considering the feature done).

## Implementation Strategy

- **MVP = User Story 1** (Phase 3): an architect can create, author, save, and reopen a diagram of any of the 5 supported types. Ship and demo before proceeding — this alone closes the primary gap the spec exists to address (Enterprise/Business Architects having no home in ADP for non-C4 diagram types).
- **Then User Story 2** (Phase 4): rendering — the smaller of the two remaining stories, and the one with the real cross-language architecture decision already resolved in planning (client-side SVG, `cairosvg`-backed PNG).
- **Then User Story 3** (Phase 5): browse/manage — lowest priority per the spec's own framing (a diagram is only as useful as being findable later, but authoring/rendering come first).
- **The additive scope boundary is load-bearing, not incidental**: per the spec's Assumptions, this feature makes zero changes to `ArchitectureDescription`, `web/src/canvas/C4Canvas.tsx`, or `adp.renderer` — T027's explicit regression check against the existing C4/canvas test suites (SC-003) is not a formality, it's verifying the central architectural claim of the whole feature.

## Summary

- **Total tasks**: 29 across 6 phases.
- **Per story**: US1=6 (T011–T016), US2=4 (T017–T020), US3=5 (T021–T025); Setup=2, Foundational=8, Polish=4.
- **MVP scope**: User Story 1 (T001–T016) — create/author/save/reopen for all 5 diagram types, end to end.
- **Tests**: mandatory per phase (ART-IV) — written to fail first, including translated tests for vendored code (T003), which must fail against ADP's own empty `web/src/diagrams/core/` before the vendored source lands.
