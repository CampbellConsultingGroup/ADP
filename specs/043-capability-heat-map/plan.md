# Implementation Plan: Capability Heat Map

**Branch**: `043-capability-heat-map` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/043-capability-heat-map/spec.md`

## Summary

Add a new "Heat Map" tab to the existing Business Architecture screen: every business capability shown in
its L1/L2/L3 hierarchy (flat, matching the existing capability tree exactly — FR-002, resolved via
clarification), each cell shaded by a user-selectable metric (maturity level, default, or strategic
relevance). Ground-truth research below found this needs **zero backend changes** — the existing
`GET /api/v1/business/capabilities` endpoint already returns every field the heat map needs. This is a
frontend-only feature, built directly on top of the swatch/dimension-selector pattern this session just
established in `web/src/insights/ApplicationsHeatMap.tsx` (919-insights-dashboard).

## Technical Context

**Language/Version**: TypeScript 5.x + React 18 — frontend only, no backend touched at all (confirmed by the
Ground-Truth research below, not assumed).
**Primary Dependencies**: None new. Reuses the existing `useCapabilities()` hook and `BusinessCapability`/
`MaturityLevel`/`StrategicRelevance`/`MATURITY_LEVEL_LABEL`/`STRATEGIC_RELEVANCE_LABEL` exports
(`web/src/api/business.ts`), the already-exported `buildTree()` tree-construction function
(`web/src/business/CapabilityTree.tsx`), and the swatch-palette/dimension-selector pattern from
`web/src/insights/ApplicationsHeatMap.tsx` (919-insights-dashboard, this session) as the direct structural
precedent.
**Storage**: N/A — no new persisted data, no migration. Reads the existing `business_capabilities` table
(ADP-SPEC-033/034/035) via the already-existing, already-unpaginated `GET /api/v1/business/capabilities`
endpoint.
**Testing**: Vitest + Testing Library — a new component test mirroring `ApplicationsHeatMap.test.tsx`'s
mocked-hook (`vi.mock("../api/business")`) convention.
**Target Platform**: Existing ADP web app.
**Project Type**: Web application — frontend-only change.
**Performance Goals**: SC-002 (switch metric in a single action, immediate update) met by construction —
`useCapabilities()` already fetches every capability's full data in one call (the same call
`CapabilityTree`/`CapabilityNode` already make), so switching the color-coding metric is a pure client-side
recolor with zero additional fetch, identical in shape to 919's own SC-002 decision.
**Constraints**: FR-011 (remain usable for a deep/wide hierarchy, no silent truncation) — the grid must
scroll rather than truncate, matching `StrategyHeatMap.tsx`'s `overflowX: auto` / `ApplicationsHeatMap.tsx`'s
CSS-grid-with-scroll precedent.
**Scale/Scope**: Demo-scale capability portfolio (`scripts/seed_retail.py` seeds a small, fixed capability
tree, consistent with every other domain's seeded data this session has confirmed) — no pagination or
virtualization concern for v1.

## Ground-Truth Research (done before writing this plan, not assumed)

1. **Zero backend changes needed.** Direct reads of `src/adp/business/router.py`'s `GET /capabilities`
   handler (`list_capabilities`, no query params, no pagination) and `BusinessCapability`
   (`src/adp/business/models.py:70-88`) confirm the existing response already carries `level`, `parent_id`,
   `position`, `domain_id`/`domain_name`, `strategic_relevance`, and `maturity_level` for every capability,
   unfiltered. `web/src/api/business.ts`'s existing `useCapabilities()` hook and `BusinessCapability` TS type
   already mirror this exactly — the same data `CapabilityTree.tsx` already renders. This feature needs no
   new endpoint, no new hook, no new model change anywhere in `src/adp/`.
2. **There is no separate "capability detail view."** Spec.md's User Story 3 / FR-008 describe drilling
   "into that capability's existing detail view" — but a direct read of `web/src/business/BusinessPage.tsx`
   and `CapabilityNode.tsx` confirms capabilities have no master/detail split the way Value Streams and
   Domains do (`BusinessPage.tsx`'s `value-streams`/`domains` tabs both have a `List`/`Detail` pair;
   `capabilities` renders only `<CapabilityTree />`, no detail component). The capability tree's own
   inline-expandable row (`CapabilityNode.tsx` — always expanded by default, carrying edit fields, the
   Links panel, and Agent Review) **is** the closest thing to a "detail view." FR-008 is satisfied, without
   contradicting the spec, by switching to the Capabilities tab and scrolling/highlighting that capability's
   existing row — not by building a new, separate detail screen the rest of the platform doesn't have either.
3. **Every row is already expanded by default.** `CapabilityNode.tsx`'s `expanded` state defaults to `true`
   (`useState(true)`), so a drill-through only needs to scroll a node into view, not also expand its
   ancestors first — simplifying US3's implementation.
4. **Value ranges confirmed**: `maturity_level` is `1 | 2 | 3 | 4 | 5` (`MATURITY_LEVEL_LABEL`: Ad hoc →
   World Class) — a direct 1:1 fit for `ApplicationsHeatMap.tsx`'s existing 5-step `FIVE_STEP` swatch
   palette, reusable as-is. `strategic_relevance` is `1 | 2 | 3` (Strategic/Core/Supporting) — a 3-value
   scale, needing its own 3-step subset of the same palette rather than reuse of the 5-step version
   unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Status | Notes |
|---|---|---|
| ART-I — Spec-Driven Development | PASS | Approved spec (checklist 100% pass after `/speckit-clarify`), this plan follows it. |
| ART-II — Model is Single Source of Truth | PASS | Pure read projection over already-fetched `BusinessCapability` data (spec.md FR-010); no new persisted artifact anywhere. |
| ART-III — Everything Machine-Readable | PASS | Consumes the existing typed `BusinessCapability` API response; no free-text artifact introduced. |
| ART-IV — Test-Driven Development | PASS (planned) | New component test written before implementation in `/speckit-tasks`/`/speckit-implement`. |
| ART-V — Security by Design | PASS | Spec.md's threat model: read-only, already-open data, no new boundary. |
| ART-VI — Observability | N/A | No new backend code path, no AI step. |
| ART-VII — Grounded AI Only | N/A | No AI-generated content. |
| ART-XIII — Typed Contracts Everywhere | PASS | Consumes the existing typed `BusinessCapability`/`BusinessCapabilityListResponse` contract unchanged — no new contract to define. |

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/043-capability-heat-map/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
└── tasks.md              # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

No `contracts/` directory — there is no new or changed API contract (Ground-Truth Research #1).

### Source Code (repository root)

```text
web/src/business/
├── CapabilityHeatMap.tsx        # NEW — the grid + metric selector
├── CapabilityHeatMap.test.tsx   # NEW
├── CapabilityTree.tsx           # + export buildTree() already exported; + focusCapabilityId prop
├── CapabilityNode.tsx           # + id attribute per row + scroll-into-view-on-focus effect
├── BusinessPage.tsx             # + "Heat Map" tab (mirrors StrategyPage.tsx's tab pattern)
└── classification.ts            # reused as-is (LEVEL_STYLE, unrelated to metric swatches)
```

**Structure Decision**: Entirely frontend, entirely inside the existing `web/src/business/` folder — no new
package, no new top-level directory, no backend file touched at all. This is the smallest-footprint feature
of the session so far: one new component + one new test + three small, additive edits to already-existing
files.

## Complexity Tracking

*No violations — table intentionally empty.*
