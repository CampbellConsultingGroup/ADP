# Phase 1 "Data Model": Diagram Editor Visual & Workspace Redesign

No database entity, migration, or API type is added or changed by this feature (spec.md FR-016) —
it is presentation-only. What follows is the equivalent surface for a frontend-only visual
feature: the token/class contract the redesign must satisfy, and the one typed extension
(`IconName`) that does change.

## Reused tokens (no new custom properties — research.md Decision 3)

| Token | Role in this feature |
|---|---|
| `--surface-2`, `--surface-3` | Canvas background; palette-rail/DSL-panel background where distinct from `--surface` |
| `--border`, `--border-strong` | Canvas boundary; grid-dot pattern color; panel/modal borders |
| `--ink`, `--ink-2`, `--ink-3` | Text at each hierarchy level across restyled controls |
| `--accent`, `--accent-2`, `--accent-wash` | Selection stroke, active-state (Connect mode, focus rings), primary buttons |
| `--crit`, `--crit-wash` | Error/alert styling (parse errors, delete-danger button) |
| `--good`, `--warn` | Save-state indicator (FR-003): saved / error states |
| `--radius`, `--radius-sm`, `--radius-lg` | Panel, button, modal corner radii |
| `--space-1`…`--space-6` | All new spacing in `diagrams.css` |
| `--mono` | DSL panel text |
| `--shadow-sm`, `--shadow-md` | Panel/modal elevation |

## `IconName` extension (`web/src/diagrams/editor/ui/Icon.tsx`)

Ten new entries added to the existing `IconName` union and `PATHS` record (FR-004) — `diamond`
already exists and is reused as-is for the diamond shape button:

| New `IconName` | Maps to `NodeShape` |
|---|---|
| `shape-rectangle` | `rectangle` |
| `shape-rounded` | `rounded-rectangle` |
| `shape-circle` | `circle` |
| `shape-stadium` | `stadium` |
| `shape-subroutine` | `subroutine` |
| `shape-double-circle` | `double-circle` |
| `shape-hexagon` | `hexagon` |
| `shape-parallelogram` | `parallelogram` |
| `shape-trapezoid` | `trapezoid` |
| `shape-asymmetric` | `asymmetric` |

Each is a simple geometric outline on the same 16×16 stroke grid every existing icon in this file
uses (`stroke="currentColor"`, `strokeWidth={1.5}`) — no new visual language, just literal outline
renderings of the shapes they represent.

## CSS class contract (research.md Decision 1)

The full, verified set of class names the six vendored files already emit, which `diagrams.css`
must define. See `contracts/diagram-css-contract.md` for the exhaustive per-file breakdown; summary:

| Class family | Emitted by |
|---|---|
| `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--tertiary`, `.btn--danger`, `.btn--compact` | `Canvas.tsx`, `DslPanel.tsx`, `ConfirmDialog.tsx` |
| `.canvas-root`, `.canvas-svg`, `.canvas-edit-affordance` | `Canvas.tsx` |
| `.card`, `.cluster` | `Canvas.tsx` |
| `.field__label` | `Canvas.tsx` |
| `.rail-section`, `.rail-section__label`, `.section-label` | `Canvas.tsx` |
| `.shape-grid`, `.tool-list` | `Canvas.tsx` |
| `.panel`, `.panel__body`, `.panel__body--flush`, `.panel__footer` | `DslPanel.tsx` |
| `.dsl-panel`, `.dsl-panel__editor` | `DslPanel.tsx` |
| `.modal`, `.modal--wide`, `.modal__header`, `.modal__title`, `.modal__body`, `.modal__footer` | `web/src/diagrams/editor/ui/Modal.tsx` (ADP-authored, not vendored) |

## Component state additions (no new external type)

- **`DiagramEditorPage.tsx`**: one new local state value for the persistent save-state indicator
  (FR-003) — an enum-shaped value (`idle | saving | saved | error`), not persisted, not sent to
  any API; purely local UI state derived from the existing `saving`/`error` state already present
  plus one new "was successfully saved at least once" flag.
- **Workspace layout collapse (FR-012)**: one new local boolean in `DiagramEditorPage.tsx` (or a
  small layout wrapper it renders) tracking whether the palette rail is expanded or collapsed on
  narrow viewports — not persisted across sessions, resets on reload (matching how ADP's own nav
  rail collapse is purely CSS-driven with no persisted user preference either).
