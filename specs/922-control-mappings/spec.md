# Feature Specification: Control Mappings (Traceability Links)

**Feature Branch**: `922-control-mappings`
**Created**: 2026-08-18
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md COMPLY_02 only" — scoped strictly to
COMPLY-02 (Control Mappings / Traceability Links) of the five-spec Compliance Domain bundle. COMPLY-01
(Framework & Control Registry) is a prerequisite and is already implemented (`specs/921-compliance-framework-registry/`).
COMPLY-03 (derived compliance status), COMPLY-04 (rollup reporting), and COMPLY-05 (Strategy linkage) are
explicitly out of scope for this spec and will be specified separately once these links exist for them to
build on.

## Clarifications

### Session 2026-08-18

- Q: Should a Control that represents a standing, estate-wide obligation with no single natural owning
  entity (e.g. GDPR Art. 30, "records of processing activities") be representable in this pass? → A: Yes —
  add a lightweight estate-wide assessment shape alongside the four entity-targeted mapping types, carrying
  the same status/evidence/assessment fields but no target-entity leg.
- Q: How should a Control's mapping target be modeled given it can point at four different entity types
  (Capability, Application, Design, Pattern)? → A: Four separate, fully database-level-FK-enforced tables,
  one per target type — consistent with every other cross-entity link already in the platform and its
  stated database-level-integrity requirement.
