Redesign ADP's diagram-building screen (`web/src/diagrams/DiagramListPage.tsx` +
`DiagramEditorPage.tsx` + the editor chrome under `web/src/diagrams/editor/`)
so it reads as part of ADP rather than as an unstyled prototype bolted onto
the app, without touching the vendored parsing/rendering engine underneath
it.

## Why

The diagram screen was added across four features (ADP-914.5–914.8,
specs 046–049) by vendoring a React editor from a sibling diagramming
project (`/home/jmuir/projects/canvas`, see `web/src/diagrams/README.md`)
and wiring it into ADP's nav. The vendored components (`Canvas.tsx`,
`DslPanel.tsx`, `shapes.tsx`, `ConfirmDialog.tsx`) still reference the
sibling project's own CSS class vocabulary — `.btn`, `.btn--secondary`,
`.card`, `.cluster`, `.panel`, `.panel__body`, `.panel__footer`,
`.rail-section`, `.rail-section__label`, `.shape-grid`, `.tool-list`,
`.field__label`, `.canvas-root`, `.canvas-svg`, `.canvas-edit-affordance`,
`.dsl-panel__editor`, `.modal`/`.modal__header`/`.modal__title` — but the
stylesheets that define those classes in the sibling project
(`apps/web/src/styles/base.css`, `components.css`, `layout.css`) were never
ported. Confirmed by grep: **zero `.css` files exist anywhere under
`web/src/diagrams/`**, and none of the above class names appear in any of
ADP's own stylesheets (`web/src/ui/tokens.css`, `web/src/ui/ui.css`,
`web/src/overview/overview.css`). Every element carrying one of those
classNames is, today, styled by nothing but the browser's user-agent
defaults. That is the root cause of the "every control looks like raw
HTML" impression in the screenshots — this is not a "needs a polish pass"
problem, it's a styling layer that was never brought over.

Specific, file-grounded problems:

1. **Shape picker is 11 Unicode glyphs, not icons.** `Canvas.tsx`'s
   `SHAPE_GLYPHS` constant (lines 38–50) maps each `NodeShape` to a
   character — `▭ ▢ ○ ◇ ⬭ ⊟ ◎ ⬡ ▱ ⏢ ⌂` — rendered directly as button text.
   These are font-dependent, inconsistently weighted, and small. ADP
   already has a proper icon system used two lines away in the same
   toolbar: the `Connect`/`Add Container`/`Group into Container`/
   `Delete Selected`/`Auto Layout` buttons use `<Icon name="..." />` from
   `web/src/diagrams/editor/ui/Icon.tsx` (a clean 16×16 stroke-based SVG
   set, `stroke="currentColor"`, no external CSS dependency — it renders
   correctly today because it needs none). The shape palette simply never
   adopted it.

2. **Every editor control is unstyled native HTML**, confirmed directly
   from the screenshots: the title `<input>`, the diagram-type `<select>`,
   Save/Chat/Connect/Add Container/Group/Delete buttons, the "Layout
   Direction" `<select>`, and the DSL `<textarea>` all render with
   browser-default chrome (square corners, default font, no color) —
   directly beneath ADP's own fully-styled nav rail, breadcrumb, search
   box, and theme toggle. The contrast is the single most obvious problem
   in every screenshot.

