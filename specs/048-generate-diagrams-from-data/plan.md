# Implementation Plan: Generate Diagrams from Business Data

**Branch**: `048-generate-diagrams-from-data` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/048-generate-diagrams-from-data/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Two "Generate Diagram" buttons — one on a value stream's detail view, one on each capability node in the capability tree — that build a typed `DiagramModel` (via the vendored `createEmptyDiagramModel`/`addNode`/`addEdge`, never hand-written DSL text) from already-client-side-cached business data, then hand it to the diagram editor as a one-time "seed" for a brand-new, unsaved diagram. Cross-page handoff (Business page → Diagrams page, with pre-filled content) mirrors the exact existing `currentDesignId`/`onSelectDesign` pattern already in `App.tsx` — no new state-sharing mechanism invented. Pure frontend, zero backend change.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18.3 (frontend only — no backend touched at all)
**Primary Dependencies**: None new. Reuses the vendored `diagram-core`'s `createEmptyDiagramModel`/`addNode`/`addEdge` (`web/src/diagrams/core/model/`), the existing `web/src/api/business.ts` read hooks (`useCapabilities()`, `useValueStream()`), and `DiagramEditorPage.tsx`/`DiagramsPage.tsx` (ADP-SPEC-046, ADP-914.5).
**Storage**: N/A — no new persisted data; generation is a pure, synchronous, in-memory transform of already-fetched React Query cache data into a `DiagramModel`. A generated diagram, once saved, is stored identically to a hand-authored one (spec FR-008).
**Testing**: Vitest + React Testing Library, matching existing conventions. The two generator functions are pure (`(sourceData) => DiagramModel`) and unit-testable with zero DOM/mocking; the new button wiring is tested the same way `DiagramEditorPage.test.tsx`/`DiagramsPage.test.tsx` already are.
**Target Platform**: Browser (existing `web/` SPA) — no new deployable.
**Project Type**: Web application — frontend-only addition to the existing FastAPI backend + React frontend split.
**Performance Goals**: None specific — a synchronous in-memory transform over already-fetched data at the same modest scale ADP-SPEC-046 already assumes (tens to low hundreds of rows).
**Constraints**: Zero backend change (spec Assumptions); zero change to `business_capabilities`/`value_streams` data model or API; generation MUST build a typed `DiagramModel` via `addNode`/`addEdge`, never hand-construct DSL text (spec ART-XIII, and the confirmed fact that `addNode` auto-generates each node's `id` internally — a generator cannot pre-assign IDs, it must build an id-mapping table as it creates nodes, then use that map when creating edges — see research.md Decision 2); cross-page seed handoff MUST reuse the existing `currentDesignId`/`onSelectDesign` lifted-state pattern already in `App.tsx`, not a new mechanism (research.md Decision 3).
**Scale/Scope**: 2 new pure generator functions (1 new file, `web/src/diagrams/generators.ts`, + 1 test file); targeted edits to 6 existing frontend files (`App.tsx`, `BusinessPage.tsx`, `ValueStreamDetail.tsx`, `CapabilityTree.tsx`, `CapabilityNode.tsx`, `DiagramsPage.tsx`) to thread the new callback/seed through, plus `DiagramEditorPage.tsx` to accept an optional seed prop. 0 backend files, 0 new dependencies, 0 migrations.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, zero `NEEDS CLARIFICATION`, clarify pass found no unresolved ambiguity) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | No new obligation | `business_capabilities`/`value_streams` remain ADP's existing sources of truth; generation reads them once, at generation time, and never claims ongoing authority (spec FR-008) — no new canonical model. |
| ART-III (Machine-Readable) | Yes | Closes a real gap: today a user must reconstruct a value stream's or capability tree's structure from memory into hand-typed DSL; generation makes that already-structured data directly expressible as a diagram. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing generator unit tests (pure functions, no DOM) and failing component-wiring tests before each corresponding implementation task. |
| ART-V (Security by Design) | Yes (verified low-risk) | Threat model re-confirmed in spec.md: no new trust boundary, no new backend code path, reuses the already-verified `escapeXml()` label-safety property from ADP-SPEC-046 for generated (not just hand-typed) labels. |
| ART-VI (Observability) | No | No new mutation type — generation is a client-side read+transform; the eventual save goes through the exact same, already-instrumented `POST /api/v1/diagrams` path as any other diagram. |
| ART-VII, ART-VIII, ART-IX, ART-X, ART-XI | No | No AI-generated content (deterministic, rule-based, not an LLM), no AI proposal to confirm, nothing new in the audit trail, no validation gating, no traceability thread beyond what ADP-SPEC-046 already established. |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 theme specifically; generated flowchart diagrams render via the same non-C4 styling system ADP-SPEC-046 already established as out of C4's scope. |
| ART-XIII (Typed Contracts) | Yes | Generation is built entirely on the vendored diagram-core's already-typed `DiagramModel`/`AddNodeInput`/`AddEdgeInput`, never ad-hoc string construction — directly verified via `diagram-ops.ts`, not assumed. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | No | No migration, no schema change, no new dependency. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | A short note in `web/src/diagrams/README.md` on the generator convention, matching ADP-SPEC-046's and ADP-914.6's existing documentation pattern. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — every design decision below (typed-model generation over DSL strings, the App.tsx lifted-state handoff, the `CapabilityNode` prop-type widening) picks the option that reuses an already-established pattern rather than introducing a new one.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md below confirms no persisted entity is introduced; the design stays exactly as additive/reuse-only as the Summary describes.

