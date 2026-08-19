# Feature Specification: Compliance Rollup Reporting

**Feature Branch**: `924-compliance-rollup-reporting`
**Created**: 2026-08-19
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md COMPY_04 only"

Source: COMPLY-04 ("Compliance Rollup (Read-Side)") of `docs/speckit-compliance-bundle_1.md`, the
fourth spec in a five-spec Compliance Domain bundle. COMPLY-01 (`RegulatoryFramework`/`Control`
registry), COMPLY-02 (`ControlMapping` traceability links), and COMPLY-03 (derived compliance
status) are already implemented — see `specs/921-compliance-framework-registry/`,
`specs/922-control-mappings/`, `specs/923-derived-compliance-status/`. This spec covers COMPLY-04
only, per explicit user scoping; COMPLY-05 (Strategy linkage) is out of scope here.

**Ground-truth corrections to the source bundle, confirmed by reading the actual codebase before
scoping this spec (not assumed):**

1. **One of the bundle's three "What to build" bullets is already delivered.** "Entity-level
   traceability: given a Capability/Application/Design, list its mapped controls and each one's
   status" is exactly what COMPLY-02 already shipped — `GET /capabilities/{id}/compliance-mappings`,
   `GET /applications/{id}/compliance-mappings`, `GET /designs/{id}/compliance-mappings`, and
   `GET /knowledge/{id}/compliance-mappings` (the Pattern-targeted reverse lookup) all already exist
   and return exactly this shape. This spec does not rebuild it; the remaining two bullets (the
   per-framework coverage rollup and the summary card) are this spec's actual scope.
2. **The bundle's premise for where this belongs doesn't hold.** The bundle says this should be
   "surfaced the same way the Governance & Standards screen already claims... a 'standards
   compliance' rollup" — no such caption exists anywhere in the current Governance screen
   (confirmed by direct search). More importantly, `web/src/governance/ComplianceTab.tsx` is a
   real, already-shipped screen with the word "Compliance" in its name, but it is about something
   entirely different: LLM-as-Judge validation-*exception* findings on designs (FAIL/WARN severity
   per finding), not the regulatory `RegulatoryFramework`/`Control` domain this spec extends. This
   naming collision was already flagged during COMPLY-02's own implementation. Since a dedicated
   "Compliance" top-level screen now exists (`web/src/compliance/CompliancePage.tsx`, shipped in
   COMPLY-01) specifically for this regulatory domain, this spec's rollup views belong there, not on
   Governance's unrelated, same-named tab. This resolves the bundle's first Open Question directly
   from evidence rather than leaving it a "product decision."
3. **The bundle's second Open Question rests on a now-stale assumption.** It says "The Strategy
   domain precedent (no Overview card yet) suggests starting scoped" — but Strategy's own Overview
   dashboard card was subsequently built (`specs/051-strategy-landing-card/`, already shipped,
   `FR-001`: "The Overview dashboard MUST display a fifth domain card for Strategy"). The real
   precedent is the opposite of what the bundle assumed: Strategy *does* have an Overview card. This
   spec follows that real precedent for its own summary card rather than the bundle's outdated
   assumption.
4. **The sensitivity-gating question COMPLY-02 left open is already resolved.** COMPLY-02 shipped
   with Application-targeted `ControlMapping` reads gated by `READ_APPLICATION_GOVERNANCE`
   (Capability/Design/Pattern/organization-scoped mappings are open reads). This spec's rollups
   must respect that same distinction — see Requirements below.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this spec precedes any implementation of the rollup reads.