3. **Diagram node fills/strokes are hardcoded hex, not theme tokens** —
   `shapes.tsx` line 28: `const fill = node.style?.fillColor ?? '#ffffff'`
   and line 29: `const stroke = selected ? SELECTION_STROKE :
   (node.style?.strokeColor ?? '#333333')`. Confirmed directly from the
   dark-theme screenshot: the three demo nodes render as solid white boxes
   with black borders/text on a near-black canvas — correct in light mode,
   jarring in dark mode. Notably, the comment directly above this code
   (lines 14–22) documents that node fill/stroke are *deliberately*
   untouched because they "come from admin-defined standards and are
   produced by both renderers, which must agree for exports to match the
   canvas" — a real, intentional constraint from the sibling project,
   which is itself a **single-theme, light-only app** (its
   `apps/web/src/styles/tokens.css` has no dark-mode block at all, and
   explicitly documents `--surface-canvas` staying "white so those
   admin-chosen colours render truthfully"). ADP added a real light/dark
   toggle this vendored code was never adapted for, so the sibling
   project's deliberate light-only decision became an unintended dark-mode
   bug once transplanted.

4. **The canvas has no visible surface at all.** No background-color, no
   border, no boundary of any kind — nodes float directly on the page
   background (`var(--bg)`, the same color as the space around the shell's
   content area). Compare the sibling's `.editor__canvas`
   (`apps/web/src/styles/layout.css` lines 248–258): explicit
   `background-color: var(--surface-canvas)` plus a dot-grid
   (`radial-gradient(circle, var(--canvas-grid-dot) 1px, transparent 1px)`
   sized by `--canvas-grid-size`) for spatial reference while placing
   shapes. ADP has neither.

5. **The DSL panel is a bare, tiny `<textarea>`** (`DslPanel.tsx`) — the
   `dsl-panel__editor` className resolves to nothing, so it renders at the
   browser's default `<textarea>` size (visible resize handle in the
   screenshots) with no syntax highlighting, no distinguishing header, and
   no visual separation from the canvas above it — it just sits at the
   bottom of the same scrolling column.

6. **The list screen is a raw `<table>`** (`DiagramListPage.tsx`) with
   unstyled `<th>`/`<td>` and native buttons for opening a row or
   deleting it, and a bare `<p>No diagrams yet.</p>` empty state. ADP
   already has an established list convention other screens use —
   `.ui-list`/`.ui-list-row` and `.ui-empty` (`web/src/ui/ui.css` lines
   114–125), used today by `web/src/knowledge/KnowledgePage.tsx` and
   `web/src/designs/DesignsPage.tsx` — the diagram list adopts none of it.

7. **The whole editor is one scrolling vertical column**, not a workspace
   layout: title row → "Shapes" label → shape grid → "Tools" label → tool
   list → optional chat panel → parse errors → the canvas `<svg>` → the
   DSL textarea → export buttons, all stacked top-to-bottom. On a
   populated diagram, the shape palette and tool list permanently occupy
   vertical space above the canvas rather than sitting beside it, and the
   DSL text — which `useDslSync` keeps live in sync with the canvas on
   every model change — is pushed below the fold, invisible while actively
   working the canvas above it. This is a structural issue, not just a
   missing-CSS one: even with full styling applied, this layout would
   still not read as a diagram editor.

8. **`DiagramsPage.tsx`'s own list/editor shell chrome is unstyled inline
   JSX** — `<div style={{ padding: 16 }}>`, a plain `<button>` for "← Back
   to diagrams," a plain `<h2>`/`<button>` "+ New Diagram" row — none of
   it uses ADP's `.ui-page`/`.ui-toolbar`/`.ui-h1` pattern that
   `DesignsPage.tsx` already establishes for an almost identical
   list-plus-create-affordance screen.

## What to build

Restyle and restructure the diagram list screen and editor screen to match
ADP's own visual language — reusing `web/src/ui/tokens.css`,
`web/src/ui/ui.css`, and the `Button`/`Card`/`Panel`/`StatusBadge`/
`PageHeader`/`Icon` components exported from `web/src/ui/index.ts` wherever
they already cover a need, the same way `web/src/designs/DesignsPage.tsx`
does for its own list-plus-create-form screen. Where the editor's workspace
needs (a multi-pane layout, a canvas surface with spatial reference marks,
a DSL/inspector rail, a real icon-based shape palette) aren't covered by
anything that exists today, add new CSS that follows `ui.css`'s own
conventions — token-driven (`var(--space-*)`, `var(--radius*)`,
`var(--surface-*)`, `var(--ink*)`, `var(--accent*)`), not new hardcoded
values — in a new stylesheet scoped to this feature (mirroring how
`overview.css` is scoped to `OverviewPage`) rather than growing `ui.css`
unboundedly. Treat the sibling project's own editor
(`canvas/apps/web/src/app/DiagramEditor.tsx` + its `layout.css`/
`components.css`) as a reference for *what makes a diagram editor read as
professional* — a persistent palette rail, a bounded/gridded canvas
surface, a dedicated inspector rail rather than a panel appended below the
fold — not as a literal design to transplant. **The final implementation
does not need to match the sibling project's actual solution** — same
lessons, ADP's own tokens and components, and ADP's own judgment on
specifics like panel tabs, export menu shape, etc.

