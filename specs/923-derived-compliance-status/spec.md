# Feature Specification: Derived Compliance Status

**Feature Branch**: `923-derived-compliance-status`
**Created**: 2026-08-18
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md COMPY_03 only"

Source: COMPLY-03 ("Derived Compliance Status") of `docs/speckit-compliance-bundle_1.md`, the third
spec in a five-spec Compliance Domain bundle. COMPLY-01 (`RegulatoryFramework`/`Control` registry)
and COMPLY-02 (`ControlMapping` traceability links) are already implemented — see
`specs/921-compliance-framework-registry/` and `specs/922-control-mappings/`. This spec covers
COMPLY-03 only, per explicit user scoping; COMPLY-04 (read-side rollup) and COMPLY-05 (Strategy
linkage) are out of scope here.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: this spec precedes any implementation of the derivation logic.
- **ART-IV** — Test-Driven Development: the source bundle explicitly requires this logic be validated
  as a standalone pure function against a documented matrix of status combinations *before* it is
  wired into any store or router — mirroring how `adp.strategy.store.compute_status()` and
  `adp.application.store.compute_business_value_score()` were built and tested.
- **ART-II** — The Model is the Single Source of Truth: this is the central rule this feature exists
  to serve. An entity's overall compliance status MUST NOT become an independently hand-set or
  cached field that can drift from what its underlying `ControlMapping` rows actually say — it is a
  computed view over already-typed data, the same discipline already applied to `ObjectiveStatus`
  (derived from progress history) and Application health score (derived via minimum-aggregation over
  per-dimension assessments).
- **ART-XIII** — Typed Contracts Everywhere: the derivation returns the existing `ComplianceStatus`
  enum (COMPLY-02) — no new status vocabulary is introduced.
- **ART-XI** — Traceability End to End: the derived status must remain traceable back to the specific
  mapped controls that produced it (an architect asking "why is this Non-Compliant" must be able to
  find the one mapping that caused it), not collapse into an opaque single value.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: None new. This feature adds a computation over `ControlMapping` rows
(`compliance_status`, already-sensitive per COMPLY-02) that already exist and are already subject to
COMPLY-02's read-side sensitivity gating (Application-targeted mappings require
`READ_APPLICATION_GOVERNANCE`). This spec introduces no new API endpoint and no new persisted data,
so it exposes no new data surface on its own.

**Trust boundaries crossed**: None. This is an in-process, no-I/O pure function plus a thin
same-package lookup helper; it does not cross a network or process boundary.

