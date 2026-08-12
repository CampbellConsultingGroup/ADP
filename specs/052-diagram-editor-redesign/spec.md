# Feature Specification: Diagram Editor Visual & Workspace Redesign

**Feature Branch**: `052-diagram-editor-redesign`
**Created**: 2026-08-12
**Status**: Draft
**Input**: User description: "Redesign ADP's diagram-building screen (list + editor) so it reads as part of ADP rather than as an unstyled prototype, without touching the vendored diagram parsing/rendering engine underneath it." (full text: `docs/diagram-editor-redesign-specify-input.md`)

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II, ART-III** — Model is Source of Truth / Machine-Readable: do not apply — this feature is purely presentational; the diagram DSL, its parsing, and its canonical storage shape are explicitly untouched (Out of Scope).
- **ART-V** — Security by Design: low-risk — see Threat Model. No new data, no new trust boundary, no backend change of any kind.
- **ART-VI** — Observability: does not apply beyond the ordinary level — no new telemetry surface, no AI step.
- **ART-VII–XI** — AI-related articles, traceability: do not apply — no AI-generated content, no new audit obligation, no traceability-thread change.
- **ART-XII** — Fixed Visual Language: does not apply — governs the locked C4 rendering theme specifically (ADP-SPEC-010), not the general diagram-editor UI.
- **ART-XIII** — Typed Contracts Everywhere: does not apply — no new API, no new persisted or transmitted data shape.
- **ART-XIV, ART-XV** — Reproducible builds / Schema evolution: do not apply — no migration, no schema change, frontend-only.
- **ART-XVI** — Documentation as Code: applies (SHOULD).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: none beyond what's already exposed — this is a visual/interaction restyle of an existing screen. No new data is read, written, or displayed that isn't already shown today.

**Trust boundaries crossed**: none — no new API call, no new backend endpoint, no new external dependency. All changes are within the existing browser-rendered SPA.

**Abuse cases**: none identified — a pure presentation-layer change to an already-authenticated, already-authorized screen carries no new abuse surface.

**Residual risk**: none beyond the ordinary risk of any frontend change (a regression in rendering or interaction) — mitigated by the existing test suite for this screen plus new tests this feature adds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The diagram screens look like part of ADP (Priority: P1) 🎯 MVP

An architect opens the Diagrams list or a diagram's editor and sees a screen that is visually consistent with the rest of ADP — styled buttons, inputs, dropdowns, list rows, and page chrome that match the design language already used on every other screen (Overview, Business, Strategy, Designs) — instead of a screen that looks like an unstyled prototype dropped into the app.

**Why this priority**: The single most visible, most immediately jarring problem, and independently valuable on its own even before any layout or theme-correctness work — every other screen in ADP already looks professional; this is the one screen that doesn't.

**Independent Test**: Open the diagram list screen and an existing diagram's editor; visually confirm every control (buttons, inputs, selects, the list rows, the empty state, the delete-confirmation dialog) renders with ADP's actual styling — no bare browser-default form controls anywhere on either screen.

**Acceptance Scenarios**:

1. **Given** an architect opens the Diagrams list screen, **When** the screen renders, **Then** the list of diagrams, the "+ New Diagram" action, and the empty state all match the visual style already used by comparable list screens elsewhere in ADP (e.g. Designs, Knowledge).
2. **Given** an architect opens a diagram in the editor, **When** the screen renders, **Then** the title field, diagram-type selector, Save action, and every toolbar button render with ADP's styled form-control and button treatment — not bare browser-default chrome.
3. **Given** an architect attempts to delete a diagram, **When** the confirmation dialog appears, **Then** it renders with ADP's modal styling (header, body, footer, actions) rather than unstyled native dialog chrome.
4. **Given** an architect saves a diagram, **When** the save completes, **Then** the screen shows a clear, persistent indication of save state (e.g. "Saved" / an error state), not just a transient label change on the Save button itself.

---

### User Story 2 - Diagram content is correct and legible in both light and dark theme (Priority: P2)

An architect building a diagram at night in dark mode sees a canvas that fits the app's dark appearance — not a bright white rectangle — while an architect who later exports or views a saved diagram sees consistent, correct colors regardless of which theme was active when it was authored.

**Why this priority**: This closes an actual rendering bug (not just an aesthetic gap) — today's canvas and node colors do not respond to the app's theme toggle at all, which is jarring and inconsistent with how every other themed surface in ADP behaves. Independent of the chrome restyle in User Story 1 and the layout work in User Story 3.