Concretely, in scope:

- **List screen** (`DiagramListPage.tsx`): replace the raw `<table>` with
  ADP's `.ui-list`/`.ui-list-row` pattern (as `DesignsPage.tsx` and
  `KnowledgePage.tsx` already do), the `.ui-empty` empty state instead of
  a bare `<p>`, and `Button`/`Icon` from `web/src/ui` for the New Diagram
  and per-row Delete actions. `DiagramsPage.tsx`'s wrapping chrome (page
  title, "+ New Diagram", "← Back to diagrams") should adopt
  `.ui-page`/`.ui-toolbar`/`.ui-h1`/`.ui-subtle` the same way
  `DesignsPage.tsx` does.

- **Editor page chrome** (`DiagramEditorPage.tsx`): title input, diagram
  type select, and Save button restyled with `.ui-input`/`.ui-select`/
  `Button`; some visible save-state feedback (the sibling's `DiagramEditor`
  shows an idle/saving/saved/error status pill next to Save — ADP's
  current version only swaps the Save button's own label to "Saving…" with
  no persistent state indicator once saved).

- **Shape palette**: replace `SHAPE_GLYPHS` Unicode characters with real
  SVG icons following the same pattern as `editor/ui/Icon.tsx`'s existing
  16×16 stroke icon set (extend that file's icon vocabulary — it already
  demonstrates the right approach, it's just missing shape glyphs), laid
  out in a labeled grid consistent with `.ui-panel`'s heading treatment.

- **Toolbar/tools organization**: give "Shapes" and "Tools" (Connect, Add
  Container, Group, Delete Selected, Layout Direction, Auto Layout) a
  persistent rail treatment (a left-hand palette column, in the spirit of
  the sibling's `.editor__rail-left`) rather than a stacked block above
  the canvas, so the canvas is not competing with the palette for vertical
  space on a populated diagram.

- **Canvas surface**: give it a real background (`var(--surface)` or a
  purpose-specific canvas-surface token — see the Theme section below), a
  visible boundary/border, and a spatial reference pattern (dot or grid)
  so an empty canvas doesn't read as "nothing rendered" and shape
  placement has visual reference points — matching what the dot-grid
  achieves in the sibling project, expressed via ADP's own token names.

- **DSL panel**: give it a dedicated, appropriately-sized panel treatment
  (not a 3-row native textarea with a visible resize handle) with a
  labeled header distinguishing it from the canvas, using `.ui-panel`/
  monospace token (`var(--mono)`) styling; keep the existing Apply-button
  gate on canvas→DSL edits (see the Human Workflow section — this is
  existing, correct behavior, not a bug).

- **Layout structure**: move from one scrolling column to a workspace
  layout — palette rail, canvas (with its own scroll/overflow region), and
  a DSL/inspector rail sized so the DSL text stays visible while the
  canvas is being edited, not pushed below the fold. Whether this is a
  fixed 3-column CSS grid (as the sibling does) or something else that
  fits better inside ADP's existing `.shell-content` frame is left to the
  person specifying this — see Open Questions.

- **Modal/dialog treatment**: `ConfirmDialog.tsx`/`ui/Modal.tsx` (used for
  delete confirmation) should get real styling for `.modal`,
  `.modal__header`, `.modal__title`, `.modal__body`, `.modal__footer` —
  currently also unstyled native `<dialog>` chrome for the same "class
  doesn't exist" reason as everything else on this screen.

- **Human workflow, not just appearance** — verified against the current
  code, so the redesign preserves what already works and fixes what's
  genuinely missing or badly communicated:
  - *Connecting nodes*: Connect mode exists (`Canvas.tsx`
    `handleNodePointerDown`) with a direction picker (forward/reversed/
    bidirectional/no-arrowhead) — functionally solid, needs visual
    affordance (a pressed/active toggle state on the Connect button, a
    connect-mode cursor/canvas outline) once real button styling exists.
  - *Editing a node's label*: inline on canvas via double-click or a
    hover/selection-revealed pencil affordance (`renderEditAffordance`) —
    no side panel exists for this today, and nothing in this pass should
    add one; this is a screen-real-estate/visual-treatment problem for the
    pencil/palette icon buttons (`.canvas-edit-affordance`, currently
    unstyled), not a missing-feature problem.
  - *Selection feedback*: single-select, multi-select (Shift/Ctrl/Cmd
    click), and marquee (rubber-band) selection all exist; selected shapes
    get a `SELECTION_STROKE` (`#2563eb`, hardcoded — should become
    `var(--accent)` so selection color tracks the app's actual accent
    token instead of a value that happens to currently match it).
  - *Undo/redo*: **does not exist anywhere in this code** — confirmed by
    grep (no `undo`/`redo` state, no Ctrl/Cmd+Z handling in
    `handleKeyDown`; only Delete/Backspace is handled, with an in-app
    confirm dialog as the sole safety net, and its own copy literally says
    "This cannot be undone"). Flagged for a scoping decision — see Open
    Questions — because it's a substantial workflow gap but may be a
    separate feature from a visual redesign.
  - *Canvas↔DSL sync*: canvas→DSL is live (`useDslSync`'s `dsl` is
    `useMemo`-derived from `model` on every change) — the DSL panel always
    reflects the current canvas state in real time. DSL→canvas is
    **not** live — it requires an explicit "Apply" button click
    (`DslPanel.tsx`), which is correct/intentional (avoids applying
    invalid/mid-typing DSL to the canvas), but this asymmetry is currently
    not visually communicated at all — nothing distinguishes "this side
    updates live" from "this side needs an explicit action," and a user
    could reasonably expect either. The redesign should make this
    directionality visible (e.g., a live indicator/label on the DSL
    panel, more prominent Apply affordance).
  - *Unsupported/error DSL surfacing*: `UnsupportedElementNotice.tsx`
    already reports line + content + message for parse failures — keep
    this behavior, just give it `.ui-alert`-consistent styling instead of
    inline `style={{ color: '#b00020' }}` (also not a token).
  - *Save/export flow*: Save persists title + DSL (`DiagramEditorPage.tsx`
    `handleSave`); Export SVG/PNG (`ExportAction.tsx`) only appears after
    a diagram has a `savedId` — both plain unstyled buttons today with no
    visual hierarchy between them (Save is the primary action, Export is
    secondary) — apply that hierarchy through `Button`'s `variant` prop.
  - *Zoom/pan*: **neither exists today**, in ADP's copy or the sibling's
    own `Canvas.tsx`/`layout.css` (grepped both — no zoom/scale state, no
    wheel handler; panning is native browser scroll inside an
    `overflow: auto` container as the canvas's own computed size grows
    past the viewport). This is a shared gap, not something ADP is
    missing relative to what it vendored from — treat as explicitly out
    of scope for this pass (see below) unless the canvas surface work
    above makes it clearly necessary to address alongside it.

### Theme considerations (dark and light)

This needs to be resolved deliberately, not defaulted silently, because
the two halves of this screen have genuinely different constraints:

- **App chrome** (toolbar, panels, list, DSL panel frame, modals): should
  be fully theme-aware via the same `var(--surface)`/`var(--ink)`/
  `var(--border)`/`var(--accent)` tokens every other ADP screen already
  uses — no open question here, this is exactly what `tokens.css`'s
  light/dark blocks exist for.

- **Diagram node/shape content** (fill, stroke, label text) is the real
  tension. Today's answer is "fixed light-mode hex, never changes" — a bug
  in dark mode, confirmed by the screenshots. But simply making node
  fill/stroke fully theme-reactive isn't obviously correct either:
  `shapes.tsx`'s own comment documents that these values are meant to
  come from **admin-defined standards** and must match exactly what the
  export renderer (`core/render/svg-renderer.ts`) produces, because a
  human viewing a saved/exported diagram (PNG/SVG, embedded in a doc or
  wiki page) needs it to look the same regardless of what theme the
  *editor* happened to be in when it was authored — an exported artifact
  has no "dark mode." ADP has direct precedent for exactly this tension
  already: ADP-SPEC-010 (locked-theme C4 rendering) deliberately fixes
  container fill (`#2874A6`) for WCAG-AA-verified consistency across
  renders, rather than letting it vary with viewer theme. The person
  architecting a diagram at night in dark mode needs a canvas that isn't
  a jarring white rectangle in an otherwise-dark app — but the artifact
  they eventually export needs to look right on its own, independent of
  editor theme. This tradeoff has no single obviously-correct resolution
  and is called out explicitly in Open Questions below, with two concrete
  directions to choose between (or a hybrid): (a) the canvas **surface**
  (background/grid) is theme-aware even though authored node fill/stroke
  colors stay fixed/admin-defined regardless of app theme (closest to
  today's actual constraint, and to the sibling project's own explicit
  design), or (b) node default fill/stroke (only when the user hasn't
  explicitly picked a custom color via the style popup) become
  theme-reactive tokens, while an explicit user-chosen color always wins
  and is preserved verbatim through export.

- **Canvas surface** itself (background + grid): should be theme-aware
  regardless of which direction is chosen for node content above — a
  `--surface-canvas`-equivalent ADP token (light: a card-like surface
  tone, dark: a comparably dim tone, not `var(--bg)` which is what it
  effectively renders as today) plus a dot/grid pattern keyed to a
  low-contrast border-family token in each theme, mirroring the sibling's
  `--canvas-grid-dot`/`--canvas-grid-size` approach but named per ADP's
  own token conventions.

- **DSL panel**: plain text today, no syntax highlighting, so no
  additional theme risk right now — but if real syntax highlighting is
  added as part of this pass (not required — see Open Questions), its
  token colors must be defined for both themes from the start, not
  authored once in light and left to look wrong in dark.

- **Selection, hover, and other screen-only affordances** (selection
  stroke, marquee rectangle, pencil/palette hover buttons, resize
  handles): these are never exported, so they have no light/dark tension
  at all — they should simply use `var(--accent)` and friends like every
  other interactive element in ADP, replacing the current hardcoded
  `#2563eb`/`#888`/`#333` values in `Canvas.tsx`.

### Explicitly out of scope for this change

- **Any change to `web/src/diagrams/core/`** (the vendored parser/
  serializer/DSL-family engine) — this is a visual/interaction redesign
  of the chrome and canvas presentation, not a change to how diagrams are
  parsed, validated, or serialized. Per `web/src/diagrams/README.md`, that
  package is meant to stay a low-diff mirror of the sibling project's
  `packages/diagram-core`.
- **Undo/redo** — a real gap (confirmed absent), but a state-management
  feature, not a visual restyle; whether it belongs in this pass or a
  follow-up is an open question below, not something to silently add or
  silently skip.
- **Zoom/pan controls** — absent in both ADP's copy and the sibling
  project's own editor; out of scope unless the canvas-surface work makes
  it clearly necessary to address together (see above).
- **The sibling project's `ViolationsPanel.tsx`** (admin-defined Standards
  surface) — already explicitly deferred per `web/src/diagrams/README.md`
  ("out of scope for v1... not an oversight"); this redesign should not
  reintroduce it.
- **Version history / restore, Share dialog, per-diagram Details modal
  (owner/created-date/description)** — all present in the sibling's own
  `DiagramEditor.tsx` but with no equivalent data or backend support in
  ADP's `src/adp/diagrams/` today; do not add UI for capabilities ADP's
  backend doesn't have.
- **Icon-library palette** (the sibling's `Palette.tsx`, offering a
  searchable icon library for `shape: 'icon'` nodes) — ADP's editor
  supports rendering icon nodes (`Canvas.tsx`'s `iconArtwork`/
  `getLibraryIcons` machinery) but has no UI entry point to *place* one;
  whether that's part of this redesign or a separate feature is an open
  question below, not something to build silently as a side effect of
  restyling.
- **Backend/API changes** — `src/adp/diagrams/` (router, store, export
  endpoint) is untouched by this work; every change here is
  frontend-only.

## Constraints to respect

- Reuse `web/src/ui/tokens.css` custom properties exclusively for color,
  spacing, radius, and typography — no new hardcoded hex values or pixel
  literals where a token already exists for the purpose (the exact
  problem being fixed in `shapes.tsx`/`Canvas.tsx` today).
- Reuse `Button`, `Card`, `Panel`, `StatusBadge`, `PageHeader`, `Icon` from
  `web/src/ui/index.ts` wherever the need matches what they already do —
  follow `web/src/designs/DesignsPage.tsx` as the closest existing
  precedent for a list-plus-create-form screen structure. Do not
  reimplement a second button/badge/panel system under `web/src/diagrams/`
  once a first-party equivalent exists.
- New, workspace-specific CSS (palette rail, canvas surface, DSL/inspector
  rail) should live in a stylesheet scoped to this feature, following
  `ui.css`'s naming and token-usage conventions, not a copy of the sibling
  project's `base.css`/`components.css`/`layout.css` files or class names.
- `web/src/diagrams/core/` (vendored diagram-core parser/serializer) must
  not be modified as part of this work.
- `web/src/diagrams/editor/ui/Icon.tsx` is a working, dependency-free icon
  component — extend its icon set rather than introducing a second icon
  mechanism, an icon font, or an external icon package.
- Any node-content color change (theme-reactive defaults, if that
  direction is chosen) must not alter what a *saved* diagram exports to
  SVG/PNG unless a corresponding, deliberate decision is made about
  export-time color resolution — `core/render/svg-renderer.ts` and the
  canvas (`shapes.tsx`) must keep agreeing on what a diagram "looks like"
  per the existing SC-004 consistency requirement referenced throughout
  the vendored code's comments.
- Accessibility: the existing keyboard-reachable edit affordances
  (`renderEditAffordance`, hover-and-focus-revealed, per
  `Canvas.tsx`'s FR-017 comment), the native `<dialog>`-based modal's
  focus trap (`ui/Modal.tsx`), and ARIA labeling already present on
  toolbar controls must be preserved through the restyle, not just
  visually replicated.

## Open questions to resolve during specification

1. **Node/shape default color theming**: should default (non-custom)
   node fill/stroke become theme-reactive tokens, or should the canvas
   deliberately stay on a fixed light ground (mirroring the sibling
   project's own explicit single-theme decision and ADP's own
   locked-theme-rendering precedent for C4 diagrams), with only the
   canvas *surface* (background/grid) reacting to app theme? This is the
   single highest-impact decision in this spec and has real tradeoffs on
   both sides (see Theme Considerations above) — it should not be decided
   implicitly by whoever implements it.
2. **Undo/redo**: is closing this gap part of this redesign, or a
   separately-scoped follow-up feature? It's a real, confirmed absence
   (not a visual issue), and its scope (history stack shape, keyboard
   binding, interaction with the DSL-apply flow) is large enough that
   bundling it into a visual redesign risks scope creep either way —
   needs an explicit yes/no before `/speckit-specify` proceeds.
3. **Editor layout shape**: a fixed 3-column CSS grid (palette rail /
   canvas / DSL rail, mirroring the sibling's `.editor__body`), or
   something more adaptive to ADP's own shell (e.g. a collapsible palette,
   given `.shell-content` is the only available vertical real estate and
   ADP's nav rail already consumes horizontal space the sibling app
   didn't have to share)? Worth deciding before layout CSS is written,
   since it affects minimum supported viewport width.
4. **DSL syntax highlighting**: in scope for this pass, or left as plain
   monospace text (current behavior) with only the panel chrome restyled?
   If in scope, its token colors need first-class light/dark definitions
   from day one per the Theme Considerations section.
5. **Icon-library palette entry point**: `Canvas.tsx` already has the
   plumbing to render icon nodes (`iconArtwork`, `getLibraryIcons`) but no
   UI to place one — is adding that entry point part of this redesign
   (since it's arguably a "shape palette" completeness gap under the same
   heading as the Unicode-glyph fix), or a separate feature?
6. **Selection-stroke color**: `Canvas.tsx`'s hardcoded `SELECTION_STROKE`
   (`#2563eb`) does **not** match ADP's actual `--accent` token
   (`#2874A6` in light mode, `#4aa3d8` in dark) — switching it to
   `var(--accent)` is a genuine, visible color change (not just a
   token-naming cleanup), and selection-stroke is exactly the kind of
   thing an existing Playwright/visual test could assert a literal value
   against. Confirm against `web/src/diagrams/editor/**/*.test.ts` (and
   any Playwright specs under `web/tests/e2e`) whether anything pins the
   current literal color before treating this as a safe default.
