# Feature Specification: Governance Architecture Health — pattern conformance and capability findings

**Feature Branch**: `939-governance-architecture-health`
**Created**: 2026-11-15
**Status**: Draft
**Beads**: ADP-loz (pattern conformance roll-up, follow-on from 936) and ADP-n2t (capability findings roll-up, follow-on from 938)
**Input**: User description: "ADP-n2t and ADP-loz"

## Background and Resolved Decisions

The Governance screen has three tabs: Design Status, Compliance (design validation exceptions) and Activity Feed. Two recent features compute governance signals that never reach it:
- **Pattern conformance (936)**: each pattern adoption has a status, computed on each request: conformant, conformant with warnings, non-conformant, indeterminate or not applicable.
- **Capability model analysis (938)**: overlaps (a business capability realized by two or more applications), three kinds of gap, and technology exposure (business capabilities that depend on retiring or past-end-of-life technology).

This feature brings both onto the Governance screen.

Decisions confirmed with the user (2026-11-15):

| # | Decision |
|---|---|
| D1 | **One new tab, "Architecture Health"**: summary tiles at the top, then a Patterns section and a Capabilities section listing what needs attention. Each item links to its own screen. |
| D2 | **Governance screen only.** The Overview page's Governance card is unchanged. |

Ground-truth checks against the code (main at 18de010):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | `GET /api/v1/patterns/adoptions?with_status=true` already returns every adoption with its derived status, evaluated for the caller (fields the caller can't read make an adoption indeterminate) (`src/adp/patterns/adoptions_router.py:165-180`). The web hook `useAdoptions(true)` exists (`web/src/api/patterns.ts:442`) | No new backend for patterns |
| GT-2 | `GET .../application-capabilities/analysis/findings` returns overlaps, gaps and shared. `.../business-rollup` returns each business capability's exposure band (938). Both hooks exist (`web/src/api/capAnalysis.ts`) | No new backend for capabilities. Exposed capabilities are the business L3s whose exposure is past end of life or retiring |
| GT-3 | Adoptions open inside the Patterns screen's Adoptions section via local state (`web/src/patterns/AdoptionsList.tsx`). There is no way to open one from another screen | The Patterns screen needs an "open this adoption" entry point, like 937/938's capability navigation |
| GT-4 | Business capabilities, applications and application capabilities already navigate across screens through `CapabilityNavContext` / `AppCapNavContext` (938) | Reused |

## Clarifications

### Session 2026-11-15

- Q: Where do the roll-ups go? → A: One new Governance tab, "Architecture Health" (D1).
- Q: Does the Overview card change? → A: No (D2).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: nothing new is stored. Every count is derived from the existing derived endpoints.
- **ART-V** — Security by Design: no new data or endpoint. Each figure comes from an endpoint that already applies its own permission rules (pattern conformance per caller; cost and risk never used here).
- **ART-XI** — Traceability: every listed item navigates to its own screen.
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. The tab only reads endpoints that already exist and already apply their permission rules. Pattern conformance is evaluated for the caller, so restricted data shows up as "indeterminate", never as a pass or fail. The capability views use no cost or risk fields. No new trust boundary, data or write path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — See what needs attention at a glance (Priority: P1)

A governance lead opens Governance → **Architecture Health**. Five tiles show:
- non-conformant pattern adoptions;
- indeterminate adoptions;
- business capabilities exposed to retiring or past-end-of-life technology;
- overlaps;
- gaps.

With the seeded data, the tiles show 2 non-conformant adoptions (both on E-commerce & Digital: the event backbone and the mesh migration), 1 exposed capability (Process Checkout) and 1 overlap (Apply Promotions).

**Why this priority**: this is the roll-up both beads ask for.

**Independent Test**: open the tab with the seed data and check each tile's count against the Patterns and Applications → Capabilities screens.

**Acceptance Scenarios**:

1. **Given** adoptions with statuses non-conformant, indeterminate and conformant, **When** the tab opens, **Then** the tiles show the non-conformant and indeterminate counts.
2. **Given** business L3s whose exposure is past end of life, retiring and current, **When** the tab opens, **Then** the exposure tile counts the first two, and only Level 3 capabilities.
3. **Given** the findings, **When** the tab opens, **Then** the overlap tile counts overlaps and the gap tile counts all three gap lists.
4. **Given** nothing needs attention, **When** the tab opens, **Then** every tile shows 0 and each section says so.

---

### User Story 2 — Work through pattern conformance (Priority: P1)

Under **Patterns**, the lead sees the adoptions that need attention: non-conformant first, then indeterminate, then conformant with warnings. Each row shows the adoption, pattern, scope and status. A summary line counts the rest (conformant and not applicable). Selecting an adoption opens it on the Patterns screen, with its conformance report.

**Why this priority**: ADP-loz is precisely this list.

**Independent Test**: with the seed, both E-commerce & Digital adoptions are listed as non-conformant, and the Marketing & Loyalty one is summarized as conformant. Selecting it opens that adoption on the Patterns screen.

**Acceptance Scenarios**:

1. **Given** adoptions in every status, **When** the section renders, **Then** it lists non-conformant, then indeterminate, then conformant-with-warnings adoptions, and summarizes the conformant and not-applicable counts.
2. **Given** an indeterminate adoption, **When** it is listed, **Then** a note explains that indeterminate can mean data the viewer can't see, or registry data that's missing.
3. **Given** a listed adoption, **When** it is selected, **Then** the Patterns screen opens on that adoption.
4. **Given** no adoptions at all, **When** the section renders, **Then** it says no patterns have been adopted yet.

---

### User Story 3 — Work through capability findings (Priority: P2)

Under **Capabilities**, the lead sees:
- **Exposed capabilities**: each business L3 exposed to retiring or past-end-of-life technology, with its band and L1 › L2 path, worst first;
- **Overlaps**;
- **Gaps**, as the same three lists as on Applications → Capabilities.

Every item links to its own screen.

**Why this priority**: ADP-n2t. It reuses 938's views, so it costs less than US2.

**Independent Test**: with the seed, Process Checkout is listed as Retiring, and Apply Promotions as an overlap. Selecting each opens it.

**Acceptance Scenarios**:

1. **Given** exposed L3s, **When** the section renders, **Then** past-end-of-life items come before retiring ones, each with its path.
2. **Given** an overlap, **When** it is listed, **Then** it names each application and the application capability it acts through, as on Applications → Capabilities.
3. **Given** any listed item, **When** it is selected, **Then** its own screen opens.

### Edge Cases

- One data source fails to load: its tiles and section show an error, and the other section still renders.
- Data is still loading: each tile shows a placeholder, never a misleading 0.
- An adoption with no status (the list was loaded without statuses) is treated as unknown and not counted. This doesn't happen here, because the tab always asks for statuses.
- A business L2 or L1 is never counted as exposed. Only L3s are, so the count matches the number of capabilities a person would fix.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Governance screen MUST have a fourth tab, "Architecture Health", after the existing three.
- **FR-002**: The tab MUST show five tiles:
  - non-conformant adoptions;
  - indeterminate adoptions;
  - exposed business capabilities (L3s with exposure past end of life or retiring);
  - overlaps;
  - gaps (the total of the three gap lists).
- **FR-003**: The Patterns section MUST list non-conformant, then indeterminate, then conformant-with-warnings adoptions, sorted by name within each status. It MUST summarize the conformant and not-applicable counts.
- **FR-004**: Selecting an adoption MUST open it on the Patterns screen.
- **FR-005**: The Capabilities section MUST list exposed business L3s (past end of life first, then retiring, then by name, each with its path), plus overlaps and gaps presented as on Applications → Capabilities.
- **FR-006**: Every listed business capability, application, application capability and adoption MUST navigate to its own screen.
- **FR-007**: Each section MUST load, fail and show empty states independently.
- **FR-008**: Nothing new is stored and no backend is added. All figures come from the existing derived endpoints (GT-1, GT-2).

### Key Entities

None new. The feature uses existing derived results: adoption status (936), capability findings and exposure (938).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With the seed data, a governance lead can name the non-conformant adoption and the exposed and overlapping business capabilities from one screen, without opening Patterns or Applications.
- **SC-002**: Every tile count equals the corresponding count on its source screen (Patterns adoptions, Applications → Capabilities findings).
- **SC-003**: Every listed item opens its own screen in one click.
- **SC-004**: Every acceptance scenario is covered by an automated test.

## Assumptions

- "Needs attention" for patterns means non-conformant, indeterminate and conformant-with-warnings. Conformant and not applicable are summarized, not listed.
- Exposure counts only retiring and past-end-of-life L3s. Contained is a deliberate holding state, not a problem to flag here.
- Shared application capabilities are informational (938) and are not shown on this governance view.

## Out of Scope (follow-ons)

- Overview card metrics (D2).
- History or trends (ADP-5mc for patterns, ADP-v2l for capabilities).
- Notifications or alerts when a status changes.