**Independent Test**: Toggle the app between light and dark theme while a diagram with several shapes is open in the editor; confirm the canvas surface and its spatial reference marks adapt to the active theme, and confirm shape colors follow whichever resolution this spec settles on (see the clarified requirement below) consistently in both themes — never an unstyled, jarring mismatch.

**Acceptance Scenarios**:

1. **Given** an architect switches the app from light to dark theme, **When** a diagram is open in the editor, **Then** the canvas surface (its background and spatial reference pattern) visually adapts to the active theme.
2. **Given** a diagram with shapes that use only default (not explicitly customized) colors, **When** the app theme is toggled, **Then** those shapes render per this spec's resolved node-color requirement (FR-010) consistently — never leaving a stark, unstyled white box on a dark canvas.
3. **Given** an architect explicitly sets a custom color on a shape via the existing style controls, **When** the diagram is later exported to SVG/PNG, **Then** that exact custom color is preserved in the export, unaffected by the editor's theme at export time.
4. **Given** an architect hovers, selects, or multi-selects shapes, **When** those interaction states render, **Then** their colors (selection outline, marquee rectangle, hover affordances) use the app's actual accent color in both themes, not a hardcoded value that happens to resemble it.

---

### User Story 3 - The editor is a workable diagram-building workspace (Priority: P3)

An architect actively building a diagram can see the shape palette, the canvas, and the DSL text simultaneously — without scrolling the palette out of view to work the canvas, or scrolling the canvas out of view to check the DSL — and gets clear visual feedback for the connect-mode and canvas↔DSL-sync behaviors that already exist today but aren't currently communicated.

**Why this priority**: The largest structural change, layered on top of User Stories 1 and 2 — a real workflow improvement, but the screen is already meaningfully better once the first two stories land, so this is correctly last.

**Independent Test**: Open the editor with several shapes already placed; confirm the shape palette, canvas, and DSL panel are all visible and usable together without requiring the user to scroll one out of view to interact with another; confirm entering connect mode shows a clear active-state indicator, and confirm the DSL panel visually communicates that canvas edits reflect into it live while DSL edits require an explicit action to apply.

**Acceptance Scenarios**:

1. **Given** an architect has placed several shapes on the canvas, **When** they view the editor, **Then** the shape palette, the canvas, and the DSL panel are all visible and independently usable at the same time, without one obscuring or requiring the scroll-away of another.
2. **Given** an architect activates connect mode, **When** it is active, **Then** the Connect control shows a clear, visually distinct active/pressed state.
3. **Given** an architect edits the canvas, **When** the change is applied, **Then** the DSL panel visibly updates to reflect it, communicated as a live/automatic update.
4. **Given** an architect edits the DSL text, **When** they have not yet applied it, **Then** the screen visibly communicates that an explicit action is required before the change reaches the canvas — distinct from the DSL panel's own live-updating-from-canvas behavior in the other direction.

---

### Edge Cases