**Abuse cases**: None specific to this feature. The one risk worth naming for whoever wires this
function into a future consumer (COMPLY-04 or elsewhere): that consumer MUST apply the same
sensitivity gate COMPLY-02 already applies when *reading* a mapping's `compliance_status`
(e.g. an Application's derived status must not be computable by a caller who could not have read
that Application's individual mappings) — this spec's own scope has no caller to enforce that against
yet, so it is called out here rather than silently assumed.

**Residual risk**: None beyond the above, which is explicitly deferred to the spec that adds a
caller (documented in Assumptions below).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One failing control is never hidden by passing ones (Priority: P1)

An Enterprise Architect (or a future dashboard/API acting on their behalf) needs to know, at a
glance, whether an entity (a Capability, Application, Design, or knowledge-base Pattern) is actually
in good regulatory standing — without personally reading every individual control mapping and
mentally reconciling them. The single most important property of that summary is that it never
hides a real problem: one Non-Compliant control anywhere must dominate the result, exactly the way
Application Health already treats its worst dimension as the whole score, rather than being averaged
away by many passing controls.

**Why this priority**: This is the entire reason a derived status exists instead of a hand-set field
— to make risk immediately, reliably visible. Getting this wrong (e.g. averaging) would make the
feature actively misleading, worse than no summary at all.

**Independent Test**: Can be fully tested by calling the derivation with a set of mapped-control
statuses that includes exactly one Non-Compliant among many Compliant ones, and confirming the
result is Non-Compliant.

**Acceptance Scenarios**:

1. **Given** an entity has one mapped control with status Non-Compliant and twenty mapped controls
   with status Compliant, **When** the overall status is derived, **Then** the result is
   Non-Compliant.
2. **Given** an entity has one mapped control with status Non-Compliant and no other mapped
   controls, **When** the overall status is derived, **Then** the result is Non-Compliant.

---

### User Story 2 - Unresolved or partial work is visibly distinct from full compliance (Priority: P2)

The same architect needs to distinguish "nothing is actively failing, but work is still outstanding"
from genuine, complete compliance — so that an entity with several controls still awaiting
assessment doesn't read as falsely reassuring.

**Why this priority**: Without this distinction, newly-mapped or in-progress compliance work would
either look identically "fine" as fully-assessed compliant work, or would incorrectly trip the same
Non-Compliant signal reserved for actual failures — both are misleading in different ways.

**Independent Test**: Can be fully tested by calling the derivation with a mix of Partial and Not
Assessed statuses (no Non-Compliant present) and confirming the result is Partial.

**Acceptance Scenarios**:

1. **Given** an entity has no Non-Compliant mapped controls, but has at least one Partial or Not
   Assessed mapped control, **When** the overall status is derived, **Then** the result is Partial.
2. **Given** an entity has one mapped control freshly linked with its default status (Not Assessed)
   while all its other mapped controls are Compliant, **When** the overall status is derived,
   **Then** the result is Partial, not Compliant — mapping a new, not-yet-assessed control onto an
   otherwise fully-compliant entity correctly downgrades its status until that new mapping is
   actually assessed.

---

### User Story 3 - Full compliance is only reported when it is actually earned (Priority: P3)

The architect needs "Compliant" to mean what it says: every applicable control is either compliant
or explicitly marked not applicable, and at least one control was actually assessed as compliant —
not just "nothing bad happened to be recorded yet."

**Why this priority**: This is the positive counterpart to User Story 1 — it protects the meaning of
the best-case label the same way Story 1 protects the worst-case one. Lower priority than 1/2 because
an overly cautious false-Partial is a much smaller harm than a false-Compliant would be.

**Independent Test**: Can be fully tested by calling the derivation with an all-Compliant set, and
separately with a Compliant+Not-Applicable mix, confirming both produce Compliant.

**Acceptance Scenarios**:

1. **Given** every one of an entity's mapped controls has status Compliant, **When** the overall
   status is derived, **Then** the result is Compliant.
2. **Given** an entity's mapped controls are a mix of Compliant and Not Applicable, with at least one
   Compliant, **When** the overall status is derived, **Then** the result is Compliant.
3. **Given** every one of an entity's mapped controls has status Not Applicable and none is
   Compliant, **When** the overall status is derived, **Then** the result is Not Applicable — a
   distinct outcome meaning the framework genuinely does not apply here, not the same as an
   unassessed entity.

---

### Edge Cases

- An entity with zero mapped controls at all (no `ControlMapping` rows reference it) derives to Not
  Assessed — there is nothing to assess, and this must read as "unknown," not as a false Compliant
  or false Non-Compliant.
- An entity whose *every* mapped control is Not Applicable, with none Compliant, derives to Not
  Applicable (resolved via user clarification — see Assumptions) — a genuine gap in the aggregation
  rule as originally proposed in the source bundle, which did not cover this combination.
- Deriving status for an entity type this feature does not cover (the estate-wide/"organization"
  scope introduced by COMPLY-02) is explicitly out of scope here — see Assumptions.
- A control mapped, then later unmapped (its `ControlMapping` row deleted): the next derivation
  simply excludes it, since the derivation always reads the current set of mappings fresh rather than
  remembering past ones.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST be able to derive one overall Compliance Status for a given Capability,
  Application, Design, or Pattern, based on the compliance status of every Control currently mapped
  to that entity.
- **FR-002**: If any of an entity's mapped controls has status Non-Compliant, the derived overall
  status MUST be Non-Compliant, regardless of how many other mapped controls are Compliant.
- **FR-003**: If none of an entity's mapped controls is Non-Compliant, but at least one is Partial or
  Not Assessed, the derived overall status MUST be Partial.
- **FR-004**: If every one of an entity's mapped controls is Compliant or Not Applicable, and at
  least one is Compliant, the derived overall status MUST be Compliant.
- **FR-005**: If an entity has no mapped controls at all, the derived overall status MUST be Not
  Assessed.
- **FR-006**: If every one of an entity's mapped controls is Not Applicable and none is Compliant,
  the derived overall status MUST be Not Applicable — a genuinely distinct, explicit outcome meaning
  "this framework does not apply to this entity," resolved via user clarification (Q1) rather than
  silently defaulting to Not Assessed (which would conflate "deliberately reviewed and found
  inapplicable" with "never looked at").
- **FR-007**: The derived status MUST always be computed fresh from the entity's current set of
  mapped controls at the moment it is requested — it MUST NOT be read from any separately stored or
  cached field that could fall out of sync with the underlying mappings.
- **FR-008**: The derivation rule MUST treat every mapped control equally: no control's position in
  its framework's hierarchy, and no notion of control severity or criticality, may change its
  contribution to the derived result in this pass.
- **FR-009**: The derived status MUST be expressed using the same fixed status vocabulary already
  used for an individual control mapping's own status (Compliant / Partial / Non-Compliant / Not
  Assessed / Not Applicable), so it can be displayed and compared using one consistent vocabulary
  throughout the product.
- **FR-010**: The derivation rule MUST be independently verifiable against a documented matrix of
  input status combinations (covering at minimum every scenario named in User Scenarios & Testing and
  Edge Cases above) before any other part of the system is permitted to depend on it.

### Key Entities *(include if feature involves data)*

- **Compliance Status (derived)**: The single overall status value computed for one Capability,
  Application, Design, or Pattern from the set of `ControlMapping` rows (COMPLY-02) that currently
  target it. Not a new persisted entity — it is a computed value, produced on demand from existing
  data, using the same status vocabulary (`ComplianceStatus`) already defined for an individual
  mapping.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every documented input-status-combination scenario (at minimum: a Non-Compliant
  control present; no Non-Compliant but a Partial or Not-Assessed control present; every control
  Compliant or Not-Applicable with at least one Compliant; zero mapped controls; every control Not
  Applicable with none Compliant), the derived status matches the documented expected outcome, with
  zero discrepancies, before this logic is used anywhere else.
- **SC-002**: A single Non-Compliant control mapped to an entity is never masked by any number of
  Compliant controls mapped to the same entity — demonstrated with a deliberately lopsided ratio
  (one Non-Compliant among at least twenty Compliant controls still derives to Non-Compliant).
- **SC-003**: The same aggregation rule produces correct results for all four entity types this
  feature covers (Capability, Application, Design, Pattern) with no type-specific special-casing of
  the rule itself — confirmed by exercising the same scenario matrix against each entity type.
- **SC-004**: Adding, removing, or changing the status of a single mapped control on an entity is
  reflected the next time that entity's overall status is requested, with no stale result possible.

## Assumptions

- **Scope of entity types**: This pass computes the derived status only for the four
  FK-enforced, entity-targeted mapping types COMPLY-02 defines with a real owning entity —
  Capability, Application, Design, and Pattern. The estate-wide "organization" scope COMPLY-02 also
  supports (a control obligation with no single owning entity) has no natural per-entity status to
  derive and is left to COMPLY-04's framework-wide rollup work, consistent with how the source
  bundle already divides "per-entity derived status" (COMPLY-03) from "estate-wide coverage rollup"
  (COMPLY-04).
- **No new API surface in this pass**: Per the source bundle's own stated implementation order
  ("`compute_compliance_status()` should be built and tested as a standalone pure function before
  it's wired into any store or router"), this spec delivers the derivation logic itself plus the
  minimal lookup needed to gather an entity's current mapped-control statuses. It does not add a new
  HTTP endpoint — that is future work for whichever spec first needs to surface a derived status to
  a caller (expected to be COMPLY-04).
- **No weighting or severity scheme**: As the source bundle states explicitly, per-control severity
  or criticality weighting is a deliberately deferred v2 concern, not attempted here.
- **No time-decay**: A derived status reflects the most recently recorded `assessed_at` on each
  mapped control indefinitely; this pass does not add any automatic downgrade of stale assessments
  after a time period.
- **Read access to the function itself is unrestricted**: Since this pass adds no new API endpoint,
  there is no new permission surface to define. Whoever wires this into a future reader is
  responsible for applying the same sensitivity gate COMPLY-02 already applies to reading the
  underlying mappings (see Threat Model).
- **All-Not-Applicable resolution (Q1, resolved by user)**: When every one of an entity's mapped
  controls is Not Applicable and none is Compliant, the derived status is Not Applicable — a fifth,
  genuinely distinct reachable output (alongside Compliant/Partial/Non-Compliant/Not Assessed),
  deliberately not folded into Not Assessed, so "this framework doesn't apply here" reads differently
  from "nobody has looked yet."
