---

description: "Task list for C4 Diagram Type in the Diagram Tool"
---

# Tasks: C4 Diagram Type in the Diagram Tool

**Input**: Design documents from `/specs/053-c4-diagram-type/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/diagram-type-contract.md,
quickstart.md

**Tests**: Mandatory (ART-IV) — this feature's tests fall into two distinct kinds, both required:
(a) new correctness coverage for the vendored `c4` DSL family, which currently has none anywhere in
the repo (research.md Decision 2), and (b) six existing tests that currently assert `"c4"` is
*rejected* on purpose (contracts/diagram-type-contract.md's table) — these must be updated to
assert the opposite, not deleted, since the behavior they guard against is exactly what this
feature changes.

**Organization**: Grouped by user story (spec.md P1/P2/P3). Note up front: because the two
Foundational-phase changes (the `DiagramType` value itself, and the one seeding-logic fix) are
*shared prerequisites* every story depends on, each story phase below is almost entirely
verification — there is very little story-specific production code left to write once Foundational
is done. That is a genuine, correct outcome of this feature's small size, not a gap in the task
breakdown.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's US1/US2/US3

## Path Conventions

Frontend: `web/src/diagrams/`. Backend: `src/adp/diagrams/`, `tests/`. Repo root:
`/home/jmuir/projects/ADP`.

---

## Phase 1: Setup

**Purpose**: Add `"c4"` as an accepted value on both sides of the existing `DiagramType`
enumeration (data-model.md) — the one true prerequisite for everything else in this feature.

- [X] T001 [P] In `src/adp/diagrams/models.py`, add `"c4"` to the `DiagramType` Literal
  (`Literal["flowchart", "sequence", "erd", "uml", "architecture", "c4"]`, data-model.md).
- [X] T002 [P] In `web/src/diagrams/api.ts`, add `"c4"` to the frontend `DiagramType` union
  (mirrors T001 — data-model.md notes these two are hand-mirrored, not generated from one source;
  both must change together).

**Checkpoint**: `"c4"` is now a structurally valid value on both the backend and frontend type, but
nothing yet offers it as a UI choice or seeds it correctly — Foundational phase completes the
picture.

---

## Phase 2: Foundational

**Purpose**: Close the vendored `c4.ts` engine's zero-coverage gap (research.md Decision 2), make
`"c4"` an actual selectable choice in the editor, and fix the one real implementation wrinkle
(research.md Decision 1) — all three are blocking prerequisites every user story phase below
depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Create `web/src/diagrams/core/dsl/c4.test.ts`, mirroring `families.test.ts`'s
  existing per-family round-trip pattern (`families.test.ts:33,57,86,112,131`). Cover, at minimum:
  a `parse(serialize(model))` round-trip for a `Person`/`System`/`Container`/`Component` mix, a
  `SystemDb`/`ContainerQueue` variant pair, a nested `System_Boundary`, a `Rel`/`BiRel` pair, and
  one malformed-line case asserting the returned `ParseError`'s line/content/message shape matches
  every other family's error shape (spec.md FR-007). This file does **not** modify `c4.ts` itself
  (vendored, unchanged per plan.md's Constraints) — it is pure new test coverage for existing,
  correct behavior; expect it to pass without any production-code change.
- [X] T004 In `web/src/diagrams/DiagramEditorPage.tsx`, add `"c4"` to the `DIAGRAM_TYPES` array
  (spec.md FR-001). Depends on T001, T002.
- [X] T005 In `web/src/diagrams/DiagramEditorPage.tsx`'s new-diagram model-seeding logic, add the
  `"c4"` → `"c4-context"` `diagramTypeId` mapping (research.md Decision 1, data-model.md) — when
  the selected `DiagramType` is `"c4"`, call `createEmptyDiagramModel("c4-context")` instead of
  `createEmptyDiagramModel("c4")`; every other `DiagramType` value keeps calling
  `createEmptyDiagramModel(diagramType)` directly, unchanged. Depends on T004 (same file).

**Checkpoint**: `"c4"` is selectable, a new C4 diagram seeds correctly at Context level, and the
underlying parser/serializer now has real regression coverage. User story phases can proceed.

---

## Phase 3: User Story 1 - Create and author a new C4 diagram (Priority: P1) 🎯 MVP

**Goal**: An architect can pick "C4 Diagram" when creating a new diagram, author it via the text
description (Person/System/Container/Component, relationships, boundaries), and see it render
correctly on the canvas — with clear errors for anything the format doesn't recognize.

**Independent Test**: Start a new diagram, select the C4 type, describe a person, two systems, and
a relationship via the text description; confirm all three elements and the relationship render
correctly on the canvas (spec.md's own Independent Test for this story).

### Tests for User Story 1 (MANDATORY — ART-IV)

> Foundational (T003–T005) already delivers this story's full functional surface — these tasks
> verify that surface at the application level, distinct from T003's DSL-engine-level coverage.

- [X] T006 [P] [US1] Update `web/src/diagrams/DiagramEditorPage.test.tsx`'s existing
  "labels only the ... recommended" test (contracts/diagram-type-contract.md: currently at
  `DiagramEditorPage.test.tsx:256,262`) — `toHaveLength(5)` → `toHaveLength(6)`, and add `"c4"` to
  the iterated type list, confirming it's present and selectable (spec.md Acceptance Scenario 1).
- [X] T007 [P] [US1] Add a test to `DiagramEditorPage.test.tsx` asserting a newly created `"c4"`
  diagram's DSL panel shows a valid, empty Context-level starting point (e.g. its text content is
  exactly the serialized empty-Context form, not a flowchart-family default or an unrelated
  fallback) — the app-level confirmation that T005's seeding fix actually took effect (spec.md
  Acceptance Scenario 2).
- [X] T008 [US1] Add a test to `DiagramEditorPage.test.tsx` (mirroring the existing "saves a new
  diagram with the authored DSL content" pattern) that: creates a new `"c4"` diagram, enters valid
  C4 text describing a `Person`, a `System`, and a `Rel` between them via the DSL panel, applies it,
  and confirms all three render on the canvas (spec.md Acceptance Scenario 3) — including an
  explicit assertion that the `Person` node renders using the canvas's existing default shape
  fallback (a plain rectangle, since `shapes.tsx`'s `renderNodeShape` — vendored, unchanged — has no
  dedicated `'person'` case; `svg-renderer.ts`'s export path, unlike the canvas, already does — see
  T012). This is a pre-existing, latent behavior this feature makes reachable for the first time,
  not a defect this feature introduces or is expected to fix.
- [X] T009 [P] [US1] Add a test to `DiagramEditorPage.test.tsx` confirming that applying malformed
  C4 text (e.g. a misspelled element keyword) surfaces a line/content error through the same
  `parseErrors` presentation already used for every other diagram type (spec.md Acceptance
  Scenario 4) — an application-level confirmation that T003's engine-level error-shape coverage is
  actually wired through to the UI.

**Checkpoint**: User Story 1 fully functional and independently testable — run
`cd web && npx vitest run src/diagrams/core/dsl/c4.test.ts src/diagrams/DiagramEditorPage.test.tsx`
and quickstart.md Scenarios 1–3.

---

## Phase 4: User Story 2 - Save, reopen, and continue a C4 diagram (Priority: P2)

**Goal**: A saved C4 diagram is listed correctly, reopens with full fidelity, and the six existing
tests that currently assert `"c4"` is rejected (contracts/diagram-type-contract.md) now assert the
opposite — the exact behavior this feature changes.

**Independent Test**: Save a C4 diagram containing several elements, navigate away, reopen it from
the diagram list, and confirm every element, relationship, and label is exactly as left (spec.md's
own Independent Test for this story).

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T010 [P] [US2] In `tests/unit/diagrams/test_diagrams_models.py`: add `"c4"` to the
  `test_create_accepts_each_supported_type` parametrized list (currently lines 42–47); change
  `test_create_rejects_unsupported_type`'s example value (currently line 50–52, uses `"c4"`) to a
  still-genuinely-unsupported string (e.g. `"gantt"`) — per contracts/diagram-type-contract.md,
  this test's *purpose* (reject unknown types) is preserved, only its example value changes.
- [X] T011 [P] [US2] In `tests/contract/test_diagrams_api_contract.py`: the same two changes as
  T010 at the contract-test layer (currently lines 43–54's parametrized create test, and line 117's
  "rejects unsupported type" test), plus add `"c4"` to the list/filter test's 5-type set (currently
  lines 162, 172).
- [X] T012 [US2] Add a test to `DiagramEditorPage.test.tsx` (mirroring the existing "loads an
  existing diagram's saved content into the editor" pattern) that saves a `"c4"` diagram with
  several elements and relationships, simulates reopening it, and confirms every element,
  relationship, position, and label is restored exactly (spec.md Acceptance Scenarios 1–2, SC-003).

**Checkpoint**: User Stories 1 AND 2 both work independently — run
`pytest tests/unit/diagrams/ tests/contract/test_diagrams_api_contract.py -q` and
`cd web && npx vitest run src/diagrams/` and quickstart.md Scenario 4.

---

## Phase 5: User Story 3 - Export a C4 diagram (Priority: P3)

**Goal**: A C4 diagram exports to an image file the same way every other diagram type already does
— confirming the existing, already-generic export path needs no C4-specific change.

**Independent Test**: With a C4 diagram open, use the export action and confirm an image file is
produced showing the diagram's current content (spec.md's own Independent Test for this story).

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T013 [US3] Create `web/src/diagrams/editor/ExportAction.test.tsx` (none exists today for any
  diagram type) covering: exporting a C4-family `DiagramModel` produces non-empty SVG output via
  `renderToSvg` containing recognizable output for each element (including confirming the `Person`
  element exports using `svg-renderer.ts`'s existing dedicated `'person'` case — `svg-renderer.ts:
  341` — a deliberate visual difference from the canvas's own plain-rectangle fallback for the same
  shape, T008's note, both pre-existing and both correct in their own contexts, not something this
  feature needs to reconcile). Confirm the PNG export call path (`exportDiagramPng`) is invoked with
  that same SVG, unchanged from how every other diagram type already exports (spec.md FR-006).

**Checkpoint**: All three user stories independently functional — run
`cd web && npx vitest run src/diagrams/editor/ExportAction.test.tsx` and quickstart.md Scenario 5.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification against the plan's own completeness gates and the spec's
zero-regression requirement (SC-006).

- [X] T014 [P] Run `adp-generate --check` — confirm the OpenAPI contract (ART-XIII: generated, not
  hand-maintained) regenerates cleanly with the new `"c4"` `Literal` value and produces no
  uncommitted diff beyond the expected schema change.
- [X] T015 [P] Run the full regression suite: `pytest tests/ --ignore=tests/integration -q` and
  `cd web && npx vitest run && npx tsc --noEmit` — zero failures across the whole platform, not
  just this feature's own tests (SC-006: zero existing diagrams change type, content, or behavior).
- [X] T016 Manually walk through quickstart.md Scenarios 1–6 in a real browser and via `curl`
  against the running dev API — the automated suite covers structural/state assertions; this is the
  actual acceptance check that a real architect's create → author → save → reopen → export flow
  works end to end, and that pre-existing (non-`c4`) diagrams are visibly unaffected (Scenario 6).
- [X] T017 Replace the auto-generated `053-c4-diagram-type` stub line in `CLAUDE.md` (added by
  `update-agent-context.sh` during `/speckit.plan`) with a proper hand-written narrative at commit
  time, per this session's established convention — not part of implementation itself, but required
  before this feature's commit per prior precedent (052, 051, 050).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — T001/T002 fully parallel (different files, different
  languages).
- **Foundational (Phase 2)**: T003 depends only on Setup being conceptually complete (it tests
  already-vendored, unchanged code — no real dependency, but sequenced here since it's a blocking
  quality gate for every story). T004 depends on T001+T002. T005 depends on T004 (same file). BLOCKS
  all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational. T010/T011 (backend) are independent of
  Phase 3 entirely; T012 (frontend reopen test) has no logical dependency on Phase 3 either, though
  in practice both extend the same `DiagramEditorPage.test.tsx` file, so coordinate edits if run
  concurrently with Phase 3's tasks.
- **User Story 3 (Phase 5)**: Depends on Foundational only — genuinely independent of Phase 3/4,
  since export operates on whatever `DiagramModel` is already in memory regardless of how it got
  there.
- **Polish (Phase 6)**: Depends on all three stories being complete.

### Parallel Opportunities

- T001, T002 (Phase 1) — different files, different languages, fully parallel.
- T003 (Phase 2) is parallel with T001/T002 — different file, no real dependency (it tests unchanged
  vendored code).
- T006, T007, T009 (Phase 3) are parallel — distinct assertions, though likely land in the same
  `DiagramEditorPage.test.tsx` file alongside T008 and T012 (Phase 4); coordinate edits across
  phases if working concurrently rather than sequentially.
- T010, T011 (Phase 4) are parallel — different files (unit vs. contract tests).
- T014, T015 (Phase 6) are parallel — independent verification commands.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001–T002)
2. Phase 2: Foundational (T003–T005) — this is where nearly all of this feature's actual code
   changes live, by design (Dependencies section above).
3. Phase 3: User Story 1 (T006–T009)
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–3, `c4.test.ts` and
   `DiagramEditorPage.test.tsx` green.
5. This alone already delivers the feature's entire headline value (spec.md's own MVP framing) —
   architects can create and author C4 diagrams. Reasonable point to pause and demo.

### Incremental Delivery

1. Setup + Foundational → the `"c4"` value exists, is selectable, and is correctly seeded.
2. User Story 1 → validate independently → "architects can create and author C4 diagrams."
3. User Story 2 → validate independently → "...and trust them to save and reopen correctly," plus
   closes the six existing tests that would otherwise contradict this feature's own contract.
4. User Story 3 → validate independently → "...and export them, same as every other type."
5. Phase 6 Polish → schema-drift check, full regression, manual walkthrough, `CLAUDE.md` narrative
   update, ready to commit.

## Notes

- No data-model migration tasks — data-model.md's own framing confirms no schema/migration is
  needed (the field is stored as plain `TEXT`); T001/T002 are the entire "data model" change.
- Six of this feature's test tasks (T006, T007's assertion shape, T009's shape, T010, T011) are
  *fixing existing tests to assert the opposite of what they assert today* — not adding coverage
  from zero. This is deliberate and expected: those tests currently encode the pre-feature contract
  on purpose (contracts/diagram-type-contract.md), and asserting the new contract is exactly this
  feature's job.
- Commit after each phase checkpoint, consistent with this session's established per-story commit
  rhythm on prior features.
