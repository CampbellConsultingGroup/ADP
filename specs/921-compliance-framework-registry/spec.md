# Feature Specification: Compliance Framework & Control Registry

**Feature Branch**: `921-compliance-framework-registry`
**Created**: 2026-08-17
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md for COMPLY_01 only" — scoped strictly to
COMPLY-01 (Framework & Control Registry) of the five-spec Compliance Domain bundle. COMPLY-02 (control
mappings/traceability), COMPLY-03 (derived compliance status), COMPLY-04 (rollup reporting), and COMPLY-05
(Strategy linkage) are explicitly out of scope for this spec and will be specified separately once this
registry exists for them to build on.

## Clarifications

### Session 2026-08-17

- Q: Who is authorized to write to this registry (create/edit/delete frameworks and controls)? → A: New
  dedicated permission (`ActionType.WRITE_COMPLIANCE`), granted to the three architect roles
  (Enterprise/Solution/Technical) — same shape as `WRITE_APPLICATION`, treating Compliance as its own
  top-level domain rather than folding it under Business Architecture's existing `WRITE_BUSINESS_ARCH`.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: `RegulatoryFramework` and `Control` become part of
  the canonical typed model; any future rollup, report, or link (COMPLY-02–05) is derived from these
  records, never hand-maintained separately.
- **ART-III** — Everything is Machine-Readable: both entities are typed records with a published schema,
  not free text — consistent with ADP's existing distinction between "content you look up"
  (knowledge base) and "content you formally reference" (typed registries like Business Capabilities).
- **ART-XI** — Traceability End to End: this spec does not itself create any cross-entity link, but it
  establishes the stable, referenceable identities (`Framework.id`, `Control.id`) that COMPLY-02's mapping
  links will target — the registry is the traceability graph's foundation, not yet the graph itself.
- **ART-XIII** — Typed Contracts Everywhere: both entities are defined as typed records with explicit,
  validated fields (no freeform blobs) from the outset.
- **ART-XV** — Schema Evolution is Governed: this spec introduces two new entity types to the canonical
  model; their addition follows the platform's existing schema-versioning discipline.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: The organization's regulatory framework and control catalog — which regulations and
control taxonomies the organization tracks (e.g. "we track GDPR and SOC 2"), and how granularly. This is
lower sensitivity than compliance *status* or *evidence* (those belong to COMPLY-02, out of scope here),
but the catalog's existence and shape can still hint at an organization's regulatory exposure and audit
scope.

**Trust boundaries crossed**: Browser → API, through the platform's existing OIDC-authenticated session —
no new trust boundary is introduced.

**Abuse cases**:
- An unauthorized actor tampers with the control catalog (adds, edits, or deletes frameworks/controls) to
  obscure or misrepresent what the organization is tracked against → mitigated by gating all writes behind
  a dedicated Compliance-write permission held only by the three architect personas (Clarification Session
  2026-08-17, Q1), the same enforcement mechanism used for every other registry domain.
- A user casually deletes a `RegulatoryFramework` that has many `Control` children, destroying a large
  catalog in one action → mitigated by requiring the deletion to cascade transparently (the user is
  informed of scope) rather than silently orphaning children; treated as a deliberate, attributable action
  rather than a soft-delete/undo flow in this pass (see Residual risk).

**Residual risk**: This pass has no soft-delete or version history for `RegulatoryFramework`/`Control` — an
accidental deletion of a large control tree is not recoverable except by re-entry. Accepted at this risk
level because: (a) this is reference/catalog data typically entered and reviewed deliberately, not a
high-frequency write path; (b) the higher-sensitivity data this registry will eventually support —
compliance status and evidence — is explicitly out of scope for COMPLY-01 and does not exist yet for
anything to be lost. Revisit if usage patterns show frequent destructive edits.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register a regulatory framework (Priority: P1)

An architect or compliance owner needs to start tracking a regulatory or industry framework the
organization must comply with (e.g. "NIST 800-53 Rev 5", "GDPR", "SOC 2 Type II") before any control
mapping or reporting work can happen. They record the framework's identity, jurisdiction, issuing
authority, version, and (if known) its effective date and a link to the source document.