- What happens to a diagram that already has shapes with explicitly-set custom colors when this redesign ships? → Unaffected — FR-010's resolution applies only to shapes using default (unset) color, per the clarified requirement; explicitly customized colors are never overridden.
- What happens on a narrow browser viewport where a persistent multi-pane workspace (User Story 3) may not comfortably fit alongside ADP's own nav rail? → The workspace layout must degrade gracefully (e.g. a collapsible palette) rather than becoming unusable or requiring horizontal scrolling of the page itself; exact behavior is left to planning, but "unusable below some viewport width with no fallback" is not acceptable.
- What happens to diagrams already saved before this redesign ships? → Unaffected in storage — this is a presentation-only change; no diagram's saved DSL or model content changes as a result of this feature.
- What happens when a diagram fails to parse (invalid DSL)? → The existing error-surfacing behavior (line, content, and message reported) is preserved; only its visual styling changes to match ADP's alert convention (Constraints).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The diagram list screen MUST render using ADP's existing list, empty-state, and action-button visual conventions — not unstyled native table/paragraph/button elements.
- **FR-002**: The diagram editor's page chrome (title field, diagram-type selector, Save action, back navigation) MUST render using ADP's existing styled form-control and button conventions.
- **FR-003**: The diagram editor MUST show a persistent, visible save-state indication (e.g. saved / saving / error) distinct from a momentary label change on the Save control itself.
- **FR-004**: The shape-selection palette MUST use real icons consistent with the icon style already used elsewhere on the same toolbar — not single-character text glyphs.
- **FR-005**: The delete-confirmation dialog MUST render using ADP's existing modal styling.
- **FR-006**: The canvas MUST have a visible surface — a background distinguishing it from the surrounding page chrome, plus a spatial reference pattern (e.g. a grid or dot pattern) so an empty canvas is visibly a workable surface rather than blank page background.
- **FR-007**: The canvas surface (background and spatial reference pattern) MUST visually adapt to the active app theme (light/dark).
- **FR-008**: The DSL text panel MUST render as a distinctly-styled, appropriately-sized panel with its own labeled header — not a bare, minimally-sized native text box.
- **FR-009**: All interaction-only visual states that are never part of an exported diagram (selection outline, marquee/rubber-band selection, hover affordances, resize handles) MUST use the app's actual accent and semantic color tokens, consistent across both themes.
- **FR-010**: Default (non-customized) shape fill and stroke colors MUST remain fixed regardless of the app's active theme — matching the current behavior and the precedent set by ADP's locked C4 rendering theme (ADP-SPEC-010). Only the canvas surface itself (FR-007) adapts to theme; default shape colors do not.
- **FR-011**: A shape's explicitly user-set custom color (chosen via the existing style controls) MUST be preserved exactly through export (SVG/PNG) regardless of the app's theme at export time — unaffected by FR-010, since neither default nor custom shape colors change with theme.
- **FR-012**: The editor MUST provide a workspace layout in which the shape palette, the canvas, and the DSL panel are simultaneously visible and independently usable on supported viewport widths, adapting gracefully on narrower viewports (e.g. a collapsible or toggleable palette or panel) rather than becoming unusable or forcing horizontal scroll of the page itself.
- **FR-013**: The Connect tool MUST show a clear, visually distinct active-state indicator while connect mode is engaged.
- **FR-014**: The screen MUST visually communicate the directionality of canvas↔DSL synchronization: that canvas edits reflect into the DSL panel automatically, and that DSL edits require an explicit action before they reach the canvas.
- **FR-015**: Existing keyboard-accessible interaction affordances (inline shape-label editing, the delete-confirmation dialog's focus handling, toolbar control labeling) MUST be preserved through this redesign, not just visually replicated.
- **FR-016**: This feature MUST NOT modify how diagrams are parsed, validated, or serialized, and MUST NOT modify any backend endpoint, storage shape, or API contract for diagrams.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can visually distinguish the diagram editor as part of ADP (not a separate, unstyled tool) within the first few seconds of opening it — no control on the screen renders with unstyled browser-default chrome.
- **SC-002**: An architect working in dark theme never encounters an unstyled, jarringly bright element on the canvas surface itself.
- **SC-003**: An architect can place, connect, and label shapes while simultaneously reading the corresponding DSL text, without needing to scroll one part of the screen out of view to see another, on a standard desktop viewport.
- **SC-004**: 100% of diagrams saved before this change continue to render identically in the canvas and in export, except for the specific, deliberate color-resolution change made under FR-010/FR-011.
- **SC-005**: Every existing automated test for the diagram editor and list screens continues to pass, and new tests cover each restyled element's presence and each theme-adaptive behavior.

## Assumptions

- **Undo/redo**: out of scope, deferred to a separate follow-up feature. It is a real, confirmed gap (no undo/redo exists anywhere in the current editor), but it is a state-management capability — not a visual restyle — large enough to warrant its own spec (history-stack shape, keybindings, interaction with the DSL-apply flow) rather than expanding this feature's scope.
- **DSL syntax highlighting**: out of scope for this pass. The DSL panel gets real panel chrome (header, sizing, border) per FR-008, but its text content remains plain monospace — adding colorized syntax highlighting is a separate future enhancement, since the problem being fixed is the panel's *container* styling, not a missing capability.
- **Icon-library palette entry point**: out of scope. Placing icon-type nodes (`shape: "icon"`) has no existing UI entry point today, and adding one is a new capability, not a restyle of an existing control — separate from this feature.
- **Selection-stroke color**: resolved, not left open. Confirmed directly (no test in the codebase asserts the current literal selection-stroke hex value), so switching it to the app's actual accent token (FR-009) is a safe default, not a clarification.
- **Zoom/pan**: remains out of scope, per the source material — absent both in ADP's current editor and in the reference implementation it was adapted from; only revisited if the canvas-surface work (FR-006/FR-007) makes it clearly necessary alongside it.
- **Version history, share dialog, per-diagram details modal**: out of scope — these exist in the reference implementation this screen was adapted from, but ADP's backend has no supporting data for them; this feature does not add UI for capabilities the backend doesn't support.
- **Vendored parsing/rendering engine**: entirely untouched (FR-016) — this feature is scoped to presentation only.
