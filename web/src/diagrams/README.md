# Diagram types beyond C4 (ADP-SPEC-046)

This module is additive to, and completely independent from, `web/src/canvas/`
(the existing C4 workspace — untouched by this feature).

## `core/` — vendored, low-diff mirror of a sibling project

`core/` is a near-verbatim copy of `/home/jmuir/projects/canvas/packages/diagram-core/src/`
(only relative import paths were adjusted). It is **not** meant to diverge
stylistically from its upstream source — see
[specs/046-diagram-type-support/research.md](../../../specs/046-diagram-type-support/research.md)
Decision 1 and Decision 6 for why vendoring (a one-time copy) was chosen over a
live cross-repo dependency, and why the whole `src/` tree was copied unmodified
(including the unused `c4` DSL family) rather than surgically stripped.

**Do not hand-edit files under `core/` without a documented reason** — if the
upstream library gains a fix or feature ADP needs, re-copy the relevant files
from the sibling project and re-run the tests in `core/**/*.test.ts` (many of
which are themselves translated from the sibling project's own existing test
suite) rather than patching the vendored copy in place, so a future re-sync
stays a clean diff.

## `editor/` — vendored + adapted from the sibling project's React editor

Vendored from `canvas/apps/web/src/canvas/`: `Canvas.tsx`, `shapes.tsx`,
`DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`,
`UnsupportedElementNotice.tsx` — all confirmed backend-agnostic (their props
don't assume the sibling project's own Fastify backend exists).

**Deliberately excluded**:
- `ViolationsPanel.tsx` — surfaces the sibling project's own admin-defined
  Standards system, out of scope for v1 (spec.md FR-009, deferred by design,
  not an oversight).
- `ExportMenu.tsx`'s backend-coupled PNG export call — that component posts
  to the sibling project's own `resvg-js`-backed endpoint, which doesn't
  exist in ADP. Rebuilt from scratch as `ExportAction.tsx`, targeting ADP's
  own `cairosvg`-backed export endpoint instead (research.md Decision 3).

## `DiagramEditorPage.tsx`, `DiagramListPage.tsx`, `api.ts`

ADP-authored, not vendored — the integration surface between the vendored
`core`/`editor` pieces and ADP's own backend (`src/adp/diagrams/`).
