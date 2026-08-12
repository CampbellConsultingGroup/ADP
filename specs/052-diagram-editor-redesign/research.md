# Research: Diagram Editor Visual & Workspace Redesign

## Decision 1: Restyle vendored components via a new stylesheet targeting their existing class names — never edit their JSX

**Decision**: `web/src/diagrams/editor/Canvas.tsx`, `shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`,
`ConfirmDialog.tsx`, and `UnsupportedElementNotice.tsx` (the six files `web/src/diagrams/README.md`
confirms are vendored from the sibling project) keep every `className` they already emit — a new
stylesheet, `web/src/diagrams/diagrams.css`, supplies real CSS definitions for those exact class
names (`.btn`/`.btn--primary`/`.btn--secondary`/`.btn--tertiary`/`.btn--danger`/`.btn--compact`,
`.canvas-root`, `.canvas-svg`, `.canvas-edit-affordance`, `.card`/`.cluster`, `.field__label`,
`.rail-section`/`.rail-section__label`, `.shape-grid`, `.tool-list`, `.panel`/`.panel__body`/
`.panel__body--flush`/`.panel__footer`, `.dsl-panel`/`.dsl-panel__editor`, `.modal`/`.modal--wide`/
`.modal__header`/`.modal__title`/`.modal__body`/`.modal__footer`), using ADP's own token values —
catalogued exhaustively by grepping every `className=` in these six files (contracts/
diagram-css-contract.md lists the full, verified set).

