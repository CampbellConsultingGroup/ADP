# Feature Specification: Strategy Domain Linkage

**Feature Branch**: `925-strategy-compliance-linkage`
**Created**: 2026-08-19
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md COMPLY_05 only" — scoped strictly to
COMPLY-05 (Strategy Domain Linkage) of the five-spec Compliance Domain bundle. COMPLY-01 (Framework &
Control Registry), COMPLY-02 (Control Mappings), COMPLY-03 (Derived Compliance Status), and COMPLY-04
(Compliance Rollup) are prerequisites and are already implemented (`specs/921-…`, `specs/922-…`,
`specs/923-…`, `specs/924-…`). This spec links the Compliance domain back to the existing Strategy
domain (Strategic Themes/Objectives, Strategy Initiatives).

## Clarifications

### Session 2026-08-19

- Q: The source bundle lists `ThemeFrameworkMapping` (a reusable Strategic Theme tagged against one or
  more Regulatory Frameworks) as a lower-priority third link, explicitly recommending it be built "only
  if the other two links prove insufficient for the reporting need." Should this spec build it now, or
  defer it? → A: Defer it. This spec builds only `ObjectiveControlMapping` and
  `InitiativeControlMapping` — the two load-bearing links. `ThemeFrameworkMapping` is filed as an
  explicit follow-on (tracked as a bead, not left to informal memory) so it isn't lost, to be picked up
  only once a real portfolio-reporting need for it surfaces.

**Ground-truth correction (resolved by direct code inspection, not assumed)**: the bundle names one
open question as "load-bearing for the whole spec" — whether `Initiative → Objective` is currently
mandatory in the schema, since a mandatory link would force bottom-up compliance remediation
(assessment finds a gap → Initiative directly, no Objective) through strategic-planning ceremony it
doesn't need. Confirmed false: `adp.strategy.initiatives`'s `strategy_initiatives` table carries no
`objective_id` column at all — the relationship lives in a separate many-to-many join table
(`strategy_initiative_objective_links`), and `StrategyInitiative.objective_ids` already defaults to an
empty list. An Initiative can exist today with zero linked Objectives. This spec requires no schema
change to enable that path; FR-004 below states it as an explicit non-regression guarantee rather than a
new capability.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: "why does this objective exist" and "what
  strategic work is remediating this compliance gap" become typed, queryable facts instead of
  tribal knowledge, a spreadsheet, or a sentence in an audit narrative document someone has to keep in
  sync by hand.
- **ART-XI** — Traceability End to End: this is a traceability link in the literal sense — connecting
  the Compliance domain's `Control`/`ControlMapping` (COMPLY-01/02) to the Strategy domain's
  `StrategicObjective`/`StrategyInitiative`, following the exact composite-PK/`ON DELETE CASCADE`
  join-table shape already established by `objective_capability`/`objective_value_stream` and by
  COMPLY-02's own mapping tables.
- **ART-XIII** — Typed Contracts Everywhere: both new link types are typed Pydantic models
  (`extra="forbid"`), not a freeform note field on either side.
- **ART-XV** — Schema Evolution is Governed: this spec introduces two new join tables to the canonical
  model via a governed migration, following the platform's existing migration-owns-constraints
  discipline.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: which strategic objectives and initiatives are tied to which regulatory controls and
compliance gaps — this is a more sensitive fact than either side alone, since it reveals not just *that*
a gap exists (COMPLY-02/03/04 already disclose that to permitted readers) but *what the organization is
doing about it and how urgently*, which is itself audit- and investor-relevant information.

**Trust boundaries crossed**: Browser → API, through the platform's existing OIDC-authenticated session —
no new trust boundary is introduced.

