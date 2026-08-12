---

description: "Task list for C4 Design View"
---

# Tasks: C4 Design View

**Input**: Design documents from `/specs/054-c4-design-view/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/elements-api-contract.md, quickstart.md

**Tests**: Mandatory (ART-IV) — every new backend endpoint and every new frontend module gets
failing tests before implementation, in every phase below.

**Organization**: Grouped by user story (spec.md P1/P2/P3). Note up front: only **User Story 1**
depends on this feature's new backend endpoints — User Stories 2–4 read/reuse data and endpoints
that already exist (level-filtering is a pure frontend concern over already-loaded elements;
technology-tag editing and layout position load/save both reuse *existing, unmodified* endpoints
per research.md Decisions 3 and 9). All four stories share the Foundational phase's adapter and
view shell, but only US1 is gated on Foundational **and** its own new backend work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's US1/US2/US3/US4

## Path Conventions

Backend: `src/adp/api/routers/`, `src/adp/authz/`, `tests/`. Frontend: `web/src/canvas-v2/`
(new), `web/src/api/designs.ts` (existing, extended), `web/src/ui/`, `web/src/shell/`,
`web/src/App.tsx`. Repo root: `/home/jmuir/projects/ADP`.

---

## Phase 1: Setup

**Purpose**: Scaffold the new backend router and frontend module so later tasks have somewhere to
land, and prove the wiring works before any real logic exists.

- [X] T001 [P] Create `src/adp/api/routers/elements.py` with the router declaration
  (`APIRouter(prefix="/api/v1/designs", tags=["elements"])`), `_get_design_store`/`_get_actor`
  helpers copied verbatim from `tags.py`'s own pattern (`tags.py:32-42`), and the `next_element_id`/
  `next_relationship_id` helpers per data-model.md's max-plus-one formula (research.md Decision 2)
  — no endpoints yet.
- [X] T002 [P] Create the `web/src/canvas-v2/` directory with an empty `c4Adapter.ts` (type
  signatures only: `elementsToC4Model(elements, relationships, level, positions): DiagramModel` and
  its reverse-direction helpers per data-model.md's mapping table) — no implementation yet.
- [X] T003 Mount the new (still-empty) router: add `elements` to the `from adp.api.routers import
  (...)` block and `app.include_router(elements.router)` in `src/adp/api/app.py`, matching every
  other router's existing mount call exactly.

**Checkpoint**: New backend router is live (returns 404 for any route, since none exist yet — this
just proves the mount doesn't break app startup); new frontend module exists.

---

## Phase 2: Foundational

**Purpose**: The adapter (Element/Relationship ⇄ DiagramModel mapping) and a minimal view shell,
reachable via a genuinely new nav entry — the shared prerequisite every user story phase below
builds on, independent of which story's own logic lands first.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Implement `elementsToC4Model` in `web/src/canvas-v2/c4Adapter.ts`: `Element[]`/
  `Relationship[]` + `C4Level` → `DiagramModel`, reusing `web/src/canvas/c4-filter.ts`'s
  `filterElementsForLevel`/`filterRelationshipsForLevel` unchanged (data-model.md's level table),
  mapping `Element.kind` directly onto `DiagramNode.role` (exact string match, no translation
  table — data-model.md's kind/role/shape table) and `positions` (when supplied) onto
  `DiagramNode.position`.
- [X] T005 [P] Implement the reverse-direction pure mapping functions in `c4Adapter.ts`
  (`diagramNodeToElementCreate`/`diagramEdgeToRelationshipCreate`/`diagramNodeToElementUpdate`) —
  pure data shaping only, no API calls here (research.md Decision 6: a `cylinder`/`stadium` shape
  maps back to its plain base `role`, never a Db/Queue distinction the canonical model can't hold;
  `DiagramModel.containers` are never mapped to anything — research.md Decision 1).
- [X] T006 Create `web/src/canvas-v2/C4DesignView.tsx`: loads a design via the existing `useDesign`
  hook (`web/src/api/designs.ts`), renders the reused, unmodified `Canvas.tsx` with the model
  produced by T004 — read-only at this point (no `onChange` wiring yet), proving the adapter's
  forward direction renders correctly end to end.
- [X] T007 Add the new, separate entry point (research.md Decision 8 — additive, not a nav swap):
  `"canvas-v2"` added to the `AppView` union (`web/src/shell/index.ts`); a new `NavDef` entry
  (e.g. `{ view: "canvas-v2", label: "C4 Design (Preview)", icon: "sol" }`) appended to
  `DESIGN_SCOPED` and a matching `TITLES` entry in `web/src/ui/AppShell.tsx`; a new
  `if (view === "canvas-v2") return <C4DesignView designId={currentDesignId} />;` branch in
  `web/src/App.tsx`'s `renderPage()`, alongside (not replacing) the existing `"canvas"` branch.

**Checkpoint**: A design's elements render, read-only, via the new component, reachable through a
genuinely new nav item that coexists with the unchanged "Canvas" item. User story phases can
proceed.

---

## Phase 3: User Story 1 - Build and edit a design's architecture visually (Priority: P1) 🎯 MVP

**Goal**: Add elements, draw relationships, and delete either — entirely by direct canvas
interaction, committed immediately to the design's real record. The concrete fix for
ADP-914.1–.4.

**Independent Test**: Open an existing design; add two new elements and a relationship between
them entirely by direct manipulation on the canvas; confirm both elements and the relationship are
present when the design is reloaded (spec.md's own Independent Test for this story).

### Tests for User Story 1 (MANDATORY — ART-IV)

- [X] T008 [P] [US1] Create `tests/unit/elements/test_elements_models.py` (new directory, mirrors
  `tests/unit/diagrams/test_diagrams_models.py`'s structure): `ElementCreate`/`ElementUpdate`/
  `RelationshipCreate` accept valid input and reject blank/oversized `name`/`label`, unknown
  `kind` values, and unknown fields (`extra="forbid"`).
- [X] T009 [P] [US1] Create `tests/unit/elements/test_id_generation.py`: `next_element_id`/
  `next_relationship_id` produce `ELM-001`/`REL-001` for an empty design, `ELM-004` after
  `ELM-001..003` exist, and — the actual point of research.md Decision 2 — a **non-colliding** id
  when a gap exists (e.g. `ELM-001`, `ELM-003` present after `ELM-002` was deleted → next id is
  `ELM-004`, not the colliding `ELM-003` a naive `len+1` formula would produce).
- [X] T010 [US1] Create `tests/contract/test_elements_api_contract.py` (mirrors
  `tests/contract/test_diagrams_api_contract.py`'s fixture/client setup): covers all 5 endpoints
  per contracts/elements-api-contract.md — create/rename/delete element, create/delete
  relationship, the cascade-delete-relationships-on-element-delete case (confirm the deleted
  element's relationships are gone from a subsequent `GET`, and that this does **not** raise
  `validate_references`' referential-integrity error), 404s for unknown design/element/
  relationship ids, 422s for invalid `kind`/blank `name`/nonexistent `source`/`target`, and that
  `PATCH .../elements/{id}` never alters `description`/`satisfies`/`provenance`/`tags`/
  `technology_metadata` (FR-011).

### Implementation for User Story 1

- [X] T011 [US1] Implement `POST /api/v1/designs/{design_id}/elements` in
  `src/adp/api/routers/elements.py`: validate `ElementCreate`, generate the id via T001's
  `next_element_id`, append the new `Element`, write an `AuditEntry` (`action="create-element"`),
  `store.save()`, return the created `Element` — mirroring `tags.py`'s exact fetch→mutate→audit→
  save structure (`tags.py:149-239`).
- [X] T012 [US1] Implement `PATCH /api/v1/designs/{design_id}/elements/{element_id}` in
  `elements.py`: update only `name`, explicitly preserving every other field (FR-011), audit
  `action="update-element"`.
- [X] T013 [US1] Implement `DELETE /api/v1/designs/{design_id}/elements/{element_id}` in
  `elements.py`: remove the element, cascade-remove every `Relationship` whose `source`/`target`
  references it (required — `ArchitectureDescription`'s `model_validator` calls
  `validate_references`, which raises on any dangling relationship endpoint), one audit entry per
  removed entity (`"delete-element"` + one `"delete-relationship"` per cascaded relationship, per
  contracts/elements-api-contract.md).
- [X] T014 [P] [US1] Implement `POST /api/v1/designs/{design_id}/relationships` in `elements.py`:
  validate `source`/`target` resolve to real elements in the design (422 if not), generate the id
  via `next_relationship_id`, audit `action="create-relationship"`.
- [X] T015 [P] [US1] Implement `DELETE /api/v1/designs/{design_id}/relationships/{relationship_id}`
  in `elements.py`: no cascade needed, audit `action="delete-relationship"`.
- [X] T016 [US1] Add all 5 new `(method, path) -> ActionType.WRITE_DESIGN` entries to
  `src/adp/authz/enforcement.py`'s existing per-route dict, matching the designs domain's
  established exact-path convention (`("PUT", "/api/v1/designs/{design_id}/elements/{element_id}/
  tags")`'s own entry style — contracts/elements-api-contract.md's exact list).
- [X] T017 [P] [US1] Create `web/src/canvas-v2/c4Adapter.test.ts`: round-trip tests for T004/T005's
  mapping functions (mirrors `families.test.ts`/`c4.test.ts`'s normalize-and-compare pattern) —
  a `Person`/`System`/`Container`/`Component` mix maps to the correct `role`/`shape` and back;
  confirm the Decision 6 narrowing (a `cylinder`-shaped node maps back to its plain `role`, no
  Db-variant field exists to lose data from since canonical `Element` never had one).
- [X] T018 [P] [US1] Create `web/src/canvas-v2/reconcile.test.ts`: given a previous and a new
  `DiagramModel`, confirm the correct mutation hook is called exactly once per actual change — one
  added node → one create-element call; one removed node → one delete-element call; a node with
  the same id but changed label → one update-element call; one added/removed edge → one create/
  delete-relationship call; no calls at all when nothing changed; after a create-element call
  resolves, the temporary Canvas-generated id is replaced with the real returned `ELM-NNN` id in
  the model passed back to `Canvas.tsx`.
- [X] T019 [US1] Create `web/src/canvas-v2/C4DesignView.test.tsx`: adding a shape via the reused
  toolbar fires the create-element mutation and the new element renders with its real backend id;
  deleting a selected element removes it and any attached relationship from the canvas and fires
  the corresponding delete calls (spec.md Acceptance Scenarios 1–4).

### Implementation for User Story 1 (frontend)

- [X] T020 [P] [US1] Add `useCreateElement`/`useUpdateElement`/`useDeleteElement`/
  `useCreateRelationship`/`useDeleteRelationship` mutation hooks to `web/src/api/designs.ts`,
  mirroring `useSaveLayout`'s exact shape (`designs.ts:47-54`) — added alongside, **not**
  replacing, the existing `usePlaceElement`/`useDrawRelationship` (which stay exactly as they are,
  still used by the untouched `C4Canvas.tsx`).
- [X] T021 [US1] Implement `web/src/canvas-v2/reconcile.ts`'s diff-and-fire logic (T018's tests
  passing), calling T020's new hooks. Depends on T020.
- [X] T022 [US1] Wire `C4DesignView.tsx`'s `Canvas` `onChange` callback to the reconciler (T006's
  shell gains real persistence), completing the add/edit/delete round trip end to end. Depends on
  T021.