- **ART-II** — The Model is the Single Source of Truth: this is the entire point of this spec — the
  per-framework coverage counts and the summary card's numbers must be computed on demand from the
  existing `RegulatoryFramework`/`Control`/`ControlMapping` data (via COMPLY-03's derived status),
  never a separately maintained/cached figure that can drift from what the underlying mappings say.
- **ART-V** — Security by Design: this spec's central open question (Q1 below) is exactly a
  least-privilege/data-exposure question — whether aggregate rollup counts can leak
  governance-sensitive information about specific Applications to a caller who could not read that
  data directly.
- **ART-XI** — Traceability End to End: every number this spec surfaces must be explainable — an
  architect looking at "3 non-compliant entities" for a framework must be able to get from that
  count back to the specific entities and mappings that produced it (already possible via COMPLY-02's
  reverse lookups).

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Aggregate compliance posture data. Individually, `compliance_status` on an
Application-targeted mapping is already sensitive enough to require `READ_APPLICATION_GOVERNANCE`
(COMPLY-02). This spec's new surfaces are aggregates (counts, percentages) over that same data — the
central threat-modeling question is whether an aggregate can leak what an individual read cannot.

**Trust boundaries crossed**: Browser → API, same as every other read endpoint in the platform. No
new external integration.

**Abuse cases**:
- A caller lacking `READ_APPLICATION_GOVERNANCE` (e.g. a Reviewer) could potentially infer
  Application-specific compliance facts by comparing a framework's rollup counts before and after an
  Application's mapping changes, if those counts are computed from ungated data → mitigation
  resolved by Q1 below, following COMPLY-02's own established precedent of filtering
  Application-targeted rows out of shared responses for callers lacking the permission, rather than
  gating the whole response.

**Residual risk**: Aggregate counts are inherently lower-resolution than the individual records they
summarize; some risk of statistical inference (e.g. a framework with exactly one mapped entity)
remains regardless of which option Q1 resolves to, and is accepted as consistent with the residual
risk already accepted for every other count-based rollup in the platform (e.g. the Application
Portfolio's own aggregate views).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a framework's compliance coverage at a glance (Priority: P1)

An Enterprise Architect reviewing a specific `RegulatoryFramework` (e.g. GDPR) wants to know, without
manually reading every mapped control one by one, how many entities are Compliant, how many are
Non-Compliant, how many are Partial, how many are Not Assessed, and how many are Not Applicable to
that framework specifically — a live count, not a hand-maintained tracker.

**Why this priority**: This is the core deliverable the whole bundle exists to produce — a rollup
that is a rendered output of the model, replacing what would otherwise be a manually-maintained
spreadsheet. Without it, COMPLY-01–03's typed data has no summarized read surface at all.

**Independent Test**: Map several controls from one framework to several different entities with a
mix of compliance statuses, then view that framework's coverage rollup and confirm the counts match
the mapped entities' actual derived statuses for that framework.

**Acceptance Scenarios**:

1. **Given** a framework with controls mapped to five entities — two Compliant, one Non-Compliant,
   one Partial, one with no assessed controls yet — **When** an architect views that framework's
   coverage rollup, **Then** the rollup shows 2 Compliant, 1 Non-Compliant, 1 Partial, 1 Not
   Assessed, 0 Not Applicable.
2. **Given** an entity has controls mapped from two different frameworks, with a Non-Compliant status
   with respect to Framework A but a fully Compliant status with respect to Framework B, **When** an
   architect views each framework's coverage rollup separately, **Then** that entity counts toward
   Framework A's Non-Compliant bucket and Framework B's Compliant bucket — never the same bucket in
   both, and never blended into one cross-framework status.
3. **Given** a framework has a standing, estate-wide ("organization"-scoped) obligation mapped with
   status Partial, in addition to its per-entity mappings, **When** an architect views that
   framework's coverage rollup, **Then** the estate-wide obligation's status is shown as its own
   distinct line, not counted as though it were one more "entity."
4. **Given** a framework's mapped entities include one Application currently Non-Compliant, **When**
   a Reviewer lacking `READ_APPLICATION_GOVERNANCE` views that framework's coverage rollup, **Then**
   that Application is excluded from every bucket's count, and the rollup's totals reflect only the
   entities the Reviewer is permitted to see — never silently including a count that hints at the
   excluded Application's status.

---

### User Story 2 - See the platform's overall compliance posture without opening Compliance (Priority: P2)

An Enterprise Architect glancing at the platform's main dashboard wants to immediately know: how many
regulatory frameworks does ADP track, what fraction of the estate's mapped entities are fully
compliant, and how many entities need attention right now — without navigating into the Compliance
section at all.

**Why this priority**: This is the dashboard-level summary the bundle asks for, mirroring Strategy's
own already-shipped Overview card. It is lower priority than User Story 1 because the detailed
per-framework rollup is the more load-bearing capability; the summary card is a compact derivative
view of the same underlying data.

**Independent Test**: With a mix of frameworks and mapped entities across several compliance
statuses already in the system, load the Overview dashboard and confirm the summary card's framework
count, overall coverage percentage, and at-risk entity count all match what direct inspection of the
underlying data would produce.

**Acceptance Scenarios**:

1. **Given** the estate has 3 registered frameworks, **When** an architect views the Overview
   dashboard, **Then** the Compliance summary card shows a framework count of 3.
2. **Given** 10 distinct entities have at least one mapped control across the whole estate, and 6 of
   them have an overall derived status of Compliant, **When** an architect views the summary card,
   **Then** it shows an overall coverage figure of 60%.
3. **Given** 2 entities have an overall derived status of Non-Compliant and 1 has Partial, **When**
   an architect views the summary card, **Then** the at-risk entity count shown is 3.
4. **Given** the architect clicks through from the summary card, **When** the click completes,
   **Then** they land on the dedicated Compliance screen (not the unrelated Governance
   validation-exceptions tab).

---

### Edge Cases

- A framework with zero controls mapped to anything yet: its coverage rollup shows every bucket at
  zero, not an error and not an absent row.
- An entity mapped to controls from a framework, where every one of those controls is Not
  Applicable, with none Compliant: per COMPLY-03's own resolved rule, this entity counts toward that
  framework's Not Applicable bucket, not Not Assessed and not Compliant.
- The platform has zero registered frameworks at all: the summary card shows a framework count of
  zero and a coverage percentage that reads as "no data yet" rather than a misleading 0% (0% reads
  as "everything failing," which is not what "nothing exists yet" means).
- A caller without `READ_APPLICATION_GOVERNANCE` views a framework's rollup that includes
  Application-targeted mappings: those entities are excluded from every count they see (FR-007).
- A framework whose *only* mapped entities are Application-targeted: for a caller lacking
  `READ_APPLICATION_GOVERNANCE`, its coverage rollup shows every bucket at zero (FR-008's
  zero-state handling applies identically here, not a separate case) rather than an error or an
  absent framework.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For a given `RegulatoryFramework`, the system MUST provide a live count of every
  entity mapped (directly or via a mapped control) to that framework, grouped by that entity's
  compliance status *with respect to that framework specifically* — i.e., computed only from the
  subset of the entity's mapped controls that belong to that framework, not the entity's status
  across every framework it happens to have controls mapped from.
- **FR-002**: The per-framework coverage count MUST cover all five possible derived statuses
  (Compliant, Partial, Non-Compliant, Not Assessed, Not Applicable), showing zero rather than
  omitting a bucket that currently has no entities in it.
- **FR-003**: A framework's estate-wide ("organization"-scoped) obligation mapping, if one exists,
  MUST be shown as its own distinct status line in that framework's rollup, separate from the
  per-entity counts, since it has no single owning entity to be counted as one of them.
- **FR-004**: The system MUST provide a platform-wide summary showing: the total count of registered
  regulatory frameworks; an overall coverage percentage (the share of all distinctly-mapped entities
  across the whole estate whose overall derived compliance status is Compliant); and an at-risk
  entity count (entities whose overall derived compliance status is Non-Compliant or Partial).
- **FR-005**: The platform-wide summary MUST be reachable from the platform's main dashboard, and
  MUST link through to the dedicated Compliance section for further detail.
- **FR-006**: Every count and percentage this spec introduces MUST be computed fresh from the
  current `RegulatoryFramework`/`Control`/`ControlMapping` data at the moment it is requested — never
  read from a separately stored or cached figure that could drift from what the underlying data
  actually says.
- **FR-007**: For a caller lacking `READ_APPLICATION_GOVERNANCE`, every Application-targeted entity
  MUST be excluded from every count and percentage in both the per-framework coverage rollup and the
  platform-wide summary — mirroring COMPLY-02's own forward-lookup precedent of filtering
  Application-targeted rows out of a shared response rather than gating the whole response. A
  framework's rollup (and the platform-wide summary) MAY therefore show different totals to
  different callers depending on their permissions; this MUST be clear from the presentation so it
  does not read as inconsistent or broken (resolved via user clarification, Q1).
- **FR-008**: When a framework has zero controls mapped to anything, its coverage rollup MUST still
  display, showing every bucket at zero rather than omitting the framework or erroring.
- **FR-009**: When the platform has zero registered frameworks, the platform-wide summary MUST
  clearly distinguish "no data recorded yet" from a genuine 0% coverage figure, so an empty estate is
  never visually indistinguishable from a fully non-compliant one.

### Key Entities *(include if feature involves data)*

- **Framework Coverage Rollup**: A computed view, not a persisted entity — for one
  `RegulatoryFramework`, a count of entities at each of the five compliance-status buckets (scoped
  to that framework's own controls only), plus that framework's estate-wide obligation status as a
  separate line if one exists.
- **Compliance Summary**: A computed view, not a persisted entity — platform-wide: total framework
  count, overall coverage percentage, and at-risk entity count, derived across every framework's
  mapped entities at once.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can determine a specific framework's full compliance coverage picture
  (all five status buckets plus any estate-wide obligation) in one glance, without manually opening
  and cross-referencing individual control mappings.
- **SC-002**: An architect can determine the platform's overall compliance posture (framework count,
  coverage percentage, at-risk count) directly from the main dashboard, with zero additional
  navigation required to see those three numbers.
- **SC-003**: Every rollup number is independently reproducible: recomputing it by hand from the
  underlying `ControlMapping` data (as already exposed by COMPLY-02's reverse-lookup endpoints)
  always matches what the rollup displays, in 100% of tested scenarios.
- **SC-004**: A caller lacking `READ_APPLICATION_GOVERNANCE` never sees an Application-specific
  compliance fact through the aggregate rollups that they could not already see through the existing
  gated individual-mapping reads (per Q1's resolution).
- **SC-005**: Changing a single `ControlMapping`'s status is reflected in both the per-framework
  rollup and the platform-wide summary the next time either is viewed, with no stale figure possible.

## Assumptions

- **Scope boundary with COMPLY-02**: The "entity-level traceability" bullet from the source bundle
  is already fully delivered by COMPLY-02's reverse-lookup endpoints and is explicitly out of scope
  here — see the Ground-Truth Corrections above.
- **Screen placement**: Both new rollup views belong on the existing dedicated Compliance screen
  (`web/src/compliance/`) and the platform's main Overview dashboard — not on
  `web/src/governance/ComplianceTab.tsx`, which is an unrelated, already-shipped LLM-Judge
  validation-exceptions view that merely happens to share the word "Compliance" in its name.
- **"At-risk" definition**: An entity is counted as at-risk in the platform-wide summary if its
  overall derived compliance status is Non-Compliant or Partial — both represent a known,
  unresolved gap, as opposed to Not Assessed (unknown) or Not Applicable (out of scope by design).
- **"Overall coverage %" denominator**: The percentage is computed over every entity that has at
  least one `ControlMapping` anywhere in the estate (across any framework), not over every entity
  that exists in the platform — an entity nobody has ever attempted to assess against any framework
  is not part of the coverage calculation at all, consistent with how Not-Assessed-vs-unmapped is
  already treated by COMPLY-03.
- **Entity types included**: The per-framework rollup and platform-wide summary count entities of
  all four entity-targeted mapping types COMPLY-02/03 already support — Capability, Application,
  Design, and Pattern — with no type-specific exclusion beyond the sensitivity handling in Q1/FR-007.
- **No PDF/export report, no cross-framework overlap analysis**: Both explicitly out of scope per
  the source bundle, unchanged here.
- **No new persisted data**: Both rollup views are computed on demand from existing
  `RegulatoryFramework`/`Control`/`ControlMapping` tables (COMPLY-01/02) and the existing derived
  status function (COMPLY-03) — no new table, no migration expected for this spec, though that is
  confirmed at planning time, not assumed final here.
- **Application-visibility resolution (Q1, resolved by user)**: For a caller lacking
  `READ_APPLICATION_GOVERNANCE`, Application-targeted entities are excluded entirely from every
  rollup count and percentage (FR-007) — mirroring COMPLY-02's own forward-lookup precedent of
  filtering rather than blocking. The same framework's rollup, and the platform-wide summary, can
  therefore legitimately show different totals to different callers.