**Rationale**: This is the literal, minimal-diff realization of the vendoring convention
`README.md` already states as policy — "a future re-sync stays a clean diff" — and of this
feature's own Constraints (spec.md: `web/src/diagrams/core/` must not be modified; vendored files
are not core, but the same low-diff spirit applies). The vendored components already have real,
working structure and behavior (connect mode, multi-select, marquee selection, keyboard
accessibility, the native-`<dialog>`-based modal's focus trap) — they are missing exactly one
thing, a stylesheet, confirmed directly: **zero `.css` files exist anywhere under
`web/src/diagrams/`** (`find` returns nothing). Supplying that one missing layer fixes the "looks
unstyled" problem for these six files without touching a single line of vendored markup.

**Alternatives considered**:
- *Edit the vendored files' JSX to use ADP's own `.ui-*` classes directly* — rejected. This is
  exactly the kind of change `README.md` warns against ("if the upstream library gains a fix... re-
  copy... rather than patching the vendored copy in place"); it would also mean two divergent
  class-naming conventions to keep straight (ADP's `.ui-*` BEM-lite for ADP-authored files, vs. the
  sibling's `.btn--*`/`.panel__*` for vendored ones) if done inconsistently, or a genuinely large,
  regression-risky JSX diff across 1,200+ lines of `Canvas.tsx` alone if done consistently.
- *Fork the sibling project's own stylesheets wholesale (`base.css`/`components.css`/`layout.css`)
  into ADP* — rejected per spec.md's own Constraints ("not a copy of the sibling project's
  ... files or class names") — those files carry the sibling app's own token system, font choices,
  and unrelated component styles (e.g. a `Palette.tsx`/`ViolationsPanel.tsx` ADP doesn't use);
  copying them wholesale would import a second design system wholesale rather than express ADP's
  own.

## Decision 2: ADP-authored chrome files (list/editor page wrappers) are rewritten directly to use ADP's existing `.ui-*` classes and shared components

**Decision**: `DiagramListPage.tsx`, `DiagramsPage.tsx`, and `DiagramEditorPage.tsx` (confirmed
ADP-authored, not vendored, per `README.md`) are edited directly — their raw `<table>`, bare
`<div style={{...}}>` wrapper, inline `<button>`/`<input>`/`<select>` elements are replaced with
`web/src/ui`'s existing `Button`/`Card`/`Icon`/`StatusBadge`, and the `.ui-page`/`.ui-toolbar`/
`.ui-h1`/`.ui-subtle`/`.ui-list`/`.ui-list-row`/`.ui-empty`/`.ui-input`/`.ui-select`/`.ui-alert`
classes — the exact pattern `web/src/designs/DesignsPage.tsx` already demonstrates for a
near-identical list-plus-create-affordance screen (read in full: 140 lines, confirmed as the
closest existing precedent named in spec.md's Constraints).

**Rationale**: Unlike the vendored editor internals, these three files are small (75/70/202
lines), fully owned by ADP, and already inconsistent with ADP's own conventions in ways a "new
stylesheet only" fix can't reach — e.g. `DiagramListPage.tsx`'s list uses plain `useState`/
`useEffect` fetch calls against `./api` directly rather than the TanStack Query hooks every other
ADP list screen uses (`useDesignList` in `DesignsPage.tsx`), and its raw `<table>` structure has
no equivalent in `.ui-list`'s row-based shape — these need real JSX restructuring, not just new
CSS. Editing them carries no vendoring risk since ADP already owns them outright.

**Alternatives considered**:
- *Also give these three files their own scoped classes in `diagrams.css`, styled to resemble
  `.ui-*` without directly reusing it* — rejected: would create a second, parallel implementation
  of list-row/button/badge/panel styling only cosmetically compatible with the rest of ADP,
  violating spec.md's own Constraint ("do not reimplement a second button/badge/panel system").

## Decision 3: Canvas surface and grid use ADP's existing tokens — no new CSS custom properties needed

**Decision**: The canvas background reuses `var(--surface-2)` (a subtly-recessed surface tone
already used elsewhere for secondary panels), its border reuses `var(--border)`, and the
spatial-reference dot/grid pattern is a `radial-gradient` keyed to `var(--border)` at low density
— all read directly from `web/src/ui/tokens.css` (read in full: 74 lines, complete token
inventory confirmed). No new custom property is added to `tokens.css`.

**Rationale**: The sibling project needed dedicated `--surface-canvas`/`--canvas-grid-dot`/
`--canvas-grid-size` tokens because its own `tokens.css` has no equivalent "recessed surface" tone
to reuse. ADP's token set already has one (`--surface-2`/`--surface-3`, used today by
`overview.css` for secondary panel backgrounds) — reusing it satisfies spec.md's Constraint
("reuse `tokens.css` ... no new hardcoded values") more precisely than inventing single-purpose
tokens for a concept ADP's palette already covers, and keeps this feature from growing the global
token surface for a need scoped to one screen.

**Alternatives considered**:
- *Add dedicated `--surface-canvas`/`--canvas-grid-dot` tokens mirroring the sibling's naming* —
  rejected as unnecessary: `--surface-2`/`--border` already read correctly as a recessed,
  low-contrast surface + grid-dot color in both themes (confirmed by inspecting both the light and
  `@media (prefers-color-scheme: dark)` blocks); a purpose-named token would be justified only if
  the canvas needed a shade `tokens.css` doesn't already have, which it doesn't.

## Decision 4: Default shape colors resolved to stay theme-independent (FR-010) — implementation implication

**Decision**: `shapes.tsx`'s `fill = node.style?.fillColor ?? '#ffffff'` / `stroke = ... ??
'#333333'` defaults are **left as literal, fixed hex values** — not swapped for `var(--surface)`/
`var(--ink)` tokens, and not modified at all as part of this feature, per spec.md FR-010
(resolved: default shape colors stay theme-independent, matching ADP's own locked-C4-theme
precedent, ADP-SPEC-010).

**Rationale**: This was the single highest-impact open question in spec.md, already resolved with
the user before planning began (spec.md's own record of the decision). Recorded here only to make
explicit what it means for implementation: **no code change to `shapes.tsx`'s color defaults is
in scope for this feature at all** — the "dark-mode white box" appearance for default-colored
shapes is not eliminated by this feature, only the canvas *surface* around those shapes becomes
theme-correct (Decision 3). This is a deliberate, already-made product decision, not an oversight
to flag again.

**Alternatives considered**: None — already resolved via the clarification round in spec.md; not
re-litigated here.

## Decision 5: Workspace layout uses a responsive CSS Grid, collapsing at the same breakpoint ADP's own shell already uses

**Decision**: The editor's three regions (palette rail, canvas, DSL panel) are laid out with CSS
Grid (`grid-template-columns`) at desktop widths, wide enough to show all three simultaneously
(FR-012). Below `900px`, the palette rail collapses to a toggleable drawer (a disclosure button
reveals/hides it over the canvas) rather than the three columns simply stacking — mirroring
`ui.css`'s own existing `@media (max-width: 900px)` breakpoint, which already collapses ADP's nav
rail from a fixed sidebar to a horizontal scroll strip at exactly this width (read directly:
`ui.css` lines 42–48).

**Rationale**: Reusing the app's own already-established responsive breakpoint (rather than
picking a new one specific to this screen) keeps the diagram editor's responsive behavior
consistent with how the rest of the shell already degrades, and directly answers spec.md's own
open question about minimum supported viewport width by pointing at a width ADP has already
committed to supporting well. A collapsible palette (not the DSL panel or canvas) is chosen as the
element that yields space first, since the canvas is the primary work surface and the DSL panel is
explicitly required to "stay visible while the canvas is being edited" (source input document,
now spec.md's User Story 3) — the palette is the one region an architect consults intermittently
(pick a shape, then work the canvas) rather than continuously.

**Alternatives considered**:
- *A brand-new breakpoint chosen specifically for this screen* — rejected: no evidence the
  three-pane workspace needs to collapse at a different width than the rest of the shell already
  does, and a second breakpoint value adds a second thing to keep in sync as ADP's own responsive
  conventions evolve.
- *Stack all three regions vertically on narrow viewports (today's actual current behavior)* —
  rejected: this is precisely what FR-012 requires moving away from; stacking three regions
  vertically at any width reintroduces the "scroll one out of view to use another" problem this
  feature exists to fix.

## Decision 6: Modal styling is added directly to `diagrams.css`, not to global `ui.css`

**Decision**: `.modal`/`.modal--wide`/`.modal__header`/`.modal__title`/`.modal__body`/
`.modal__footer` (the classes `web/src/diagrams/editor/ui/Modal.tsx` — confirmed ADP-authored, not
in `README.md`'s vendored list — already emits) get their CSS definitions inside the new
`diagrams.css`, not added to the shared `web/src/ui/ui.css`, even though `Modal.tsx` is generic
enough that another screen could theoretically reuse it later.

**Rationale**: No other ADP screen uses a `<dialog>`-based modal with this exact class
vocabulary today (confirmed: `web/src/diagrams/editor/ui/Modal.tsx` is the only file emitting
`modal__*` classes in the whole `web/src` tree) — promoting it to `ui.css` now would be
speculative generalization ahead of a second real consumer. `diagrams.css` is scoped to this
feature (mirroring `overview.css`'s own scoping to `OverviewPage`, per spec.md's Constraints), so
adding the modal styling there keeps the change local and easy to find, and it can be promoted to
`ui.css` later if/when a second screen actually needs the same modal shape.

**Alternatives considered**:
- *Promote `Modal.tsx` and its styling to `web/src/ui` now* — rejected as out of scope: this
  feature is about the diagram editor screen specifically; generalizing a component for
  hypothetical future reuse is a separate decision for whoever needs it next.