**Abuse cases**:
- An unauthorized actor creates or edits a link to fabricate a false remediation narrative ("this gap is
  already being worked" when no real Initiative work is happening), or to sever a true one and hide that
  work is underway → mitigated by gating all writes to both link types behind the same permissions that
  already gate Compliance and Strategy writes (`WRITE_COMPLIANCE` / `WRITE_BUSINESS_ARCH`), held
  identically by the same three architect personas plus Platform Admin — no new, weaker write path is
  introduced.
- A user without `READ_APPLICATION_GOVERNANCE` infers an Application's compliance gap indirectly by
  seeing that an Initiative is linked to a `ControlMapping` row, even without being permitted to see that
  mapping's own target/status directly → mitigated by having the Initiative-side reverse lookup inherit
  the same read gate the underlying `ControlMapping` row already carries (COMPLY-02's own established
  precedent), rather than exposing it via a lesser-gated shortcut.
- A `Control`, `ControlMapping`, `StrategicObjective`, or `StrategyInitiative` is deleted while links to
  it exist, silently orphaning rows or leaving a dangling reference → mitigated by cascading the delete
  to dependent link rows (disclosed to the user performing the delete), consistent with the platform's
  existing cascade-with-disclosure convention rather than leaving orphaned data or blocking the delete
  outright.

**Residual risk**: as with COMPLY-02, there is no independent verification workflow — an architect
holding write access can record a link that doesn't reflect real remediation intent, the same class of
trust already accepted for `compliance_status` itself. This feature does not change that posture; it
does not introduce a new way to falsify compliance data, only a new way to link two already-writable
facts together.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trace remediation work back to a compliance gap (Priority: P1)

An architect is looking at a `ControlMapping` that has just been assessed `non_compliant` (e.g., an
Application's MFA enforcement gap against GDPR Art. 32). They open a Strategy Initiative — either one
that already exists or one they create for this purpose — and link it to that specific gap. From then on,
anyone looking at either side (the Initiative, or the compliance gap itself) can see the other: the
Initiative shows which compliance gap(s) it's remediating, and the gap shows which Initiative(s), if any,
are actively working to close it. When the gap is later reassessed as `compliant`, the live status shown
through the Initiative's link updates automatically — there is no separate status to remember to update
on the link itself.

**Why this priority**: this is the highest-value link in the bundle — without it, a `non_compliant`
status is a dashboard fact with no connection to the work meant to fix it, which is exactly the kind of
drift-prone, hand-maintained tracking this platform exists to eliminate.

**Independent Test**: can be fully tested by linking one Initiative to one specific `ControlMapping`,
confirming the link is visible from both sides, confirming an Initiative can be linked to a compliance
gap with **no** Strategic Objective involved at any point, and confirming the shown status changes
automatically when the underlying mapping's `compliance_status` is later updated — without touching the
link itself.

**Acceptance Scenarios**:

1. **Given** a `ControlMapping` assessed `non_compliant` against an Application, **When** an architect
   links an existing Strategy Initiative to that specific mapping, **Then** the link is created and is
   visible from both the Initiative's own view and the mapping's own view.
2. **Given** a compliance gap with no Strategic Objective anywhere in the system related to it, **When**
   an architect creates a brand-new Initiative and links it directly to the gap, **Then** the Initiative
   is created and linked successfully with zero Objective involved — no strategic-planning step is
   required first.
3. **Given** an Initiative linked to a `ControlMapping` currently showing `non_compliant`, **When** that
   mapping is later reassessed and its `compliance_status` is updated to `compliant` (through the
   existing compliance-mapping update flow, not through this feature), **Then** the status shown wherever
   the Initiative's linked mapping appears reflects `compliant` immediately, with no separate update
   performed on the link itself.
4. **Given** an existing Initiative-to-mapping link, **When** an architect removes it, **Then** the link
   no longer appears from either side, and neither the Initiative nor the `ControlMapping` row itself is
   affected.
5. **Given** one `ControlMapping` row representing a single compliance gap, **When** two different
   Initiatives are each linked to it (e.g., a short-term mitigation and a longer-term remediation), **Then**
   both links coexist and both are visible from the mapping's side.

---

### User Story 2 - See why an objective exists (Priority: P2)

An architect reviewing a Strategic Objective wants to know whether it exists because of a business goal,
a regulatory requirement, or both. They link the Objective to the specific `Control`(s) that drove it
(e.g., an objective to "achieve GDPR Art. 32 security-of-processing readiness across all customer-facing
applications" links to GDPR Art. 32 itself). Later, anyone reviewing that objective — or compiling a
report on how much of this year's strategic work is regulatory-driven — can see the connection directly
rather than relying on someone's memory of why the objective was proposed.

**Why this priority**: this is audit-narrative and portfolio-reporting value, not the live remediation
loop User Story 1 provides — real, but lower-stakes than losing traceability on active remediation work.

**Independent Test**: can be fully tested by linking one Objective to one Control, confirming the link is
visible from both the Objective's own view and the Control's own view, and confirming the same Objective
can be linked to multiple Controls (e.g., it satisfies more than one regulatory clause at once).

**Acceptance Scenarios**:

1. **Given** a Strategic Objective and an existing Control, **When** an architect links them, **Then**
   the link is visible from both the Objective's own view and the Control's own view.
2. **Given** a Strategic Objective already linked to one Control, **When** an architect links it to a
   second, different Control (potentially from a different Framework), **Then** both links coexist and
   both are visible.
3. **Given** an existing Objective-to-Control link, **When** an architect removes it, **Then** the link
   no longer appears from either side, and neither the Objective nor the Control itself is affected.
4. **Given** a Strategic Objective with no Objective-to-Control link at all, **When** it is viewed,
   **Then** it is shown as purely business-driven — no regulatory linkage is implied or fabricated.

---

### Edge Cases

- What happens when the `ControlMapping` an Initiative is linked to is deleted (e.g., because its target
  Application or Design was removed)? The Initiative-to-mapping link is cascade-deleted along with it —
  the Initiative itself is unaffected and simply loses that one link.
- What happens when a Control is deleted while an Objective is linked to it? The Objective-to-Control
  link is cascade-deleted; the Objective itself, and any of its other links, are unaffected.
- What happens when a Strategic Objective or Strategy Initiative is deleted while it holds links to
  Controls or `ControlMapping` rows? The corresponding link rows are cascade-deleted; the Compliance-side
  rows (Control, ControlMapping) are unaffected.
- Can the same Objective be linked to the same Control twice? No — re-linking an already-linked pair is a
  no-op (or is rejected as a duplicate), consistent with how every other many-to-many link in the
  platform behaves.
- Can an Initiative be linked to a `ControlMapping` whose `compliance_status` is already `compliant` (not
  actually a gap)? Yes — no validation forbids this; an Initiative may exist to *maintain* a compliant
  status (e.g., ongoing evidence collection) as well as to fix a broken one.
- What happens to `ObjectiveControlMapping`/`InitiativeControlMapping` when the *target entity* underlying
  a `ControlMapping` (e.g., the Application or Design) is deleted rather than the mapping row itself? This
  is governed entirely by COMPLY-02's existing cascade behavior on `ControlMapping` — this feature adds no
  new cascade rule beyond following that same chain down to its own link rows.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an authorized user to link a Strategic Objective to a Control, recording
  that the objective exists, in whole or part, because of that regulatory control.
- **FR-002**: System MUST allow an authorized user to remove an existing Objective-to-Control link.
- **FR-003**: System MUST allow querying, for a given Objective, every Control it is linked to, and the
  reverse — for a given Control, every Objective linked to it — supporting reporting such as "which
  objectives exist because of a regulatory requirement."
- **FR-004**: System MUST NOT require a Strategic Objective to exist before a Strategy Initiative can be
  created and linked to a compliance gap — bottom-up remediation (an assessment finds a gap and someone
  opens an Initiative directly, with no Objective involved) MUST remain fully supported. This capability
  already exists in the platform today and MUST NOT regress as part of this feature.
- **FR-005**: System MUST allow an authorized user to link a Strategy Initiative to a specific
  `ControlMapping` (a Control assessed in the context of one particular target — an entity, or the
  estate-wide obligation scope), not to the abstract Control alone — since one Control may carry several
  independent compliance statuses across different targets (COMPLY-02), and remediation work addresses
  one specific gap, not the control in the abstract.
- **FR-006**: System MUST allow an authorized user to remove an existing Initiative-to-mapping link.
- **FR-007**: System MUST allow querying, for a given Initiative, every `ControlMapping` it is linked to,
  and the reverse — for a given `ControlMapping`, every Initiative linked to it as remediation or
  maintenance work.
- **FR-008**: The compliance status shown wherever an Initiative's linked mapping is displayed MUST
  always reflect that mapping's current, live `compliance_status` (COMPLY-02/03) — the link itself MUST
  NOT carry a separate, independently-editable status field that could drift out of sync.
- **FR-009**: System MUST NOT automatically create a Strategy Initiative when a `ControlMapping`'s status
  changes to `non_compliant` — creating and linking the Initiative remains an explicit human action.
- **FR-010**: The two link types are independent — an Initiative-to-mapping link MUST NOT require a
  corresponding Objective-to-Control link to exist, and vice versa.
- **FR-011**: Deleting a Control, a `ControlMapping`, a Strategic Objective, or a Strategy Initiative MUST
  cascade-delete any Objective-to-Control or Initiative-to-mapping link rows that reference it, rather
  than blocking the delete or leaving an orphaned/dangling link.
- **FR-012**: Creating or removing either link type MUST be restricted to the same personas already
  permitted to write Compliance or Strategy data (Solution Architect, Technical Architect, Enterprise
  Architect, Platform Admin); a Reviewer MUST remain read-only, consistent with every other write in
  either domain.
- **FR-013**: Read access to an Initiative's linked `ControlMapping`(s) — including the reverse lookup
  from the mapping's side — MUST inherit the same read gate the underlying `ControlMapping` row already
  carries (COMPLY-02): an Application-targeted mapping still requires the sensitive-governance read
  permission to be visible even when reached through its linked Initiative, not just when read directly.
- **FR-014**: Both link types MUST support many-to-many multiplicity: one Objective may link to many
  Controls and one Control may be linked to many Objectives; one Initiative may link to many
  `ControlMapping` rows and one `ControlMapping` row may be linked to many Initiatives.
- **FR-015**: System MUST prevent the same (Objective, Control) pair, or the same (Initiative,
  `ControlMapping`) pair, from being linked more than once.

### Key Entities *(include if feature involves data)*

- **ObjectiveControlMapping**: a link between an existing Strategic Objective and an existing Control,
  recording that the objective is regulatory-driven (in whole or part). Carries no status of its own —
  the presence of the link is the signal; whether the underlying control is satisfied lives on
  `ControlMapping` (COMPLY-02), not here.
- **InitiativeControlMapping**: a link between an existing Strategy Initiative and a specific
  `ControlMapping` row (a Control assessed against one particular target). Represents remediation or
  maintenance work in progress or planned against that specific compliance gap or standing obligation.
  Carries no status of its own — the live status is always read from the linked `ControlMapping`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can link an existing Strategy Initiative to a specific compliance gap, and see
  that link reflected from both sides, in a single action without leaving either the Initiative's or the
  gap's own view.
- **SC-002**: An architect can create and link a new Strategy Initiative directly to a compliance gap
  with zero forced detour through Strategic Objective creation — 0 required intermediate steps.
- **SC-003**: Given any `ControlMapping` currently assessed `non_compliant`, an architect can determine,
  from that mapping's own view alone (no cross-referencing a separate tracker or spreadsheet), whether
  any remediation Initiative already exists for it.
- **SC-004**: Given any Strategic Objective, a viewer with appropriate access can determine, from that
  objective's own view alone, whether it is regulatory-driven and by which specific Control(s) — with
  zero cases where the shown link set is stale relative to the underlying data.
- **SC-005**: 100% of the time, the compliance status shown through an Initiative's linked mapping
  matches the status shown on the `ControlMapping` itself — there is never a separately-drifted value to
  reconcile.

## Assumptions

- **`ThemeFrameworkMapping` (the bundle's third, lower-priority link) is explicitly deferred**, per the
  2026-08-19 clarification — this spec builds only `ObjectiveControlMapping` and
  `InitiativeControlMapping`. Deferred work is tracked as a bead, not left informally in this document.
- **`ObjectiveControlMapping` carries no status field of its own** — a bare link, per the bundle's own
  stated lean ("no evidence yet that a status field earns its complexity here"). If a future need arises
  to distinguish "in progress toward compliance" from "compliance is incidental to this objective," that
  is a follow-on decision, not assumed here.
- **No dedicated cross-domain rollup/percentage endpoint** (e.g., "what % of this year's strategic work
  is compliance-driven") ships as part of this spec. The two traceability link types (FR-003, FR-007)
  make that reporting *possible* via direct list queries; a purpose-built aggregate view is left for a
  future spec once a real need for it is confirmed, mirroring COMPLY-04's own precedent of building
  rollups only after the underlying links already exist.
- **Permission gating reuses existing gates exactly, with no new `ActionType`**: writes require either
  `WRITE_COMPLIANCE` or `WRITE_BUSINESS_ARCH` (both already held by the identical set of personas —
  Solution Architect, Technical Architect, Enterprise Architect, Platform Admin), and reads of an
  Initiative's linked mappings inherit the mapping's own existing COMPLY-02 read gate rather than
  introducing a new permission.
- **Initiative → Objective is already optional in the existing schema** (confirmed by direct code
  inspection, not assumed — see Clarifications). This spec depends on, but does not change, that existing
  behavior.