- Q: Should read access to `compliance_status`/`evidence_ref` be sensitivity-gated the way application
  risk/cost/governance data already is, or is general platform read access sufficient? → A: A mapping's
  visibility inherits the target entity's own existing read gate — an Application-targeted mapping requires
  `READ_APPLICATION_GOVERNANCE` (the same gate already protecting that Application's other governance data);
  Capability-, Design-, Pattern-, and estate-wide-targeted mappings stay under general platform read access,
  matching those entities' own existing (ungated) read posture.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: a mapping's `compliance_status` becomes a typed,
  queryable fact rather than something asserted informally in a document or spreadsheet; COMPLY-03's future
  aggregate status and COMPLY-04's future rollups will be derived views over these rows, never a separately
  hand-maintained number.
- **ART-XI** — Traceability End to End: this is the traceability link itself — the mechanism by which a
  Control (COMPLY-01) becomes attributable to the Capability, Application, Design, Pattern, or the
  estate-wide scope that it actually governs, mirroring the existing capability↔design and
  objective↔capability link shape.
- **ART-XIII** — Typed Contracts Everywhere: `compliance_status` is a closed, named-CHECK-constrained
  enumeration, not a freeform string; `evidence_ref` is an explicit (if loosely-typed) pointer field, not an
  attachment blob.
- **ART-XV** — Schema Evolution is Governed: this spec introduces five new join-shaped tables to the
  canonical model, following the platform's existing migration-owns-constraints discipline.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: Compliance posture data — which Capabilities, Applications, Designs, Patterns, or
estate-wide obligations are (or are not) compliant with a given regulatory control, and the evidence backing
that assessment. This is materially more sensitive than COMPLY-01's catalog: it discloses where the
organization's actual regulatory gaps are, not just which frameworks it tracks.

**Trust boundaries crossed**: Browser → API, through the platform's existing OIDC-authenticated session — no
new trust boundary is introduced.

**Abuse cases**:
- An unauthorized actor creates, edits, or deletes mapping rows to falsely claim compliance (or falsely
  accuse an entity of non-compliance) → mitigated by gating all writes behind the same dedicated
  `WRITE_COMPLIANCE` permission established in COMPLY-01, held only by the three architect personas.
- A user without the right to see an Application's sensitive governance data infers its compliance gaps
  indirectly through this spec's mapping reads, bypassing that Application's own existing sensitivity gate
  → mitigated by tying an Application-targeted mapping's visibility to `READ_APPLICATION_GOVERNANCE`
  (Clarification Session 2026-08-18) rather than exposing it under a separate, weaker Compliance-only read
  check.
- A user deletes a `Control` or a mapped target entity and its mapping history disappears silently, erasing
  the audit trail of what was once assessed → accepted for this pass via `ON DELETE CASCADE` on both FK
  legs (mirroring every existing join table in the platform); see Residual risk.

**Residual risk**: Deleting a `Control`, a `RegulatoryFramework`, or a mapped target entity cascades and
permanently removes any mapping rows referencing it, including their `compliance_status` history — there is
no soft-delete or point-in-time snapshot in this pass. Accepted because: (a) this matches every existing
join table's cascade behavior in the platform (capability↔design, objective↔capability, etc.), so it is not
a new risk class; (b) the write gate already restricts who can trigger such a deletion to the same small set
of architect personas trusted with the underlying registry. Revisit if audit/evidentiary requirements later
demand a retained history independent of the live mapping row.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Map a control to the entity it governs (Priority: P1)

An architect or compliance owner, having identified that a specific Control (e.g. GDPR Art. 32, "security
of processing") is best evidenced against a particular Application, links the two together and records the
current assessment: whether that Application is compliant, partially compliant, non-compliant, not yet
assessed, or not applicable, along with a pointer to supporting evidence and who assessed it.

**Why this priority**: Without this, the Control registry (COMPLY-01) and the rest of the platform's
typed model remain two disconnected worlds — compliance work has nothing to attach to. This is the single
capability the rest of the Compliance Domain bundle (COMPLY-03 status aggregation, COMPLY-04 rollups,
COMPLY-05 strategy linkage) depends on existing first.

**Independent Test**: Can be fully tested by mapping a Control to an Application with a `compliant` status
and an evidence pointer, then confirming that mapping is retrievable both from the Control's side ("which
entities does this control govern") and the Application's side ("which controls apply to this Application")
— delivers value on its own as a queryable compliance record, even before any aggregation or rollup exists.

**Acceptance Scenarios**:

1. **Given** an existing Control and an existing Application, **When** an authorized user maps the Control
   to the Application with a `compliant` status and an evidence reference, **Then** the mapping is saved and
   appears when either the Control's mapped entities or the Application's mapped controls are viewed.
2. **Given** an existing Control and Capability, **When** an authorized user maps them with a
   `not_assessed` status and no evidence reference yet, **Then** the mapping is accepted — evidence is not
   required to record a mapping.
3. **Given** a Control that governs a standing, estate-wide obligation with no single natural target entity
   (e.g. GDPR Art. 30, records of processing activities), **When** an authorized user records that
   assessment for the Control without pointing it at any single Capability/Application/Design/Pattern,
   **Then** the mapping is accepted and shown as an estate-wide assessment, not misattributed to any single
   entity.
4. **Given** a Control already mapped to a specific Application, **When** the same Control is mapped to a
   *different* Application as well, **Then** both mappings exist independently, each with its own status —
   mapping the same Control to a second entity does not overwrite or affect the first.

---

### User Story 2 - Update a mapping's assessment over time (Priority: P2)

An architect or compliance owner revisits a previously recorded mapping — for example, after remediation
work closes a gap, or a periodic audit finds new evidence — and updates its compliance status, evidence
reference, and who assessed it, reflecting the current state without losing the fact that a mapping exists.

**Why this priority**: Compliance status changes over time as remediation happens and audits recur; a
mapping that can only ever be created once, never revisited, would misrepresent reality almost immediately.
This is the second most valuable slice because it's what keeps User Story 1's records trustworthy on an
ongoing basis.

**Independent Test**: Can be fully tested by creating a mapping with `non_compliant` status, then updating
it to `compliant` with a new evidence reference and assessor, and confirming the mapping reflects only the
latest assessment — delivers value as an up-to-date compliance record independent of any other story.

**Acceptance Scenarios**:

1. **Given** an existing mapping with a `non_compliant` status, **When** an authorized user updates it to
   `compliant` with a new evidence reference and assessment date, **Then** the mapping reflects the new
   status and evidence — the prior status is not separately preserved as its own record in this pass.
2. **Given** an existing mapping, **When** an authorized user changes only its `evidence_ref` without
   changing `compliance_status`, **Then** the status is unaffected and only the evidence pointer updates.

---

### User Story 3 - Trace compliance coverage from either direction (Priority: P3)

Anyone with appropriate read access — reviewing a Capability, Application, Design, or Pattern — can see
every Control mapped to it and each one's current status, and, working the other direction, anyone
reviewing a Control can see every entity (and the estate-wide scope, if applicable) it has been mapped
against and each one's status.

**Why this priority**: This read-side traceability is what makes User Stories 1–2's records useful day to
day — without it, mappings exist but nobody can conveniently answer "is this Application compliant with
what it needs to be" or "what has this Control actually been assessed against." Lower priority than
creating/updating the data itself, since the data has to exist first.

**Independent Test**: Can be fully tested by mapping several Controls to one Application (with varying
statuses) and confirming that Application's full set of mapped Controls and statuses is retrievable in one
view, and separately confirming one of those Controls' full set of mapped entities is retrievable from the
Control's own side — delivers value as bidirectional traceability independent of any aggregation logic.

**Acceptance Scenarios**:

1. **Given** an Application with three mapped Controls at different statuses, **When** an authorized user
   views that Application's compliance mappings, **Then** all three Controls and their individual statuses
   are shown together.
2. **Given** a Control mapped to a Capability, an Application, and the estate-wide scope, **When** an
   authorized user views that Control's mappings, **Then** all three are shown, each labeled with its
   target type and individual status.
3. **Given** a user who lacks `READ_APPLICATION_GOVERNANCE`, **When** they view a Control's mappings or an
   Application's mappings, **Then** any mapping targeting that (or any other) Application is withheld from
   them, while mappings targeting Capabilities, Designs, Patterns, or the estate-wide scope remain visible.

---

### Edge Cases

- What happens when a user attempts to map the same Control to the same target a second time? The system
  MUST treat this as updating the existing mapping (its status/evidence/assessment fields), not as creating
  a duplicate row.
- What happens when the Control being mapped, or its target entity, is deleted? The mapping MUST be removed
  along with it (cascading delete) — a mapping cannot outlive either side of what it connects.
- What happens when a mapping is recorded with a `not_applicable` status? This MUST be accepted as a
  distinct, valid status — it signals "this control does not apply to this entity" as a deliberate
  assessment, not "not yet looked at" (`not_assessed`).
- What happens when a user provides `assessed_by` or `assessed_at` without a status change, or a status
  change without either? Both MUST be accepted independently — none of `compliance_status`, `evidence_ref`,
  `assessed_at`, `assessed_by` require each other to be set.
- How does the system handle a Control that has no mappings at all yet? It MUST be a normal, valid state —
  an unmapped Control is simply not yet assessed against anything, not an error condition.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an authorized user to create a mapping linking an existing `Control` to an
  existing `Capability`, `Application`, `Design`, or `Pattern` (a knowledge base item of kind `pattern`).
- **FR-002**: System MUST allow an authorized user to record an assessment for a Control that represents a
  standing, estate-wide obligation, without requiring it to be pointed at any single
  Capability/Application/Design/Pattern (Clarification Session 2026-08-18).
- **FR-003**: System MUST model each of the four entity-targeted mapping shapes (Control↔Capability,
  Control↔Application, Control↔Design, Control↔Pattern) as its own dedicated mapping table with a full
  database-level foreign key on both legs — not as a single polymorphic table — consistent with every other
  cross-entity link already in the platform (Clarification Session 2026-08-18).
- **FR-004**: System MUST record, for every mapping regardless of target type, a `compliance_status` limited
  to exactly one of: `compliant`, `partial`, `non_compliant`, `not_assessed`, `not_applicable`.
- **FR-005**: System MUST allow every mapping to optionally carry an `evidence_ref` (a pointer to supporting
  evidence — a document URL, an audit finding identifier, or a design annotation), an `assessed_at` date,
  and an `assessed_by` actor reference — none of these fields MUST be required to create a mapping.
- **FR-006**: System MUST record when each mapping was created.
- **FR-007**: System MUST allow the same Control to be mapped to multiple distinct targets simultaneously,
  each with its own independent `compliance_status`, `evidence_ref`, `assessed_at`, and `assessed_by` —
  updating one mapping MUST NOT affect any other mapping of the same Control.
- **FR-008**: System MUST treat a mapping's (Control, target) pair as unique — attempting to map an
  already-mapped (Control, target) pair again MUST update the existing mapping's fields rather than create
  a second, conflicting record.
- **FR-009**: System MUST remove a mapping automatically when either the Control it references or the
  target entity it references is deleted; no mapping MUST be left referencing a Control or target entity
  that no longer exists.
- **FR-010**: System MUST allow an authorized user to update an existing mapping's `compliance_status`,
  `evidence_ref`, `assessed_at`, and `assessed_by`, independently of one another, without requiring the
  mapping to be deleted and recreated.
- **FR-011**: System MUST allow an authorized user to view, given a Control, every target it is mapped to
  and each one's current `compliance_status`.
- **FR-012**: System MUST allow an authorized user to view, given a Capability, Application, Design, or
  Pattern, every Control mapped to it and each one's current `compliance_status`.
- **FR-013**: System MUST restrict creating, updating, and deleting mappings to the same `WRITE_COMPLIANCE`
  permission established for the Framework & Control Registry (COMPLY-01), held by the Enterprise Architect,
  Solution Architect, and Technical Architect personas.
- **FR-014**: System MUST gate read access to a mapping according to its target's own existing sensitivity
  posture: a mapping targeting an Application MUST require the same `READ_APPLICATION_GOVERNANCE` permission
  that already gates that Application's other governance-flavored data; a mapping targeting a Capability,
  Design, Pattern, or the estate-wide scope MUST be visible under the platform's general authenticated read
  access, matching those entities' own existing (ungated) read posture (Clarification Session 2026-08-18).
- **FR-015**: System MUST NOT provide any approval or proposal workflow for changing `compliance_status` in
  this pass — a status update is a direct field change made by an authorized user, not a proposal requiring
  separate confirmation.

### Key Entities *(include if feature involves data)*

- **Control Mapping**: A record asserting that a specific `Control` (COMPLY-01) governs, and has been
  assessed against, a specific target — a `Capability`, `Application`, `Design`, a `Pattern` (knowledge base
  item), or a standing estate-wide obligation with no single owning entity. Carries a `compliance_status`
  (one of five fixed values), an optional evidence pointer, and optional assessment metadata (when and by
  whom). Implemented as five parallel mapping shapes (one per entity target type, plus one estate-wide shape
  with no target leg) rather than one polymorphic table, so every entity-target relationship stays enforced
  at the database level (Clarification Session 2026-08-18). The same Control may have any number of
  independent mappings, one per distinct target, each tracking its own status; an entity-targeted mapping
  ceases to exist if either the Control or its target entity is deleted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An authorized user can map a Control to a Capability, Application, Design, Pattern, or the
  estate-wide scope, with a status and evidence reference, in under 30 seconds.
- **SC-002**: 100% of mappings created against a deleted Control or a deleted target entity are removed
  automatically — zero orphaned mapping rows are ever left referencing a nonexistent Control or target.
- **SC-003**: A user reviewing any Capability, Application, Design, or Pattern can retrieve its full set of
  mapped Controls and their statuses in a single view, with zero manual cross-referencing against a separate
  spreadsheet or document.
- **SC-004**: A user reviewing any Control can retrieve its full set of mapped targets and their statuses in
  a single view.
- **SC-005**: Attempting to map an already-mapped (Control, target) pair a second time always results in
  exactly one mapping for that pair reflecting the latest values — zero duplicate mapping rows are ever
  created for the same (Control, target) pair.
- **SC-006**: A user lacking `READ_APPLICATION_GOVERNANCE` never sees an Application-targeted mapping, while
  still being able to see mappings targeting Capabilities, Designs, Patterns, or the estate-wide scope —
  zero cases of sensitive mapping data leaking past that gate.

## Assumptions

- **A mapping never requires a proposal/confirmation workflow to change `compliance_status` in this pass.**
  Whether it should route through the platform's AI-proposes/human-confirms gate is left an open question
  for a later pass per the source material; this spec treats a status change as a direct write by an
  authorized user.
- **No file/attachment storage is provided for evidence.** `evidence_ref` is a loosely-typed pointer (a URL,
  an identifier, or free text describing where evidence lives) — validating or resolving that reference is
  out of scope.
- **The same Control can carry different statuses against different targets simultaneously** (e.g.
  `compliant` at one Application, `not_assessed` at another) — each mapping row is independent by design;
  this is treated as an intended semantic, not an edge case to reconcile.
- **A `Pattern` target refers to a knowledge base item of kind `pattern`** — the existing `KnowledgeType.PATTERN`
  entries already present in the platform's knowledge base — not a new entity type introduced by this spec.
- **No weighting, severity, or aggregation logic is introduced here.** Deriving a single rolled-up status
  per entity from its individual mappings (COMPLY-03) and any dashboard-level rollup (COMPLY-04) are
  explicitly out of scope for this spec, which covers only the mapping records themselves.
- **This spec does not itself create any link from a mapping to a Strategy `Objective` or `Initiative`.**
  That is COMPLY-05's responsibility, which depends on this spec's Control Mapping records (per the source
  material's note that `InitiativeControlMapping` targets a mapping row, not a bare `Control`) but is not
  built here.
