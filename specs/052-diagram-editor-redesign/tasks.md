---

description: "Task list for Diagram Editor Visual & Workspace Redesign"
---

# Tasks: Diagram Editor Visual & Workspace Redesign

**Input**: Design documents from `/specs/052-diagram-editor-redesign/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/diagram-css-contract.md, quickstart.md

**Tests**: Mandatory (ART-IV) — extending the three existing page test files
(`DiagramListPage.test.tsx`, `DiagramsPage.test.tsx`, `DiagramEditorPage.test.tsx`), written/updated
before their corresponding implementation tasks in each story's phase.

**Organization**: Grouped by user story (spec.md P1/P2/P3), matching plan.md's Project Structure.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md's US1/US2/US3

## Path Conventions

Frontend-only feature. All paths are under `web/src/diagrams/` (repo root: `/home/jmuir/projects/ADP`).

---

## Phase 1: Setup

**Purpose**: Create the one new file every story's styling depends on.

- [X] T001 Create empty `web/src/diagrams/diagrams.css` with a file-header comment describing its
  scope (mirrors `web/src/overview/overview.css`'s own header comment style) and import it once
  from `web/src/diagrams/DiagramsPage.tsx` (top-level `import "./diagrams.css"`, alongside its
  existing imports).

**Checkpoint**: `diagrams.css` exists, is wired into the bundle, has zero rules yet (verified via
`cd web && npx tsc --noEmit` — the import itself must not break the build before any content is added).

---

## Phase 2: Foundational

**Purpose**: Shared token/class scaffolding every user story's phase writes into.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] In `web/src/diagrams/diagrams.css`, add the `.btn`, `.btn--primary`,
  `.btn--secondary`, `.btn--tertiary`, `.btn--danger`, `.btn--compact` rule set (contracts/
  diagram-css-contract.md's `Canvas.tsx`/`DslPanel.tsx`/`ConfirmDialog.tsx` table), styled from
  `--accent`/`--accent-2`/`--accent-wash`/`--crit`/`--crit-wash`/`--radius`/`--radius-sm`/
  `--space-1`…`--space-3` (data-model.md's reused-tokens table) — this class family is shared by
  every story's Canvas/DslPanel/ConfirmDialog rendering, so it belongs in Foundational rather than
  any single story's phase.
- [X] T003 [P] In `web/src/diagrams/diagrams.css`, add the `.modal`, `.modal--wide`,
  `.modal__header`, `.modal__title`, `.modal__body`, `.modal__footer` rule set (contracts/
  diagram-css-contract.md's `Modal.tsx` table; research.md Decision 6 — defined here, not in
  `web/src/ui/ui.css`), styled from `--surface`/`--surface-2`/`--border`/`--radius-lg`/
  `--shadow-md` — used by both the delete-confirmation dialog (US1) and shared by any future modal
  use in this screen.
- [X] T004 [P] [US1] Add 10 new `IconName` entries to `web/src/diagrams/editor/ui/Icon.tsx`'s
  `IconName` union and `PATHS` record per data-model.md's exact mapping (`shape-rectangle`,
  `shape-rounded`, `shape-circle`, `shape-stadium`, `shape-subroutine`, `shape-double-circle`,
  `shape-hexagon`, `shape-parallelogram`, `shape-trapezoid`, `shape-asymmetric`), each a 16×16
  `stroke="currentColor"` `strokeWidth={1.5}` outline of the shape it names, matching the file's
  existing icon-definition pattern exactly (grouped here as it's a shared editor-chrome asset, but
  labeled US1 since it's first consumed by the palette restyle in that story).

**Checkpoint**: Foundation ready — button/modal CSS and the icon set exist; user story phases can
now proceed.

---

## Phase 3: User Story 1 - The diagram screens look like part of ADP (Priority: P1) 🎯 MVP

**Goal**: List screen, editor chrome, delete dialog, and save-state indicator all use ADP's actual
`.ui-*`/`Button`/`Card`/`Icon`/`Modal` conventions — zero unstyled browser-default controls remain.

**Independent Test**: Open the Diagrams list and an existing diagram's editor; every control (list
rows, empty state, title/type/Save, toolbar buttons, delete-confirmation dialog) visibly matches
ADP's styling, verifiable without any other story's work being done.

### Tests for User Story 1 (MANDATORY — ART-IV)

> Write these first; confirm they fail against the current (unstyled) markup before implementing.

- [X] T005 [P] [US1] Update `web/src/diagrams/DiagramListPage.test.tsx` to assert the list renders
  via `.ui-list`/`.ui-list-row` structure and the empty state renders via `.ui-empty` (replacing any
  assertions tied to the current raw `<table>` structure).
- [X] T006 [P] [US1] Update `web/src/diagrams/DiagramsPage.test.tsx` to assert the page chrome
  renders via `.ui-page`/`.ui-toolbar`/`.ui-h1` and the "+ New Diagram" action renders as ADP's
  `Button` component (replacing assertions tied to the current bare `<div style={{...}}>` wrapper).
- [X] T007 [US1] Update `web/src/diagrams/DiagramEditorPage.test.tsx` to add: (a) assertions that
  the title field/type selector/Save action render via `.ui-input`/`.ui-select`/`Button`; (b) a new
  test for the persistent save-state indicator (`idle` on load, `saving` mid-request, `saved` after
  a successful save, `error` on failure) remaining visible after save completes, not just a
  transient button-label change; (c) an assertion that the delete-confirmation dialog (triggered
  from the list, reachable in this file's existing test harness) renders `.modal__header`/
  `.modal__body`/`.modal__footer` structure.

### Implementation for User Story 1

- [X] T008 [P] [US1] Rewrite `web/src/diagrams/DiagramListPage.tsx`: replace the raw `<table>` with
  `.ui-list`/`.ui-list-row` markup (title, type, updated date, Open/Delete actions per quickstart.md
  Scenario 1), replace the empty-state paragraph with `.ui-empty`, and switch its data-fetching from
  ad hoc `useState`/`useEffect` calls against `./api` to the same TanStack Query hook shape
  `web/src/designs/DesignsPage.tsx`'s `useDesignList` demonstrates (research.md Decision 2).
- [X] T009 [US1] Rewrite `web/src/diagrams/DiagramsPage.tsx`: replace the bare `<div style={{...}}>`
  wrapper with `.ui-page`/`.ui-toolbar`/`.ui-h1`, replace the raw "+ New Diagram" `<button>` with
  ADP's `Button` component, and add the `import "./diagrams.css"` entry point (T001 wires the file;
  this task is the actual first consumer of its rules). Depends on T001, T008.
- [X] T010 [US1] In `web/src/diagrams/DiagramEditorPage.tsx`: replace the raw title `<input>` and
  type `<select>` with `.ui-input`/`.ui-select`, replace the Save `<button>` with ADP's `Button`
  component, and add the new local save-state enum (`idle | saving | saved | error`,
  data-model.md's Component State Additions) rendered as a persistent indicator using `--good`
  (saved) / `--warn` or `--crit` (error) tokens — not just the existing transient label swap.
- [X] T011 [P] [US1] In `web/src/diagrams/editor/UnsupportedElementNotice.tsx`, replace the inline
  `style={{ color: '#b00020' }}` with `web/src/ui/ui.css`'s existing `.ui-alert` class (contracts/
  diagram-css-contract.md's note — this file is ADP-authored, not vendored, so this is a direct,
  safe edit; no `diagrams.css` entry needed since `.ui-alert` already exists globally).
- [X] T012 [US1] In `web/src/diagrams/editor/Canvas.tsx`'s shape-picker toolbar section, swap the
  single-character text glyphs for the new `IconName` values added in T004 (FR-004) — this is the
  one JSX line in the vendored files that changes prop values passed to the already-generic `Icon`
  component, not a class-name or structural change, so it stays within research.md Decision 1's
  "no JSX restyling" boundary.

**Checkpoint**: User Story 1 fully functional and independently testable — run
`cd web && npx vitest run src/diagrams/DiagramListPage.test.tsx src/diagrams/DiagramsPage.test.tsx src/diagrams/DiagramEditorPage.test.tsx`
and quickstart.md Scenarios 1–2.

---

## Phase 4: User Story 2 - Diagram content is correct and legible in both light and dark theme (Priority: P2)

**Goal**: Canvas surface (background + grid) adapts to theme; default shape colors stay fixed per
FR-010; all interaction-only colors (selection, marquee, hover) use `--accent`, not a hardcoded hex.

**Independent Test**: Toggle the app theme while a diagram with shapes is open; canvas
background/grid visibly change, default shape fill/stroke do not, and selection/marquee color
matches the app's actual accent in both themes — verifiable independently of US1/US3.

### Tests for User Story 2 (MANDATORY — ART-IV)

- [X] T013 [P] [US2] Add a test to `web/src/diagrams/DiagramEditorPage.test.tsx` (or a new
  `web/src/diagrams/editor/Canvas.test.tsx` if none exists — confirm first) asserting the canvas
  root element carries the `.canvas-root` class whose computed styling is driven by CSS custom
  properties (`--surface-2`/`--border`), i.e. that toggling `data-theme` on a wrapper element
  changes the resolved token values consumed by the canvas surface — a rendered-DOM-level check
  the theme is wired through CSS variables, not a hardcoded value.
- [X] T014 [P] [US2] Add a test asserting `web/src/diagrams/editor/shapes.tsx`'s default fill/stroke
  values (`'#ffffff'` / `'#333333'`) remain literal, unchanged constants — a regression guard for
  FR-010 ("no code change to shapes.tsx's color defaults is in scope"), so a future edit that
  accidentally swaps them for theme-reactive tokens fails this test rather than silently shipping.

### Implementation for User Story 2

- [X] T015 [US2] In `web/src/diagrams/diagrams.css`, add `.canvas-root`/`.canvas-svg` background
  styling: `background: var(--surface-2)`, border from `var(--border)`, and a `radial-gradient`
  dot-grid pattern keyed to `var(--border)` at low density (research.md Decision 3) — no new custom
  properties added to `web/src/ui/tokens.css`.
- [X] T016 [US2] In `web/src/diagrams/diagrams.css`, style `.canvas-edit-affordance`, the `.card.
  cluster` style popover, `.rail-section`/`.section-label`/`.rail-section__label`, `.shape-grid`,
  `.tool-list`, and `.field__label` (remaining `Canvas.tsx` classes from contracts/
  diagram-css-contract.md not already covered by T002's button rules), using `--surface`/
  `--surface-3`/`--ink`/`--ink-2`/`--border`/`--radius`/`--space-1`…`--space-4`.
- [X] T017 [US2] Confirm (or, if genuinely hardcoded outside CSS, fix) that selection-stroke,
  marquee-rectangle, and hover-affordance colors in `web/src/diagrams/editor/shapes.tsx`/
  `Canvas.tsx` resolve through a CSS class targeting `var(--accent)` rather than a literal hex —
  per the Assumptions section, no test currently pins the old literal, so this is a same-effect
  token swap done via `diagrams.css` selectors, not a JSX edit, wherever the existing markup already
  exposes a class hook for it; only fall back to a minimal JSX class-name addition if no hook exists
  today, documenting that one exception against research.md Decision 1.
- [X] T018 [US2] In `web/src/diagrams/diagrams.css`, add the `.panel`/`.panel__body`/
  `.panel__body--flush`/`.panel__footer`/`.dsl-panel`/`.dsl-panel__editor` rule set (`DslPanel.tsx`
  from contracts/diagram-css-contract.md), using `--surface-2`/`--border`/`--mono`/`--space-2`…
  `--space-4`/`--shadow-sm`, satisfying FR-008 (distinctly-styled panel with labeled header) as part
  of this story's theme-correctness pass since the panel background is theme-token-driven the same
  way the canvas is.

**Checkpoint**: User Stories 1 AND 2 both work independently — run
`cd web && npx vitest run src/diagrams/` and quickstart.md Scenarios 3–5.

---

## Phase 5: User Story 3 - The editor is a workable diagram-building workspace (Priority: P3)

**Goal**: Palette, canvas, and DSL panel simultaneously visible via a responsive CSS Grid layout
(collapsing at ADP's existing 900px breakpoint); Connect-mode active state and canvas↔DSL sync
directionality are visually communicated.

**Independent Test**: Open the editor with shapes placed; palette/canvas/DSL panel are all visible
and independently usable without scrolling one out of view; narrowing the viewport below 900px
collapses the palette to a toggle rather than breaking the layout — verifiable independently of
US1/US2's own completions.

### Tests for User Story 3 (MANDATORY — ART-IV)

- [X] T019 [P] [US3] Add a test to `web/src/diagrams/DiagramEditorPage.test.tsx` asserting the new
  workspace-layout wrapper renders palette, canvas, and DSL panel elements simultaneously in the
  DOM (all present, none conditionally unmounted) at a desktop-width render.
- [X] T020 [P] [US3] Add a test asserting the palette-collapse boolean state (data-model.md's
  Component State Additions) toggles a `data-collapsed`/class attribute on the palette rail when its
  disclosure control is clicked, and that the control is present and operable regardless of viewport
  (jsdom doesn't evaluate `@media` queries, so this test targets the state/attribute wiring, not the
  visual collapse itself — the visual collapse is verified manually via quickstart.md Scenario 6).
- [X] T021 [P] [US3] Add a test asserting the Connect tool button reflects an active/pressed
  ARIA/class state (e.g. `aria-pressed="true"` or a `.btn--active`-equivalent class) when connect
  mode is engaged, toggling off when disengaged.

### Implementation for User Story 3

- [X] T022 [US3] In `web/src/diagrams/DiagramEditorPage.tsx`, introduce the workspace-layout
  wrapper: a CSS Grid container (`grid-template-columns`) with three regions (palette rail, canvas,
  DSL panel) simultaneously visible at desktop widths, plus the new local `paletteCollapsed` boolean
  state (T020) wired to a disclosure button. Depends on T009, T010 (chrome already restyled).
- [X] T023 [US3] In `web/src/diagrams/diagrams.css`, add the workspace-grid layout rules and the
  `@media (max-width: 900px)` collapse behavior (research.md Decision 5 — matching `web/src/ui/
  ui.css` lines 42–48's existing breakpoint exactly): palette rail becomes a toggleable drawer
  overlaying the canvas rather than the three regions stacking vertically.
- [X] T024 [US3] In `web/src/diagrams/diagrams.css`, add an active/pressed visual state selector for
  the Connect tool button (FR-013) — e.g. `.btn--secondary[aria-pressed="true"]` or an equivalent
  already-present state hook — styled with `--accent-wash`/`--accent`, wired to whatever attribute
  T021's test asserts; add the attribute in `Canvas.tsx` only if no existing hook exposes connect-mode
  state today (same one-line-exception carve-out as T017, documented if used).
- [X] T025 [US3] In `web/src/diagrams/editor/DslPanel.tsx`'s consuming context (`DiagramEditorPage.
  tsx` or `DslPanel.tsx` itself if it already accepts a status prop), add the FR-014 sync-direction
  affordance: a small always-visible label/icon pair communicating "canvas → DSL: live" vs. "DSL →
  canvas: Apply required" — styled via new `diagrams.css` classes, values sourced from
  `useDslSync.ts`'s already-existing sync state (no new state introduced, only a new visual
  presentation of state that already exists per research.md's scope).

**Checkpoint**: All three user stories independently functional — run
`cd web && npx vitest run src/diagrams/` and quickstart.md Scenarios 6–7.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification against the plan's own completeness gates.

- [X] T026 [P] Run the `grep -roP` verification command from contracts/diagram-css-contract.md
  against the final state of the six vendored files' `className=` usage — confirm zero classes
  outside the documented contract, and zero `diagrams.css` selectors left unused (cross-check
  manually against the stylesheet).
- [X] T027 [P] Confirm zero JSX changes landed in the five vendored files that had no documented
  exception (`shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`) — i.e. that T012's
  icon-prop swap and any T017/T024 exceptions in `Canvas.tsx` are the *only* vendored-file diffs, via
  `git diff --stat web/src/diagrams/editor/Canvas.tsx web/src/diagrams/editor/shapes.tsx web/src/diagrams/editor/DslPanel.tsx web/src/diagrams/editor/useDslSync.ts web/src/diagrams/editor/ConfirmDialog.tsx`.
- [X] T028 Run `cd web && npx vitest run src/diagrams/ && npx tsc --noEmit && npm run test:run` (
  quickstart.md Scenario 8) — full regression pass, zero failures across the whole frontend suite,
  not just this feature's own tests.
- [X] T029 Manually walk through quickstart.md Scenarios 1–7 in a real browser (light and dark
  theme, desktop and narrow viewport) — the automated suite covers structural/state assertions, not
  visual correctness, so this manual pass is the actual acceptance check for SC-001/SC-002/SC-003.
- [X] T030 Replace the auto-generated `052-diagram-editor-redesign` stub line in `CLAUDE.md` (added
  by `update-agent-context.sh` during `/speckit.plan`) with a proper hand-written narrative at commit
  time, per this session's established convention — not part of implementation itself, but required
  before this feature's commit per prior precedent (051, 050).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (T001 creates the file T002–T004 write into). BLOCKS
  all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational. Independent of US1's own tasks, though T009
  (US1) is what actually wires `diagrams.css` into the page — US2's CSS additions are inert until
  that import lands, so in practice run Phase 3 before Phase 4 even though there's no *logical*
  coupling beyond the shared stylesheet file.
- **User Story 3 (Phase 5)**: Builds its workspace wrapper on top of the already-restyled chrome
  (T022 explicitly depends on T009/T010) — run after Phase 3. Independent of Phase 4's token/color
  work otherwise.
- **Polish (Phase 6)**: Depends on all three stories being complete.

### Parallel Opportunities

- T002, T003, T004 (Phase 2) touch different concerns within the same new file / different files —
  safe to parallelize with care (T002/T003 both edit `diagrams.css`; treat as sequential edits to one
  file in practice even though logically independent, or have one contributor own the file for this
  phase).
- T005, T006 (Phase 3 tests) are fully parallel — different files.
- T008 (Phase 3) is parallel with T004/T011 — different files.
- T013, T014 (Phase 4 tests) are parallel — different files/concerns.
- T019, T020, T021 (Phase 5 tests) are parallel — different assertions, though likely land in the
  same `DiagramEditorPage.test.tsx` file, so coordinate edits if run concurrently.
- T026, T027 (Phase 6) are parallel — independent verification commands.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (T001)
2. Phase 2: Foundational (T002–T004)
3. Phase 3: User Story 1 (T005–T012)
4. **STOP and VALIDATE**: quickstart.md Scenarios 1–2, `DiagramListPage`/`DiagramsPage`/
   `DiagramEditorPage` test files green.
5. This alone already resolves the single most visible problem (spec.md's own framing) — a
   reasonable place to pause and demo before continuing.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. User Story 1 → validate independently → the "no more unstyled prototype look" milestone.
3. User Story 2 → validate independently → the "theme-correct canvas" milestone.
4. User Story 3 → validate independently → the "workable simultaneous-pane workspace" milestone.
5. Phase 6 Polish → final contract/regression verification, `CLAUDE.md` narrative update, ready to
   commit.

## Notes

- No contract tests / no data-model migration tasks — this feature has no API surface (FR-016) and
  no persisted entities (data-model.md's own framing); the CSS class contract in
  contracts/diagram-css-contract.md plays that role instead, verified by T026.
- T012, T017, T024 are the only three points where a vendored file's JSX might need a one-line,
  explicitly-documented exception (icon prop values; a class/attribute hook for accent-token
  selection color; a class/attribute hook for connect-mode active state) — each carries an inline
  note in its own task to keep research.md Decision 1's "no JSX restyling" boundary auditable rather
  than silently eroded.
- Commit after each phase checkpoint, consistent with this session's established per-story commit
  rhythm on prior features.