**Why this priority**: Nothing else in the compliance domain — control entry, mappings, status rollups —
can exist without a framework to hang it on. This is the entry point for the entire bundle.

**Independent Test**: Can be fully tested by creating a framework record with its identifying fields and
confirming it appears, correctly, in a list of tracked frameworks — delivers value on its own as a simple
system-of-record for "which frameworks are we tracking," even before any controls are entered.

**Acceptance Scenarios**:

1. **Given** no frameworks exist yet, **When** an authorized user registers a new framework with a name,
   jurisdiction, authority, and version, **Then** the framework appears in the list of tracked frameworks
   with those details.
2. **Given** a framework whose effective date isn't meaningful (a perpetually-current framework), **When**
   the user registers it without an effective date, **Then** the framework is accepted and shown without
   one — this is not an error.
3. **Given** an existing framework, **When** an authorized user edits its authority or source link,
   **Then** the updated values are reflected immediately without affecting any controls already recorded
   under it.

---

### User Story 2 - Build out a framework's control catalog (Priority: P2)

Once a framework is registered, an architect or compliance owner enters its individual controls (e.g. NIST
`AC-2`, GDPR `Art. 17`), each with a short code, a title, and a description — and, where the framework
groups controls into families or nested sub-clauses, organizes them into a parent/child hierarchy (e.g.
NIST family `AC` containing control `AC-2`; GDPR `Art. 5` containing sub-points `Art. 5(1)(a)` through
`Art. 5(1)(f)`).

**Why this priority**: The framework record alone has no operational value — the control catalog is what
later specs (mappings, status, rollups) actually reference. This is the second most valuable slice because
it can be built and demonstrated independently of everything downstream.

**Independent Test**: Can be fully tested by adding a mix of top-level and nested controls under an
existing framework and confirming each appears with the correct code, title, description, and position
in the hierarchy — delivers value as a queryable control catalog even before any entity is mapped against
it.

**Acceptance Scenarios**:

1. **Given** a registered framework with no controls yet, **When** an authorized user adds a top-level
   control with a code, title, and description, **Then** the control appears under that framework.
2. **Given** a control already exists under a framework, **When** the user adds a second control as its
   child (e.g. a sub-clause), **Then** the child control is shown nested under its parent, and the parent
   still shows correctly at its own level.
3. **Given** two different frameworks each have a control coded `AC-2`, **When** both are entered,
   **Then** both are accepted — control codes are unique within a framework, not across frameworks.
4. **Given** a framework already has a control coded `AC-2`, **When** a user attempts to add a second
   control coded `AC-2` under the *same* framework, **Then** the system rejects it with a clear message
   that the code is already in use for that framework.
5. **Given** several sibling controls under the same parent (or at a framework's top level), **When**
   the user assigns them an explicit display order, **Then** they consistently display in that order
   wherever the catalog is shown.

---

### User Story 3 - Browse and maintain the control catalog (Priority: P3)

An architect or compliance owner, or anyone reviewing what the organization tracks, browses a framework's
full control hierarchy to understand its shape, and edits or removes controls and frameworks as the
organization's catalog evolves (a framework is retired, a control's wording is corrected, a control is
split into finer-grained children).

**Why this priority**: Read/maintenance access rounds out the registry into something usable day-to-day,
but the catalog already has value from User Stories 1–2 alone; this story is about longevity and usability
rather than unlocking new capability.

**Independent Test**: Can be fully tested by browsing an existing framework's control tree end-to-end,
editing a control's title, and deleting a leaf control, then confirming the catalog reflects each change
correctly — delivers value as ongoing catalog upkeep independent of any other story.

**Acceptance Scenarios**:

1. **Given** a framework with a multi-level control hierarchy, **When** a user views the framework,
   **Then** they see its full control tree in the correct parent/child structure and display order.
2. **Given** an existing control, **When** an authorized user edits its title or description, **Then**
   the change is reflected immediately and does not alter its code, position, or hierarchy.
