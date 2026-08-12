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

## `DiagramEditorPage.tsx`, `DiagramListPage.tsx`, `DiagramsPage.tsx`, `api.ts`

ADP-authored, not vendored — the integration surface between the vendored
`core`/`editor` pieces and ADP's own backend (`src/adp/diagrams/`).
`DiagramsPage.tsx` (ADP-914.5) owns list↔editor navigation state and is what's
wired into `App.tsx`'s "Diagrams" nav entry — neither sub-page is imported
from `App.tsx` directly.

## `persona.ts` — persona-aware default diagram type (ADP-914.6)

A small, static `PERSONA_DEFAULT_TYPE` constant (mirroring the
`ROLE_LABELS`/`ROLE_COLORS` pattern in `web/src/auth/AuthProvider.tsx`)
mapping each architect role to the diagram type `DiagramEditorPage.tsx`
pre-selects when starting a brand-new diagram, and visually flags as
"(Recommended for your role)" in the type selector. **Steering only** — every
role can still pick any of the 5 types; this never restricts `WRITE_DIAGRAM`.
Roles with no entry (`reviewer`, `platform_admin`, unrecognized/undefined)
fall back to today's pre-feature default (`flowchart`), no badge shown.

Changing a role's default is a one-line edit to the constant in `persona.ts`
— it is a deliberately judgment-call mapping (no in-codebase usage data
existed yet when it was chosen; see
[specs/047-persona-diagram-experience/research.md](../../../specs/047-persona-diagram-experience/research.md)
Decision 2), expected to be revisited once real usage patterns emerge.

## `generators.ts` — generate a diagram from ADP's own business data (ADP-914.7)

Two pure functions, `generateFromValueStream(vs)` and
`generateFromCapabilitySubtree(node)`, each `(source data) -> DiagramSeed`
(`{ title, diagramType, model }`). Both build a typed `DiagramModel` via the
vendored `core`'s `addNode`/`addEdge` — **never hand-write DSL text** (the
existing `useDslSync` machinery in `DiagramEditorPage.tsx` derives the DSL
panel from the model automatically, exactly as it does for a user's own
manual edits).

`addNode` assigns each node's id internally — a generator cannot pre-assign
one from the source entity's own id, so `generateFromValueStream` builds a
`stage.id → generated node id` map while creating nodes, then resolves edges
through it. `generateFromCapabilitySubtree` needs no such map: its top-down
recursive walk always has the parent's just-created id on hand via closure,
since a parent node is created before its children (see
[specs/048-generate-diagrams-from-data/research.md](../../../specs/048-generate-diagrams-from-data/research.md)
Decision 2 for the full reasoning, including why this was *not* obvious from
the vendored `diagram-ops.ts` API alone).

**One-way only, by design (FR-008)** — a generated diagram, once saved, is
stored identically to a hand-authored one; no provenance link back to its
source value stream/capability is kept, and there is no re-sync. "Generate
Diagram" always produces a brand-new, unsaved diagram — clicking it again is
just starting over.

**Cross-page hand-off**: "Generate Diagram" lives on the source entity's own
page (`ValueStreamDetail.tsx`, `CapabilityNode.tsx`, inside the Business
Architecture screen), which calls the generator directly and hands the
resulting `DiagramSeed` up through an `onGenerateDiagram` callback. `App.tsx`
lifts that into a `pendingDiagramSeed` state and switches `view` to
`"diagrams"` in one action — deliberately mirroring the **existing**
`currentDesignId`/`onSelectDesign` pattern already there (research.md
Decision 3), not a new state-sharing mechanism. `DiagramsPage.tsx` consumes
the seed on receipt (opens the editor pre-filled) and reports it consumed so
`App.tsx` can clear it.

## AI-assisted diagram editing (ADP-914.8)

`DiagramEditorPage.tsx` embeds `adp.chat`'s existing `ChatButton`/`ChatPanel`
(the same components already used on the Capabilities page) — the first AI-
*generative* capability in this diagram feature line (046/914.6/914.7 all had
zero AI-generated content). Three new `ChatPanel` props, added incrementally:

- **`getDiagramContext`** — a getter (called fresh at send time, never a
  captured value) returning the diagram's current title/type/DSL, threaded to
  `adp.chat`'s backend as an optional `diagram_context` request field,
  appended to that turn's system prompt. **Deliberately not a new
  `adp.chat.tools.TOOL_REGISTRY` entry** — a tool the model calls needs an id
  to call it *with*, but an ADP-914.7-generated, not-yet-saved diagram has
  none. `adp.chat`'s mechanically-enforced read-only tool boundary
  (`tests/unit/chat/test_tools_boundary.py`) needed zero changes for this
  feature.
- **`onAssistantReply`** — fires with the completed response text.
  `DiagramEditorPage.tsx` runs it through `extractProposedDsl()` (a fenced
  DSL code block, per the system prompt's instructions) and, when found,
  calls the *existing* `applyDsl()` — the same mechanism already used when
  reopening a saved diagram. Nothing is ever auto-saved; the existing Save
  button remains the only persistence gate (no new accept/reject UI).
- **`onStreamingChange`** — fires on every `isStreaming` transition;
  `DiagramEditorPage.tsx` uses it to disable `DslPanel` (a new `disabled`
  prop) and visually lock `Canvas` (a non-invasive wrapper, not a prop
  threaded into that large vendored+adapted component) for the duration of a
  request — eliminating the race between a manual edit and an incoming
  proposal (Clarifications, FR-011), mirroring this file's own pre-existing
  `disabled={saving}` convention on the Save button.

See [specs/049-ai-diagram-editing/research.md](../../../specs/049-ai-diagram-editing/research.md)
for the full reasoning, including two designs considered and rejected (a
`get_diagram` tool; a JSON/diff-shaped proposal instead of a fenced DSL
block).
