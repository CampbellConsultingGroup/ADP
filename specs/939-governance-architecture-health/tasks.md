---
description: "Task list for 939-governance-architecture-health"
---

# Tasks: Governance Architecture Health

**Input**: spec.md, plan.md in `/specs/939-governance-architecture-health/`
**Tests**: mandatory (ART-IV), written first and failing before the code.

## Phase 1: Setup

- [X] T001 Run GitNexus impact on `GovernancePage`, `PatternsPage` and `AdoptionsList` (`node .gitnexus/run.cjs impact <symbol> --direction upstream --repo .`), and record callers and risk in Notes.

## Phase 2: Foundational

- [X] T002 [P] Write web/src/governance/architectureHealth.test.ts:
  - `adoptionsNeedingAttention` orders by status (non-conformant, indeterminate, conformant with warnings) and then by name, counts conformant and not applicable separately, and ignores null status;
  - `exposedCapabilities` keeps only L3s whose exposure is past end of life or retiring, past end of life first, then by name;
  - `gapCount` totals the three gap lists;
  - all of them accept `undefined` data.
- [X] T003 Implement web/src/governance/architectureHealth.ts (plan R1). T002 should now pass.
- [X] T004 Make it possible to open an adoption from another screen (plan R3):
  - `AdoptionsList` takes an `initialSelected` prop;
  - `PatternsPage` takes an `initialAdoptionId` prop, which starts it in the Adoptions section;
  - App.tsx adds a `pendingAdoptionId` state, cleared in `onNavigate`, with a `key` on PatternsPage;
  - App.tsx passes `onOpenAdoption` into GovernancePage.

  Extend web/src/patterns/adoptions.test.tsx with a test that `initialSelected` opens the adoption.

## Phase 3: User Story 1 + 2 — tiles and the Patterns section (P1) 🎯 MVP

- [X] T005 [US1] [US2] Write web/src/governance/ArchitectureHealthTab.test.tsx, with partial mocks of `../api/patterns` and `../api/capAnalysis`:
  - the five tiles show the derived counts;
  - loading shows "…", never 0;
  - all-zero data shows the empty states;
  - the Patterns section lists adoptions in order, with the summary line and the indeterminate note;
  - clicking an adoption calls `onOpenAdoption(id)`;
  - with no adoptions, it shows "no patterns adopted";
  - when the patterns source errors, the Capabilities section still renders.
- [X] T006 [US1] [US2] Implement web/src/governance/ArchitectureHealthTab.tsx (tiles and the Patterns section), and add the tab to web/src/governance/GovernancePage.tsx (FR-001) with the `onOpenAdoption` prop. T005 should now pass.

## Phase 4: User Story 3 — the Capabilities section (P2)

- [X] T007 [US3] Extend ArchitectureHealthTab.test.tsx:
  - exposed capabilities are listed past end of life first, with path and band, and navigate through `CapabilityNavContext`;
  - Overlaps and Gaps render through `CapFindingsViews`;
  - when the capability source errors, the Patterns section still renders.
- [X] T008 [US3] Implement the Capabilities section in ArchitectureHealthTab.tsx, reusing `CapFindingsViews`, `CapWithPath` and `BandChip` (plan R2). T007 should now pass.

## Phase 5: Polish

- [X] T009 Run `npx tsc --noEmit` and `npx vitest run --coverage`. Coverage must stay at or above the ratchet in web/vite.config.ts.
- [X] T010 Check it live with Playwright on the seeded data. Expect:
  - 2 non-conformant adoptions, 1 exposed capability, 1 overlap;
  - the adoption link opens Patterns on that adoption;
  - Process Checkout opens on Business → Capabilities.
- [ ] T011 Add a CLAUDE.md Recent Changes entry, close ADP-loz and ADP-n2t, and refresh GitNexus (`analyze --index-only`). Run `detect-changes`.

## Dependencies

- T002 → T003. T003 and T004 → T005/T006 → T007/T008 → Polish.
- T002 and T004 can run in parallel.

## Notes

- **GitNexus (T001):**
  - `AdoptionsList`: CRITICAL, 116 impacted. Text search finds one caller (PatternsPage), and the change is an optional prop, so existing calls are unaffected.
  - `GovernancePage`, `PatternsPage`: UNKNOWN. Each has one caller, App.tsx.
- **Path for exposed capabilities:** the roll-up carries no parent ids, so the L1 › L2 path comes from `useCapabilities()`, the business list the heat map already loads.
- **Verification (T009, T010):**
  - 728 frontend tests (was 711, +17); tsc clean.
  - Coverage rose to 59.69 / 56.07 / 50.93 / 62.12, above the ratchet.
  - Live with Playwright: tiles 2 / 0 / 1 / 1 / 11, matching the source screens.
  - The mesh-migration adoption opens on Patterns.
  - The Patterns nav afterwards shows the catalog (pending id cleared).
  - Process Checkout opens Business Architecture.
- **T011:** the beads are closed after merge.