3. **Given** a control that has child controls beneath it, **When** an authorized user deletes it,
   **Then** its children are removed along with it, and the user is shown the scope of what will be
   removed before the deletion is confirmed.
4. **Given** a framework that has controls under it, **When** an authorized user deletes the framework,
   **Then** all of its controls (at every level) are removed along with it, and the user is shown the
   scope of what will be removed before the deletion is confirmed.

---

### Edge Cases

- What happens when a user tries to set a control's parent to itself, or to one of its own descendants
  (a cycle)? The system MUST reject this — a control cannot be its own ancestor.
- What happens when a user tries to set a control's parent to a control that belongs to a *different*
  framework? The system MUST reject this — a control's parent must belong to the same framework.
- What happens when two frameworks are entered with the same name (e.g. "GDPR" tracked at two different
  versions)? This MUST be allowed — `name` is not required to be unique; `version` is what distinguishes
  otherwise-identically-named framework revisions.
- What happens when a control is entered with no parent at all? It MUST be treated as a top-level control
  directly under its framework — this is the normal case, not an edge case requiring special handling.
- How does the system handle very deep control nesting (e.g. framework → family → control → sub-control →
  sub-sub-control)? The hierarchy MUST support this without a fixed depth limit — see Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an authorized user to register a new `RegulatoryFramework` with a name,
  jurisdiction, issuing authority, and version.
- **FR-002**: System MUST allow a `RegulatoryFramework`'s effective date and source reference link to be
  recorded optionally — a framework MUST be creatable without either.
- **FR-003**: System MUST allow an authorized user to view a list of all registered frameworks and the
  full detail of any single framework.
- **FR-004**: System MUST allow an authorized user to edit an existing framework's fields.
- **FR-005**: System MUST allow an authorized user to delete a framework; deleting a framework MUST also
  remove every control recorded under it (at every hierarchy level), and the user MUST be shown the scope
  of what will be removed before the deletion is confirmed.
- **FR-006**: System MUST allow an authorized user to add a `Control` under a framework, with a code, a
  title, and a description.
- **FR-007**: System MUST allow a control to be designated as a child of another control within the same
  framework, so that framework → family → control (and deeper) hierarchies can be represented; a control
  with no designated parent MUST be treated as top-level within its framework.
- **FR-008**: System MUST reject an attempt to set a control's parent to itself, to one of its own
  descendants, or to a control belonging to a different framework.
- **FR-009**: System MUST enforce that a control's code is unique within its own framework, and MUST
  reject an attempt to add a second control with a duplicate code under the same framework; the same code
  MUST be permitted to exist under a *different* framework.
- **FR-010**: System MUST allow an authorized user to set and change the display order of sibling controls
  (controls sharing the same parent, or the same top-level framework if no parent is set), and MUST
  consistently reflect that order everywhere the catalog is displayed.
- **FR-011**: System MUST allow an authorized user to view a framework's full control catalog as a
  hierarchy, reflecting each control's parent/child relationships and display order.
- **FR-012**: System MUST allow an authorized user to edit an existing control's title, description, or
  display order without altering its code or hierarchy position, unless the user explicitly changes those.
- **FR-013**: System MUST allow an authorized user to delete a control; deleting a control that has child
  controls MUST also remove those children (at every level beneath it), and the user MUST be shown the
  scope of what will be removed before the deletion is confirmed.
- **FR-014**: System MUST record when each framework and control was created and when it was last
  modified.
- **FR-015**: System MUST restrict creating, editing, and deleting frameworks and controls to a dedicated
  Compliance-write permission held by the Enterprise Architect, Solution Architect, and Technical Architect
  personas — mirroring the shape of the platform's existing `WRITE_APPLICATION` permission (its own
  dedicated action, not folded into Business Architecture's write permission), reflecting Compliance's
  status as its own top-level, cross-cutting domain (Clarification Session 2026-08-17, Q1).
- **FR-016**: System MUST allow every framework and control to be viewed by any authenticated user who has
  general read access to the platform's architecture data — this registry is reference/catalog data, not
  the sensitive compliance-status or evidence data that later specs (COMPLY-02 onward) will introduce.