**Checkpoint**: User Story 1 fully functional and independently testable — run
`pytest tests/unit/elements/ tests/contract/test_elements_api_contract.py -q` and
`cd web && npx vitest run src/canvas-v2/` and quickstart.md Scenarios 1–2.

---

## Phase 4: User Story 2 - Work at the right level of detail (Priority: P2)

**Goal**: Move between Context/Container/Component levels on one shared model — the level
selector only changes what's shown (spec.md FR-006/FR-007/FR-015).

**Independent Test**: Open a design containing people, systems, containers, and components;
switch between all three levels; confirm each shows only the appropriate elements, and that an
edit at one level is visible at another (spec.md's own Independent Test). Independent of User
Story 1's new backend endpoints — only needs Foundational (elements already exist in the design
being tested, however they got there).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T023 [P] [US2] Extend `C4DesignView.test.tsx`: given a design with elements of every kind,
  selecting each level shows exactly the element-kind subset data-model.md's level table
  specifies; renaming an element at one level and switching to another level where it's also
  visible shows the new name (spec.md Acceptance Scenarios 1–4).

### Implementation for User Story 2

- [X] T024 [US2] Add a level selector to `C4DesignView.tsx` (mirrors `Workspace.tsx`'s existing
  `LEVELS` array/button-row convention, `Workspace.tsx:17-21`), re-deriving the `DiagramModel` via
  T004's adapter — filtered for the newly selected level — from the same underlying `Element[]`/
  `Relationship[]` state on every level change, never a separate per-level copy (FR-015).

