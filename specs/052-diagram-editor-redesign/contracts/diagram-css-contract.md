# Contract: CSS classes the vendored diagram-editor files already expect

Not an API contract (this feature has none — FR-016) — this is the equivalent interface boundary
for a presentation-only feature: the exact set of `className` values the six vendored files
(`web/src/diagrams/README.md`'s own list) already emit in their JSX today, unchanged by this
feature (research.md Decision 1). `diagrams.css` must define every one of these, styled with
ADP's tokens. This list was produced by grepping every `className=` occurrence in each file
directly — not reconstructed from memory — so it is exhaustive as of this feature's planning.

## `Canvas.tsx`

| Class | Where / what it wraps |
|---|---|
| `.canvas-root` | The outer keyboard-focusable container (`tabIndex={0}`, `onKeyDown={handleKeyDown}`) around the whole SVG canvas — line 827. |
| `.canvas-svg` | The `<svg>` element itself — line 841. |
| `.canvas-edit-affordance` | The hover/selection-revealed inline label-edit control on a node — lines 539, 561. |
| `.card.cluster` (two classes, one element) | The floating style-editing popover shown when a shape's color/style controls are open — line 591. |
| `.rail-section` | Wraps each of the two toolbar groups, "Shapes" and "Tools" — lines 705, 724. |
| `.section-label.rail-section__label` (two classes) | The heading text ("Shapes" / "Tools") atop each rail section — line 706, 725. |
| `.shape-grid` | The grid of shape-picker buttons inside the "Shapes" rail section — line 707. |
| `.tool-list` | The list of tool buttons (Connect, Add Container, etc.) inside the "Tools" rail section — line 726. |
| `.field__label` | Labels for the two inline `<select>` controls (connect arrow-style, Auto Layout direction) — lines 744, 794. |
| `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--tertiary`, `.btn--compact` | Every button in the toolbar and the style popover — shape buttons use `.btn.btn--secondary`; the style popover's Clear/Done use `.btn.btn--tertiary.btn--compact` / `.btn.btn--primary.btn--compact`. |

## `DslPanel.tsx`

| Class | Where / what it wraps |
|---|---|
| `.panel` | The outer DSL panel container. |
| `.panel__body`, `.panel__body--flush` | The body region holding the text editor (flush = no inner padding, since the textarea fills it). |
| `.dsl-panel` | Applied alongside `.panel__body--flush` — DSL-panel-specific sizing/layout on top of the generic panel body. |
| `.dsl-panel__editor` | The `<textarea>` itself. |
| `.panel__footer` | The footer row holding the Apply button. |
| `.btn.btn--primary.btn--compact` | The Apply button. |

## `ConfirmDialog.tsx`

| Class | Where / what it wraps |
|---|---|
| `.btn.btn--secondary` | The Cancel action. |
| `.btn.btn--danger` | The confirming (destructive) action. |

(`ConfirmDialog.tsx` renders inside `Modal.tsx` — see below for the dialog chrome itself.)

## `web/src/diagrams/editor/ui/Modal.tsx` (ADP-authored, not vendored — included because its classes are otherwise undefined today)

| Class | Where / what it wraps |
|---|---|
| `.modal` | The native `<dialog>` element itself. |
| `.modal--wide` | Modifier, applied when `wide` prop is set (content-heavy dialogs — none currently use this in the diagram editor, but the prop exists). |
| `.modal__header`, `.modal__title` | The heading region (omittable via `title={null}`). |
| `.modal__body` | Always-present content region. |
| `.modal__footer` | Present only when a `footer` prop is passed (e.g. `ConfirmDialog`'s Cancel/Confirm buttons). |

## `UnsupportedElementNotice.tsx`, `useDslSync.ts`

No `className` usage found by the same grep — `useDslSync.ts` is a hook (no JSX), and
`UnsupportedElementNotice.tsx`'s error text currently uses an inline `style={{ color: '#b00020' }}`
rather than a class name (spec.md Constraints: replace with `.ui-alert`-consistent styling — this
one *can* reuse `web/src/ui/ui.css`'s existing `.ui-alert` classes directly rather than needing a
`diagrams.css` entry, since it's ADP-authored, not vendored).

## Verification

`grep -roP 'className=\{?[\`"][^\`"]*[\`"]' web/src/diagrams/editor/*.tsx web/src/diagrams/editor/ui/*.tsx`
re-run against the final state of these files at implementation time must produce no class name
absent from this document (for the six vendored files — their markup must not change at all) and
no `diagrams.css` selector left unused.
