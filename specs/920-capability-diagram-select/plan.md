# Implementation Plan: Multi-Select Capabilities → Generate Diagram

**Branch**: `920-capability-diagram-select` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/920-capability-diagram-select/spec.md`

## Summary

Replace `CapabilityNode.tsx`'s existing per-row single-capability "⛶ Generate Diagram" button with a
checkbox, add selection state (count + clear-all) to `CapabilityTree.tsx`, and add a new
"Generate Diagram from Selected" toolbar action that builds one diagram from the checked set — a new
`generateFromCapabilities()` generator (parallel to the existing `generateFromCapabilitySubtree()`) that
includes a parent-child edge between any two selected capabilities where that relationship exists, and no
other capabilities or relationship types (spec.md's resolved Clarification). Entirely frontend — no backend
change, matching `043-capability-heat-map`'s own recent precedent for a `web/src/business/`-scoped feature.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18 — frontend only, no backend touched at all.
**Primary Dependencies**: None new. Reuses the existing `useCapabilities()` hook, the existing
`createEmptyDiagramModel`/`addNode`/`addEdge` diagram-core primitives (`web/src/diagrams/core/`) that
`generateFromCapabilitySubtree()` already uses, and the existing `onGenerateDiagram`/`pendingDiagramSeed`
integration path (`App.tsx` → `DiagramsPage`) that a generated `DiagramSeed` already flows through today.
**Storage**: N/A — no new persisted data. Selection is transient, component-local UI state (spec.md FR-009),
never written anywhere.
**Testing**: Vitest + Testing Library — new tests for the `generateFromCapabilities()` generator (mirroring
`generators.test.ts`'s existing pure-function convention) and for the new selection/toolbar behavior in
`CapabilityTree.test.tsx`/`CapabilityNode.test.tsx` (new).
**Target Platform**: Existing ADP web app.
**Project Type**: Web application — frontend-only change, entirely inside `web/src/business/` and
`web/src/diagrams/generators.ts`.
**Performance Goals**: SC-001 (generate a multi-branch diagram in under 10 seconds) is met by construction —
generation is a synchronous, in-memory transform of already-fetched `useCapabilities()` data, identical in
shape to the existing single-capability generator's own (already-fast) behavior.
**Constraints**: FR-006 requires the new mechanism to fully replace the old per-row button, not sit
alongside it — removing `generateFromCapabilitySubtree()`'s only call site changes its status from
"actively used" to "kept for behavioral parity, called by the new generator's single-selection path" (see
research.md Decision 2).
**Scale/Scope**: Demo-scale capability portfolio (confirmed repeatedly this session) — no virtualization or
pagination concern for a checkbox-per-row UI or a diagram generated from the full selected set.

## Ground-Truth Research (done before writing this plan, not assumed)

1. **The exact current per-row mechanism, re-confirmed**: `CapabilityNode.tsx`'s "⛶" button calls
   `onGenerateDiagram?.(generateFromCapabilitySubtree(capability))` — the *only* call site of
   `generateFromCapabilitySubtree()` anywhere in the codebase (confirmed via search). Removing this button
   per FR-006 does not orphan that function if the new multi-select generator's single-selection path
   reuses it directly (research.md Decision 2), preserving SC-004's exact-parity requirement without
   duplicating its subtree-walk logic.
2. **`onGenerateDiagram` is already threaded three levels deep**: `CapabilityNode` → `CapabilityTree` (via
   `renderTree()`'s existing parameter) → `BusinessPage` → `App.tsx`'s `onGenerateDiagram` state setter,
   confirmed by direct re-read of all three files this session already touched for `043-capability-heat-map`.
   The new toolbar action only needs to call the *same* `onGenerateDiagram` prop `CapabilityTree` already
   receives — no new prop threading through `BusinessPage`/`App.tsx` at all.
3. **`CapabilityTree.tsx`'s toolbar (where the new action belongs) lives inside `CapabilityTree.tsx`
   itself**, not `BusinessPage.tsx` — confirmed by re-read: "Show orphans only", the `ChatButton`, "Review
   Portfolio", and "+ Add Strategic Capability" are all rendered in `CapabilityTree`'s own header row. The
   new "Generate Diagram from Selected" button and the selection count/clear-all (US2) follow that same,
   already-established local pattern.
4. **Selection state naturally resets on tab switch with zero extra code.** `BusinessPage.tsx` renders
   `{tab === "capabilities" && <CapabilityTree ... />}` — a conditional render, not a CSS-hidden persistent
   mount. Switching to another tab unmounts `CapabilityTree`, so component-local `useState` selection state
   is discarded automatically on remount — satisfying spec.md's Edge Case/Assumption about selection
   resetting on tab switch without needing `043-capability-heat-map`'s explicit `setFocusCapabilityId(null)`
   pattern (that one exists because `focusCapabilityId` lives in the *parent* `BusinessPage`, which does not
   unmount on tab switch — a different situation).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Status | Notes |
|---|---|---|
| ART-I — Spec-Driven Development | PASS | Approved spec (checklist 100% pass), this plan follows it. |
| ART-II — Model is Single Source of Truth | PASS | Diagram generation is a pure, synchronous transform of already-fetched `BusinessCapability` data at generation time; selection itself is never persisted. |
| ART-III — Everything Machine-Readable | PASS | Consumes the existing typed `BusinessCapability`/`DiagramModel` shapes; introduces no free-text artifact. |
| ART-IV — Test-Driven Development | PASS (planned) | New generator + selection/toolbar tests written before implementation in `/speckit-tasks`/`/speckit-implement`. |
| ART-V — Security by Design | PASS | Threat model in spec.md — no new read, no write path at all. |
| ART-VI — Observability | N/A | No new backend code path, no AI step. |
| ART-VII — Grounded AI Only | N/A | No AI-generated content. |
| ART-XIII — Typed Contracts Everywhere | PASS | New generator returns the existing typed `DiagramSeed`/`DiagramModel` shape unchanged — no new contract to define. |

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/920-capability-diagram-select/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

No `contracts/` directory — no new or changed API contract (this is a pure frontend feature, Ground-Truth
Research confirms no backend involvement anywhere).

### Source Code (repository root)

```text
web/src/diagrams/
├── generators.ts             # + generateFromCapabilities() (new, parallel to existing
│                               generateFromCapabilitySubtree(), which it reuses for the
│                               single-selection case — research.md Decision 2)
└── generators.test.ts        # + tests for generateFromCapabilities()

web/src/business/
├── CapabilityTree.tsx         # + selectedIds state, "Generate Diagram from Selected" toolbar
│                               button, selection count + "Clear selection"
├── CapabilityTree.test.tsx    # + tests for the above
├── CapabilityNode.tsx         # checkbox replaces the "⛶ Generate Diagram" button; + selected/
│                               onToggleSelect props
└── CapabilityNode.test.tsx    # NEW — this component has no existing render-based test file
                                (only ever exercised indirectly via CapabilityTree.test.tsx)
```

**Structure Decision**: Entirely inside `web/src/business/` plus one addition to the already-existing
`web/src/diagrams/generators.ts` — no new package, no new top-level directory, no backend file touched.
Mirrors `043-capability-heat-map`'s own minimal-footprint shape.

## Complexity Tracking

*No violations — table intentionally empty.*