**Checkpoint**: User Stories 1 AND 2 both work independently — run quickstart.md Scenario 3.

---

## Phase 5: User Story 3 - Keep working technology tagging and export, uninterrupted (Priority: P2)

**Goal**: Technology-metadata editing and export (locked-theme render + CALM) keep working exactly
as they do today — both via endpoints this feature reuses verbatim, not rebuilds. Independent of
User Story 1's new endpoints — reuses existing, already-working ones (research.md Decisions 3, 9).

**Independent Test**: On a design with existing technology metadata, confirm it's still visible
and editable; export the design and confirm the rendered image uses the platform's official style
and the CALM export still succeeds (spec.md's own Independent Test).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T025 [P] [US3] Extend `C4DesignView.test.tsx`: an element picker lists every element in the
  design; selecting one renders `InspectionPanel` with its correct technology metadata; editing it
  via `TechnologyEditor` calls the *existing* `useUpdateElementTags` hook (already covered by its
  own tests — this confirms wiring only, not re-testing that hook's own behavior).
- [X] T026 [P] [US3] Extend `C4DesignView.test.tsx`: the Export actions call
  `POST /designs/{id}/render` and `GET /designs/{id}/export/calm` (mocked) with the current design
  id — confirming no new export logic exists, matching research.md Decision 9.

### Implementation for User Story 3

- [X] T027 [US3] Add an element picker (a simple list of the design's elements, independent of
  canvas selection — research.md Decision 4) to `C4DesignView.tsx`, driving `InspectionPanel.tsx`/
  `TechnologyEditor.tsx` completely unchanged.
- [X] T028 [P] [US3] Add Export actions (render + CALM) to `C4DesignView.tsx`, calling the
  existing endpoints directly — mirroring `Workspace.tsx`'s own existing `handleExportCalm`
  implementation (`Workspace.tsx:30-51`) rather than writing new export logic.

**Checkpoint**: User Stories 1–3 all work independently — run quickstart.md Scenario 4.

---

## Phase 6: User Story 4 - Previous work isn't lost in the transition (Priority: P3)

**Goal**: A design's previously-saved layout positions carry over into the new view rather than
resetting to auto-layout (spec.md FR-013) — via the same existing, unmodified layout endpoints
C4Canvas already calls (research.md Decision 3). Independent of User Story 1's new endpoints.

**Independent Test**: Open, in the new view, a design that already had a saved visual arrangement;
confirm elements appear in their previously-arranged positions (spec.md's own Independent Test).

### Tests for User Story 4 (MANDATORY — ART-IV)

- [X] T029 [P] [US4] Extend `C4DesignView.test.tsx`: given the existing `useLayout` hook returns
  saved positions for a design/level, the adapter's produced `DiagramModel` uses those positions
  rather than auto-generated ones; given it returns empty positions, elements get a reasonable
  automatic layout (spec.md Acceptance Scenarios 1–2).
- [X] T030 [P] [US4] Extend `C4DesignView.test.tsx`: dragging an element on the canvas fires a
  debounced call to the existing `useSaveLayout` hook — confirming continued reuse, not a new
  persistence path.

### Implementation for User Story 4

- [X] T031 [US4] Wire the existing `useLayout` hook (`web/src/api/designs.ts`, unchanged) into
  `C4DesignView.tsx`'s model construction (feeding T004's adapter's `positions` parameter), and
  the existing `useSaveLayout` hook (debounced, mirroring `C4Canvas.tsx`'s own
  `_saveDebounceTimer` pattern) into position-change handling.

**Checkpoint**: All four user stories independently functional — run quickstart.md Scenario 5.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification against the plan's own completeness gates and constraints.

- [X] T032 [P] Confirm zero changes to `web/src/canvas/**` (C4Canvas and everything under it) via
  `git diff --stat web/src/canvas/` — this feature must not touch the screen it's replacing
  (plan.md Constraints; that's explicitly Phase C/ADP-914.13's job).
- [X] T033 [P] Confirm zero changes to the six vendored diagram-editor files (`Canvas.tsx`,
  `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`,
  `UnsupportedElementNotice.tsx`) and `core/dsl/c4.ts` via `git diff --stat` — confirms research.md
  Decisions 4/5's "no new callback prop" design held in practice, not just in the plan.
- [X] T034 [P] Run `adp-generate --check` — confirm the OpenAPI contract regenerates cleanly with
  the 5 new endpoints and 3 new Pydantic models, no uncommitted diff beyond the expected schema
  addition.
- [X] T035 Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and
  `cd web && npx vitest run && npx tsc --noEmit` — zero failures across the whole platform.
- [X] T036 Manually walk through quickstart.md Scenarios 1–7 in a real browser and via `curl`
  against the running dev API — the automated suite covers structural/logic assertions; this is
  the actual acceptance check that a real architect's build → level-switch → tag → export →
  reopen flow works end to end, and that the legacy "Canvas" screen is genuinely untouched
  (Scenario 7).
- [X] T037 Replace the auto-generated `054-c4-design-view` stub line in `CLAUDE.md` (added by
  `update-agent-context.sh` during `/speckit.plan`) with a proper hand-written narrative at commit
  time, per this session's established convention.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001/T002 fully parallel (different files/languages). T003 depends on T001
  (the router module must exist to be mounted).
- **Foundational (Phase 2)**: T004/T005 depend on T002 (module must exist). T006 depends on T004.
  T007 is independent of T004–T006 (pure nav/routing scaffolding) but only becomes meaningful once
  T006 exists to render. BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational **and** its own backend work (T008–T016
  before T017–T022, since the frontend reconciler/hooks call the new endpoints). This is the only
  story with a real dependency chain this deep.
- **User Story 2 (Phase 4)**: Depends on Foundational only — level-filtering operates on whatever
  elements a design already has, regardless of how they got there.
- **User Story 3 (Phase 5)**: Depends on Foundational only — reuses the *existing*
  `useUpdateElementTags`/render/CALM endpoints verbatim, untouched by User Story 1's new ones.
- **User Story 4 (Phase 6)**: Depends on Foundational only — reuses the *existing* `useLayout`/
  `useSaveLayout` endpoints verbatim.
- **Polish (Phase 7)**: Depends on all four stories being complete.

### Parallel Opportunities

- T001, T002 (Setup) — different files/languages, fully parallel.
- T004, T005 (Foundational) — different functions in the same new file; treat as sequential edits
  to one file in practice, or split ownership if run concurrently.
- T008, T009 (Phase 3 backend tests) — different files, fully parallel. T014, T015 (relationship
  endpoints) are parallel with each other once T011–T013 (element endpoints) land, since
  relationships only need elements to already exist as a validation target, not the element
  endpoints' own code.
- T017, T018 (Phase 3 frontend tests) — different files, fully parallel.
- **User Stories 2, 3, and 4 can all be built in parallel with each other, and even in parallel
  with User Story 1's backend work (T008–T016)** — none of them depend on the new endpoints, only
  on Foundational. The only real serialization is User Story 1's own frontend (T017–T022), which
  needs its own backend (T008–T016) done first.
- T032, T033, T034 (Phase 7) — independent verification commands, fully parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T007)
3. Phase 3: User Story 1 (T008–T022)
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–2, all new backend/frontend tests green.
5. This alone already delivers the feature's entire headline value (spec.md's own MVP framing) —
   the concrete fix for ADP-914.1–.4. Reasonable point to pause and demo.

### Incremental Delivery

1. Setup + Foundational → the adapter and a reachable (read-only) view exist.
2. User Story 1 → validate independently → "architects can build and edit a design's architecture
   visually, for real, for the first time."
3. User Stories 2, 3, and 4 → each validates independently, and — per the Parallel Opportunities
   above — could genuinely be built in parallel with each other and with User Story 1's own
   backend work, not strictly sequentially, if staffed for it.
4. Phase 7 Polish → vendored/legacy-file untouched checks, schema-drift check, full regression,
   manual walkthrough, `CLAUDE.md` narrative update, ready to commit.

## Notes

- No data-model migration tasks — plan.md's own framing confirms no schema/migration is needed;
  T001/T011–T016 are the entire "new backend surface," all additive.
- User Story 1 is the only story with real internal sequencing (backend before frontend, since the
  frontend literally calls the backend's new routes) — Stories 2–4 are each a single, mostly
  self-contained slice once Foundational exists, by design (research.md's own framing: this
  feature's hardest, most novel work is concentrated in User Story 1; everything else is mostly
  wiring to code that already exists and already works).
- Commit after each phase checkpoint, consistent with this session's established per-story commit
  rhythm on prior features.