- **FR-017**: System MUST expose each framework and control through a stable identifier suitable for other
  records to reference — this registry is the foundation later specs (COMPLY-02's control mappings) will
  link against, even though this spec creates no such link itself.

### Key Entities *(include if feature involves data)*

- **Regulatory Framework**: A named regulatory or industry framework the organization tracks compliance
  against (e.g. "NIST 800-53 Rev 5", "GDPR", "SOC 2 Type II"). Carries a jurisdiction, an issuing
  authority, a version (tracked independently of the name, since a framework can be revised without
  changing what it's called), an optional effective date (some frameworks are perpetually current, with
  no defined start), and an optional link to its authoritative source. Owns zero or more Controls.
- **Control**: A single, individually-trackable clause, requirement, or sub-requirement within a
  Regulatory Framework (e.g. NIST `AC-2`, GDPR `Art. 17`). Carries a code that is unique within its own
  framework (but not globally), a title, a description, and a display position among its siblings. A
  control may optionally nest under another control within the same framework, allowing frameworks to be
  represented at whatever granularity they actually use — some group many fine-grained sub-controls under
  one broad control, others stand alone as a single leaf requirement, and this can vary clause by clause
  within the same framework.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An authorized user can register a new regulatory framework, with all of its core details, in
  under one minute.
- **SC-002**: An authorized user can add a control — top-level or nested under an existing control — in
  under 30 seconds.
- **SC-003**: 100% of controls entered under a framework display in the correct hierarchical position and
  order relative to their framework and parent, with no ambiguity about where a control sits.
- **SC-004**: Attempting to enter a duplicate control code within the same framework is rejected 100% of
  the time, with a clear explanation of why.
- **SC-005**: A user unfamiliar with a specific framework's shape can browse a control catalog of 50+
  controls and locate any individual control's place in the hierarchy in under two minutes.
- **SC-006**: Deleting a framework or a control with descendants always shows the user the full scope of
  what will be removed before the deletion takes effect — zero cases of a user being surprised by
  additional records disappearing.

## Assumptions

- **Control nesting depth is not capped at a fixed number of levels.** The source material notes that
  granularity varies not just framework-to-framework but clause-to-clause within the same framework (e.g.
  GDPR Art. 5 plausibly wants six children, while Art. 33 stands alone as one leaf) — capping depth at a
  fixed number (the way the Business Capability hierarchy caps at three levels) would misrepresent real
  frameworks. This spec assumes unbounded nesting depth; if a real framework catalog later proves depth
  reliably settles at a knowable maximum, that can be revisited as a follow-on refinement, not a blocker
  here.
- **`RegulatoryFramework` does not carry a lifecycle status (active/superseded/draft) in this pass.** No
  evidence in the source material shows frameworks needing status tracking distinct from their
  `effective_date` field. If a real need emerges (e.g. explicitly marking a framework as superseded once a
  new revision is registered), that is a follow-on addition, not assumed necessary now.
- **General read access to this registry is not sensitivity-gated beyond the platform's baseline
  authenticated-read access.** The higher-sensitivity data this registry supports — compliance status and
  evidence — belongs to COMPLY-02 and is explicitly out of scope here; this spec's data is the equivalent
  of a framework/control reference catalog, comparable in sensitivity to the existing Business Capability
  registry.
- **No bulk import of any framework's canonical control set (e.g. NIST's full catalog) is provided in this
  pass.** Controls are entered one at a time by an authorized user. A bulk-import tool is explicitly
  out of scope per the source material and would be a separate, later feature.
- **No versioning or diffing between framework revisions is provided.** `version` is a flat, descriptive
  field on the framework record, not a linked history connecting one framework revision to its
  predecessor.
- **No control-to-control relationships (e.g. "supersedes", "overlaps with") are modeled in this pass** —
  only the parent/child hierarchy needed to represent nesting.
- **This spec creates no link between a Control and any other domain entity** (Capability, Application,
  Design, etc.) — that traceability is COMPLY-02's responsibility, which this registry exists to support
  but does not implement here.
