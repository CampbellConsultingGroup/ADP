# Feature Specification: Mapping Rationale — why an application realizes a capability, and where

**Feature Branch**: `943-mapping-rationale`
**Created**: 2026-11-16
**Status**: Draft
**Bead**: ADP-55k.4 (spec 4 of 4 in epic ADP-55k; depends on 940, merged in PR #147)
**Input**: User description: "943 mapping-rationale (ADP-55k.4)". The epic's description and notes hold the user's source notes and decisions.

## Background and Resolved Decisions

The user's notes (2026-11-15, in ADP-55k) say that several applications supporting one capability is not a problem in itself. It is normal for a capability under migration, for regional variation, and for specialization by channel or segment. **"It is a problem only when the redundancy is unintentional or unmanaged."** The notes propose a reason on each mapping:
- **target**: strategic; keep and invest;
- **tactical**: tolerated; stays for a regional or functional reason;
- **transitional**: being retired or replaced;
- **redundant**: overlap with no justification; a rationalization candidate.

As the notes put it: "Three apps on one capability is fine if one is target, one transitional and one region-specific. It is a problem if all three are in use with no plan." They describe the redundancy view as "capability with >1 app and no target, or >1 'redundant'".

Today, 938's overlap finding flags **every** business L3 capability realized by two or more applications that aren't retired, so intended variation is reported alongside real redundancy.

| # | Decision |
|---|---|
| D7 (epic) | The rationale goes on **937's realization link** (application capability L3 ↔ application), with an **optional geography** (region-level realization). 938's overlap finding should then flag only overlaps that aren't explained. The old application ↔ business capability link (with its fit score) is **unchanged**. |
| N1 | The rationale is **optional**. Every existing realization starts as **unclassified**, and nothing is guessed or back-filled. |
| N2 | The rationale is a fact about a **mapping**, not an application. It's independent of the application-level TIME classification and 7R strategy, which stay as they are. |

Ground-truth checks against the code (main at 407a514, migration head `050`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | `app_capability_realizations` has only `app_capability_id`, `app_id` and `created_at`, with a composite primary key on the pair (`src/adp/application/store.py:238`) | The rationale and geography are new attributes on the link. Existing rows read as unclassified, with no geography |
| GT-2 | Realizations are added and removed only on the application capability: `POST /api/v1/application-capabilities/{ac_id}/applications` and `DELETE .../applications/{app_id}` (`app_capabilities_router.py:303`), edited in Applications → Capabilities (`web/src/application/AppCapDetail.tsx`). Writes use the `WRITE_APPLICATION` prefix rule | The rationale and geography are set in the same place, with no new permission |
| GT-3 | 938's `findings()` (`src/adp/application/cap_analysis.py:495`) reports an overlap for every business L3 reached by two or more non-retired applications through application capabilities. It is shown on Applications → Capabilities → Overlaps (`CapFindingsViews.tsx`) and counted by 939's Architecture Health "overlaps" tile | Overlaps are split into **needs attention** and **explained**. The Architecture Health tile counts only the first |
| GT-4 | Applications already carry `time_classification` (Tolerate / Invest / Migrate / Eliminate) and `r_strategy` | They are shown next to each mapping for context, but they don't drive or constrain the rationale (N2) |
| GT-5 | The geography tree from 940 is Global → region → country. 942 decides whether two geographies overlap by containment in both directions | A realization's optional geography is a region or country (Global means no geography). "Same scope" uses 942's containment rule |
| GT-6 | The application export writes `realized_by_application_ids` on each application capability file (`src/adp/export/application_arch.py:196`) | The export adds each realization's rationale and geography, and keeps the existing id list for current readers |

## Clarifications

### Session 2026-11-16

- Q: Can an application realize the same application capability with a different reason in different regions? → A: No. One reason and one optional geography per realization.
- Q: Is "no target" judged across the whole overlap or per region? → A: Across the whole overlap. Any target anywhere counts.
- Q: How does the application's TIME classification relate to the mapping reason? → A: It is shown for context, with a non-blocking hint when the two disagree (FR-013).
- Q: Where does the Redundant list live? → A: In a fourth tab on Applications → Capabilities, beside Overlaps, Gaps and Shared.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: the rationale lives once, on the realization. Overlap status is derived on read and never stored.
- **ART-V** — Security by Design: writes use the existing `WRITE_APPLICATION` gate. The rationale and geography are not sensitive.
- **ART-IX** — Auditability: every change to a realization's rationale or geography is logged with the actor, the old value and the new value.
- **ART-XIII** — Typed Contracts: the rationale is a closed set of four values plus "unclassified".
- **ART-XV** — Schema Evolution: one reversible migration (`051`) that adds columns only.
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. The rationale and geography are ordinary architecture classification data, readable by every platform user, like the realization links they describe. Writes need `WRITE_APPLICATION`. They expose no cost, risk or governance data, so the sensitive-category gates don't apply.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Classify why an application realizes a capability (Priority: P1)

An application architect opens the application capability "Promotion Evaluation". It is realized by Store POS and by Commerce Cloud. They mark Store POS as **target** and Commerce Cloud as **tactical**, scoped to the Americas, because online promotions there still run on the e-commerce platform.

**Why this priority**: the rationale is the data every later view depends on. Without it, nothing distinguishes intended variation from redundancy.

**Independent Test**: set, change and clear the rationale and geography on realizations; confirm that existing realizations read as unclassified and that adding a realization works with or without a rationale.

**Acceptance Scenarios**:

1. **Given** an existing realization with no rationale, **When** an architect sets it to target, **Then** it is saved and shown as target on the application capability and on the application.
2. **Given** a realization, **When** the architect sets the geography to the Americas, **Then** it shows as realized in the Americas only. Clearing the geography makes it apply everywhere again.
3. **Given** a realization, **When** the architect clears the rationale, **Then** it returns to unclassified.
4. **Given** a new realization being added, **When** the architect picks a rationale and geography at the same time, **Then** both are saved with the link. Adding a realization without them still works.
5. **Given** a geography of Global, **When** the architect tries to save it, **Then** it is refused, with a message saying that no geography already means everywhere.
6. **Given** a reviewer, **When** they try to change a rationale, **Then** they are refused.

---

### User Story 2 — Overlaps flag only what isn't explained (Priority: P1)

An enterprise architect opens Applications → Capabilities → Overlaps. "Apply Promotions" used to be listed simply as an overlap. Now that one application is target and the other tactical for the Americas, it appears under **Explained**. "Process Payroll", realized by three applications with no rationale recorded, is listed under **Needs attention** with the reason "2 mappings unclassified".

**Why this priority**: this is the outcome the user asked for: intended variation stops being reported as a problem, so the overlap list becomes a real rationalization worklist.

**Independent Test**: build business L3s whose applications have each combination of rationales and geographies, and check which section each lands in and the reasons given.

**Acceptance Scenarios**:

1. **Given** a business L3 realized by two or more non-retired applications, **When** any of those mappings is unclassified, **Then** the overlap needs attention, with the reason "unclassified" and the count.
2. **Given** such an overlap, **When** any mapping is redundant, **Then** it needs attention, with the reason "redundant" naming those applications.
3. **Given** such an overlap where every mapping is classified and none is redundant, **When** none of them is target, **Then** it needs attention, with the reason "no target".
4. **Given** such an overlap, **When** two or more target mappings apply in the same scope (both everywhere, the same geography, or one geography inside the other), **Then** it needs attention, with the reason "competing targets".
5. **Given** an overlap with one target, one transitional and one tactical application scoped to Brazil, **Then** it is listed under Explained, and each application is shown with its rationale and geography.
6. **Given** two target applications scoped to Europe and the Americas respectively, with no other mappings, **Then** the overlap is explained (regional targets).
7. **Given** the Governance → Architecture Health screen, **Then** its overlaps tile counts only the overlaps that need attention, and the screen shows how many are explained.
8. **Given** an overlap that needs attention for several reasons, **Then** every reason is listed.

---

### User Story 3 — Redundancy view (Priority: P2)

An enterprise architect wants the rationalization candidates in one place. They open a **Redundant** view, which lists every mapping marked redundant, grouped by business L3. Each entry shows the application, the application capability it realizes, its geography, and the application's TIME classification and 7R strategy. An application marked Invest whose mapping is marked redundant shows a "check: TIME says Invest" hint.

**Why this priority**: useful once rationales exist (US1). The overlaps list from US2 already covers the urgent cases.

**Independent Test**: mark mappings redundant across several capabilities; confirm the view lists exactly those, grouped and with context, and shows the hint only where TIME and the rationale disagree.

**Acceptance Scenarios**:

1. **Given** three mappings marked redundant, on two business L3s, **Then** the view lists the three under those two capabilities.
2. **Given** a redundant mapping whose application has TIME Invest, **Then** the entry shows a hint that the two disagree. It is never blocked or changed.
3. **Given** a target mapping whose application has TIME Eliminate, **Then** the application capability's realization list shows the same hint.
4. **Given** no redundant mappings, **Then** the view says so.
5. **Given** an entry, **When** the architect follows it, **Then** they land on the application capability with that realization in view, where they can change it.

---

### User Story 4 — Export, seed and search (Priority: P3)

AI tools and offline consumers reading the exported files see each realization's rationale and geography. The demo data shows both outcomes: an explained overlap and one that needs attention.

**Why this priority**: keeps the exported files in step with the API, and makes the feature visible in the demo. Not needed to use it.

**Independent Test**: export, then read an application capability file; reseed in a scratch environment, then open Overlaps.

**Acceptance Scenarios**:

1. **Given** an exported application capability, **Then** its file lists each realization with its application, rationale and geography, and still includes the existing list of application ids.
2. **Given** the seeded demo, **Then** Overlaps shows at least one explained overlap and one that needs attention, and the Redundant view has at least one entry.

### Edge Cases

- **An application reaches one business L3 through two application capabilities with different rationales.** Each mapping is listed separately. The rules apply to mappings, so an unclassified or redundant one still flags the overlap.
- **Retired applications.** They are excluded from overlaps (as in 938), whatever their rationale. A retired application marked target doesn't make an overlap explained.
- **A mapping's geography is deleted.** The mapping keeps its rationale and falls back to "everywhere". The scope rules are then re-derived on the next read.
- **A transitional mapping with no replacement in place.** It is still explained if a target exists. Planning the replacement belongs to roadmaps and initiatives, not this feature.
- **A single application realizing a business L3.** It isn't an overlap, so it's never listed, even if marked redundant. It still appears in the Redundant view (US3), because redundant was chosen deliberately.
- **Removing a realization** removes its rationale and geography with it.
- **The application ↔ business capability fit-score link** is untouched and plays no part in these rules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each application capability realization MUST carry an optional **rationale**: `target`, `tactical`, `transitional` or `redundant`. No value means **unclassified**.
- **FR-002**: Each realization MUST carry an optional **geography**: a region or a country from the geography tree. No geography means everywhere. Global MUST be refused.
- **FR-003**: Existing realizations MUST read as unclassified, with no geography. Nothing is inferred or back-filled.
- **FR-004**: Writers MUST be able to set, change and clear the rationale and geography of an existing realization, and to set both when adding one. Adding a realization without them MUST keep working.
- **FR-005**: Rationale and geography writes MUST require the existing application write permission (`WRITE_APPLICATION`). A reviewer MUST be refused.
- **FR-006**: Every rationale or geography change MUST be logged with the actor, the old value and the new value.
- **FR-007**: An overlap (a business L3 realized by two or more non-retired applications, as in 938) MUST be classified on read as **needs attention** when any of these holds, and as **explained** otherwise:
  - (a) a mapping is unclassified;
  - (b) a mapping is redundant;
  - (c) no mapping is target;
  - (d) two or more target mappings share a scope, meaning both apply everywhere, they name the same geography, or one geography contains the other.
- **FR-008**: Each overlap that needs attention MUST list every reason that applies, with the applications concerned. "No target" is listed only when no mapping is unclassified, because an unclassified mapping may yet be the target. The status is the same either way.
- **FR-009**: The overlap list MUST show each application's rationale and geography, and keep the two sections apart, with needs attention first.
- **FR-010**: The overlap classification MUST be derived on read and never stored.
- **FR-011**: The Governance Architecture Health overlaps tile MUST count only overlaps that need attention, and the screen MUST show the number explained.
- **FR-012**: A **Redundant** tab on Applications → Capabilities (beside Overlaps, Gaps and Shared) MUST list every mapping marked redundant on a non-retired application, grouped by the business L3s it reaches. Each entry MUST show the application, the application capability, the geography, and the application's TIME classification and 7R strategy. A mapping that reaches no business L3 MUST be listed in its own group.
- **FR-013**: A non-blocking consistency hint MUST appear where the rationale and the application's TIME classification disagree:
  - a target mapping on an application marked Eliminate or Migrate;
  - a redundant mapping on an application marked Invest.

  The hint never prevents saving and never changes either value.
- **FR-014**: Realizations MUST show their rationale and geography wherever they are listed: on the application capability, and in the application's own capability list.
- **FR-015**: The export MUST add each realization's application, rationale and geography to the application capability file, and keep the existing application-id list.
- **FR-016**: The demo seed MUST include at least one explained overlap, one overlap that needs attention, and one redundant mapping.
- **FR-017**: The application ↔ business capability fit-score link MUST NOT change.

### Key Entities

- **Application Capability Realization** (existing, extended): an application realizing an application capability (L3). It gains an optional **rationale** and an optional **geography** (region or country).
- **Overlap** (derived, existing, extended): a business L3 realized by two or more non-retired applications. It gains a derived **status** (needs attention or explained) and a list of **reasons**.
- **Redundancy entry** (derived): a realization marked redundant, with the application's context for rationalization.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can classify a realization (rationale and geography) in under 30 seconds, without leaving the application capability.
- **SC-002**: In a portfolio where every overlap has one target and the other mappings are justified, the needs-attention list is empty: no intended variation is flagged.
- **SC-003**: Every overlap with an unclassified or redundant mapping, no target, or competing targets appears under needs attention, with every applicable reason: 100% across the test matrix.
- **SC-004**: The overlaps list, the Redundant view and the Architecture Health tile all agree on their counts after any rationale change, with no refresh beyond reopening the screen.
- **SC-005**: No existing realization, application, capability or fit-score value changes as a result of this feature (checked before and after the migration).

## Assumptions

- **Rationale meanings** follow the user's notes: target = keep and invest; tactical = tolerated for a regional or functional reason; transitional = being retired or replaced; redundant = no justification, a rationalization candidate.
- **One rationale and one optional geography per realization** (confirmed in Clarifications). An application that realizes the same application capability as target in one region and transitional in another isn't modelled in v1. It is rare, and the mapping can be scoped to its main region with the difference explained elsewhere.
- **"No target" is judged across the whole overlap, not per geography** (confirmed). Regional targets in different regions count as targets.
- **TIME and 7R are context only** (N2, confirmed). The rationale is neither derived from them nor validated against them, beyond the advisory hint in FR-013.
- **The overlap rule stays at business L3**, as in 938. Two applications realizing the same application capability with no business link aren't an overlap in this sense.
- **The Redundant view is a tab beside Overlaps, Gaps and Shared** (confirmed) on Applications → Capabilities, not a new screen.
- **941's shared-service candidate finding** (several performers on an L3) is about org units, not applications, so this feature doesn't change it.
- **No change to search.** Realizations aren't indexed separately.