## Project Structure

### Documentation (this feature)

```text
specs/048-generate-diagrams-from-data/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

No `contracts/` directory — this feature adds no new API endpoint and changes no existing one; generation is a client-side-only transform over already-existing read endpoints.

### Source Code (repository root)

```text
web/src/
├── diagrams/
│   ├── generators.ts               # NEW: generateFromValueStream(vs), generateFromCapabilitySubtree(node)
│   │                                #   -- pure functions, (source data) -> DiagramSeed
│   ├── generators.test.ts          # NEW: unit tests, no DOM
│   ├── DiagramsPage.tsx            # MODIFIED: accepts an optional `seed` prop (from App.tsx);
│   │                                #   on receiving one, opens the editor pre-filled and reports
│   │                                #   it consumed (mirrors currentDesignId/onSelectDesign)
│   └── DiagramEditorPage.tsx       # MODIFIED: new optional `seed?: {title, model}` prop --
│                                    #   when present (and no `diagramId`), initializes `title`/
│                                    #   `model`/`diagramType` from the seed instead of the
│                                    #   persona-aware empty default (ADP-914.6)
├── App.tsx                         # MODIFIED: new `pendingDiagramSeed` state + `onGenerateDiagram`
│                                    #   callback, threaded to BusinessPage, passed to DiagramsPage
│                                    #   -- mirrors the existing currentDesignId/onSelectDesign pattern
└── business/
    ├── BusinessPage.tsx            # MODIFIED: threads the new onGenerateDiagram callback down to
    │                                #   ValueStreamDetail and CapabilityTree (currently declared in
    │                                #   props but unused -- now genuinely wired for the first time)
    ├── ValueStreamDetail.tsx       # MODIFIED: new "Generate Diagram" button in the header action
    │                                #   row, calls generateFromValueStream(vs) then onGenerateDiagram(seed)
    ├── CapabilityTree.tsx          # MODIFIED: threads a per-node onGenerateDiagram callback through
    │                                #   renderTree() to each CapabilityNode
    └── CapabilityNode.tsx          # MODIFIED: `capability` prop type widens from `BusinessCapability`
                                     #   to `CapabilityTreeNode` (a strict superset -- all existing
                                     #   field access still compiles) so the node has its own full
                                     #   subtree available; new per-node "Generate Diagram" button in
                                     #   the existing action-button row (research.md Decision 1)
```

**Structure Decision**: One new file pair (`generators.ts` + its test) holding the two pure generator functions, plus targeted edits to 6 existing files purely to thread a callback/seed through — no new page, no new route, no new top-level module. Every touched file already has a directly analogous existing pattern to extend (per-node action buttons in `CapabilityNode.tsx`, lifted cross-page state in `App.tsx`, an already-declared-but-unused `onNavigate` prop in `BusinessPage.tsx`) rather than a novel one being introduced.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
