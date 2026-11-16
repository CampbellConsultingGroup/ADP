# Implementation Plan: Governance Architecture Health

**Branch**: `939-governance-architecture-health` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/939-governance-architecture-health/spec.md` (beads ADP-loz, ADP-n2t).

## Summary

The Governance screen gets a fourth tab, "Architecture Health". It has five summary tiles, a Patterns section (adoptions that need attention, opening on the Patterns screen) and a Capabilities section:
- exposed business L3s;
- overlaps and gaps, reusing 938's `CapFindingsViews`.

The feature is **frontend only**. It reads three existing hooks: `useAdoptions(true)`, `useCapabilityFindings()` and `useCapabilityRollup()`. There is no backend change, no migration and no new package.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: TanStack Query v5 (existing). **Zero new packages.**
**Storage**: none.
**Testing**: vitest component tests (pure derivation helpers plus the tab), with the hook modules partially mocked. tsc. CI's `frontend-tests` job (ADP-d3y) enforces both.
**Performance Goals**: three cached queries, which the other screens already share. Derivation is linear in adoptions plus business capabilities.
**Constraints**:
- each section loads, fails and shows empty states independently (FR-007);
- no backend change (FR-008);
- coverage must not fall below the ratchet in `web/vite.config.ts`.

**Scale/Scope**: about 2 new components (the tab and a pure `architectureHealth.ts` helper), plus small edits to GovernancePage, PatternsPage, AdoptionsList and App.tsx. Roughly 15 tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, beads ADP-loz/ADP-n2t |
| ART-II | ✔ | Nothing stored; all counts derived from existing derived endpoints |
| ART-IV | ✔ | Helper and component tests written before the code |
| ART-V | ✔ | No new data path; each source keeps its own permission rules |
| ART-XI | ✔ | Every item navigates (FR-006) |

No violations. Post-design re-check: unchanged.

## Design decisions

- **R1 — Pure derivation helper.** `web/src/governance/architectureHealth.ts` exports:
  - `adoptionsNeedingAttention(adoptions)` → `{ attention: Adoption[] (ordered), conformant: number, notApplicable: number }`;
  - `exposedCapabilities(rollup)` → L3 items with a band of past end of life or retiring, ordered by band then name;
  - `gapCount(findings)`.

  It's unit-testable without rendering, and the tiles and sections share it, so their counts can't disagree (SC-002).
- **R2 — Reuse 938's views.** Overlaps and Gaps render through `CapFindingsViews` (modes `overlaps` and `gaps`), so they match Applications → Capabilities exactly (FR-005). Exposed capabilities reuse `CapWithPath` and `BandChip` from `capAnalysisUi.tsx`.
- **R3 — Opening an adoption from another screen (GT-3).** App.tsx gets `pendingAdoptionId`, cleared on normal navigation, like 938's pending ids. It is passed as `PatternsPage initialAdoptionId` (start in the Adoptions section) → `AdoptionsList initialSelected`. GovernancePage takes an `onOpenAdoption` prop from App. A prop is used rather than a context because only one screen opens adoptions.
- **R4 — Tiles never show a misleading 0 while loading** (edge case). A loading tile shows "…", and an errored tile shows "—" with its section's error.

## Project Structure

```text
specs/939-governance-architecture-health/  spec.md plan.md tasks.md checklists/
web/src/governance/architectureHealth.ts           NEW pure helpers
web/src/governance/architectureHealth.test.ts      NEW
web/src/governance/ArchitectureHealthTab.tsx       NEW
web/src/governance/ArchitectureHealthTab.test.tsx  NEW
web/src/governance/GovernancePage.tsx              + tab, onOpenAdoption prop
web/src/patterns/PatternsPage.tsx                  + initialAdoptionId
web/src/patterns/AdoptionsList.tsx                 + initialSelected
web/src/App.tsx                                    + pendingAdoptionId, wiring
```

## Complexity Tracking

None.
