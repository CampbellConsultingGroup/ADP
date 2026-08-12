# Quickstart: Diagram Editor Visual & Workspace Redesign

Browser-based verification (this feature has no API surface — FR-016). Assumes the local dev
stack is running (`web/` on :5173, API on :8001) and at least one business capability exists (for
parity with other screens' seed data; not required by this feature specifically).

## Scenario 1: List screen matches ADP's conventions (User Story 1, Acceptance Scenario 1)

1. Navigate to Diagrams.
2. Confirm the empty state (if no diagrams exist) renders with ADP's dashed-border `.ui-empty`
   treatment, not a bare `<p>`.
3. Create a diagram, save it, return to the list.
4. Confirm it renders as a styled list row (title, type, updated date, Open/Delete actions) — not
   an HTML table with default browser cell borders.

## Scenario 2: Editor chrome matches ADP's conventions (User Story 1, Acceptance Scenarios 2–4)

1. Open a diagram in the editor.
2. Confirm the title field, diagram-type dropdown, and Save button render with ADP's styled
   input/select/button treatment (rounded corners, token colors, focus ring on click) — not
   browser-default form chrome.
3. Click Save; confirm a persistent save-state indicator appears (not just a transient button
   label change) and remains visible after the save completes.
4. Trigger the delete-confirmation dialog (from the list screen); confirm it renders with styled
   modal chrome (header, body, footer, Cancel/Confirm actions) — not a bare native dialog.

## Scenario 3: Theme-correct canvas surface (User Story 2, Acceptance Scenarios 1–2)

1. Open a diagram with a few shapes placed, in light theme.
2. Toggle to dark theme (top-bar theme toggle).
3. Confirm the canvas background and its spatial reference grid/dots visibly change to a
   dark-appropriate tone — not the same fixed appearance as light mode.
4. Confirm shape fill/stroke colors do **not** change with the toggle (FR-010's resolved
   requirement — fixed regardless of theme) — this is expected, correct behavior, not a bug to
   chase.

## Scenario 4: Custom colors survive export regardless of theme (User Story 2, Acceptance Scenario 3)

1. Set an explicit custom color on a shape via the style popover.
2. Toggle the app theme.
3. Export the diagram (SVG or PNG).
4. Confirm the exported artifact shows the exact custom color chosen in step 1, unaffected by
   which theme was active at export time.

## Scenario 5: Interaction-state colors use the accent token (User Story 2, Acceptance Scenario 4)

1. Select a shape; confirm its selection outline renders in ADP's actual accent color (matches
   the accent color visible elsewhere in the app chrome, e.g. active nav item) in both themes.
2. Drag a marquee selection over multiple shapes; confirm the marquee rectangle uses the same
   accent-derived styling.

## Scenario 6: Workspace layout keeps palette, canvas, and DSL simultaneously usable (User Story 3, Acceptance Scenario 1)

1. Open the editor at a standard desktop viewport width with several shapes already placed.
2. Confirm the shape palette, the canvas, and the DSL panel are all visible and independently
   scrollable/usable at the same time — no need to scroll the palette out of view to reach the
   canvas, or vice versa for the DSL panel.
3. Narrow the browser window below the shell's existing responsive breakpoint; confirm the palette
   degrades gracefully (e.g. collapses to a toggle) rather than the page becoming unusable or
   requiring horizontal scroll.

## Scenario 7: Connect-mode and sync-direction affordances (User Story 3, Acceptance Scenarios 2–4)

1. Click Connect; confirm the button shows a clear active/pressed visual state while engaged.
2. Edit the canvas (move or add a shape); confirm the DSL panel visibly updates automatically.
3. Edit the DSL text directly; confirm the screen visibly communicates that an explicit action
   (Apply) is required before the canvas reflects the change — distinct from the live-updating
   direction in step 2.

## Scenario 8: Automated regression check

```bash
cd web && npx vitest run src/diagrams/ && npx tsc --noEmit && npm run test:run
```
