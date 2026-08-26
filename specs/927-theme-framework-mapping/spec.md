
# Feature Specification: Theme–Framework Mapping

**Feature Branch**: `927-theme-framework-mapping`
**Created**: 2026-08-26
**Status**: Draft
**Input**: User description: "docs/speckit-compliance-bundle_1.md's COMPLY-05 section" — scoped to the
third, deferred link named there (`ThemeFrameworkMapping`), tracked as bead ADP-1ox. COMPLY-01 through
COMPLY-04 (Framework & Control Registry, Control Mappings, Derived Compliance Status, Rollup Reporting)
and COMPLY-05's other two links (`ObjectiveControlMapping`, `InitiativeControlMapping`, both built in
`specs/925-strategy-compliance-linkage/`) are already implemented and are prerequisites for this spec.

## Clarifications

### Session 2026-08-26

- Q: Should this pass include UI surfacing (a tag editor plus reverse-lookup display on the existing
  Theme and Framework screens), or ship as a data-model-and-API-only addition, with UI as an explicit
  follow-on? → A: Data-model-and-API-only. Matches this link's own "coarse, lower-priority, optional"
  framing and the precedent set by `926-framework-versioning-correction` (COMPLY-01a) for a similarly
  narrow addition. UI surfacing (a tag editor on the Theme screen, reverse-lookup display on
  `FrameworkDetail.tsx`) is filed as an explicit follow-on bead rather than left to informal memory.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — The Model is the Single Source of Truth: "which regulatory areas does this strategic
  theme touch" becomes a typed, queryable fact instead of something inferred from theme names or kept
  in a side spreadsheet for portfolio reporting.
- **ART-XI** — Traceability End to End: a traceability link in the literal sense, connecting the
  Strategy domain's `StrategicTheme` to the Compliance domain's `RegulatoryFramework`, following the
  exact composite-PK / `ON DELETE CASCADE` join-table shape already established by
  `objective_control_links` and the platform's other reusable-tag links.
- **ART-XIII** — Typed Contracts Everywhere: the link is a typed Pydantic model (`extra="forbid"`),
  not a freeform note or naming convention on either side.
- **ART-XV** — Schema Evolution is Governed: introduces one new join table to the canonical model via
  a governed migration, following the platform's existing migration-owns-constraints discipline.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: which broad strategic themes an organization associates with which regulatory
frameworks. This is deliberately coarser and less sensitive than the two sibling links already built
in `925-strategy-compliance-linkage` — it says nothing about a specific compliance gap, a specific
remediation effort, or how urgently anything is being worked; it is a portfolio-level grouping tag,
not a status or a work record.

**Trust boundaries crossed**: Browser → API, through the platform's existing OIDC-authenticated
session — no new trust boundary is introduced.

**Abuse cases**:
- An unauthorized actor creates or removes a tag to misrepresent how compliance-focused a strategic
  theme is, for audit-narrative or reporting purposes → mitigated by gating all writes behind the same
  permission that already gates the sibling links and Strategy/Compliance writes generally — no new,
  weaker write path is introduced.
- A `StrategicTheme` or `RegulatoryFramework` is deleted while tags reference it, orphaning rows or
  leaving a dangling reference → mitigated by cascading the delete to dependent link rows (disclosed to
  the user performing the delete), consistent with the platform's existing cascade-with-disclosure
  convention.

**Residual risk**: as with the sibling links, there is no independent verification workflow — a holder
of write access can tag a theme against a framework that isn't genuinely relevant. This is the same
class of trust already accepted for every other reusable-tag relationship on the platform (e.g. a
Theme tagged onto an Objective) and this feature does not change that posture.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tag a strategic theme against the regulatory frameworks it touches (Priority: P1)

An architect or compliance owner reviewing a Strategic Theme (e.g. "Regulatory & Compliance," or a
narrower theme like "Data Privacy") tags it against one or more Regulatory Frameworks it relates to
(e.g. GDPR, an internal SOC 2 program), so the association is captured as data rather than living only
in the theme's name or in someone's head.

**Why this priority**: without the ability to create the tag at all, there is nothing to report on —
this is the foundational capability the rest of the feature's value depends on.

**Independent Test**: can be fully tested by tagging an existing Theme against an existing Framework via
the API and confirming the link is persisted and returned by a subsequent read — delivers the core
"capture the association" value on its own, independent of any reverse-lookup or removal capability.

**Acceptance Scenarios**:

1. **Given** an existing Strategic Theme and an existing Regulatory Framework with no tag between them,
   **When** an authorized user tags the Theme against the Framework, **Then** the tag is created and a
   subsequent read of either side reflects the association.
2. **Given** a Strategic Theme already tagged against a Regulatory Framework, **When** an authorized
   user attempts to tag the same pair again, **Then** the request is rejected as a duplicate and the
   existing tag is left unchanged.
3. **Given** a Theme or Framework id that does not exist, **When** an authorized user attempts to create
   a tag referencing it, **Then** the request is rejected and no tag is created.

---

### User Story 2 - See which frameworks a theme touches, and which themes a framework carries (Priority: P1)

A portfolio reviewer, looking at a Strategic Theme, sees every Regulatory Framework it has been tagged
against; looking at a Regulatory Framework, they see every Strategic Theme tagged onto it. This is the
"coarse portfolio rollup" this link exists to enable — without both read directions, the tag captured in
User Story 1 has no reporting value.

**Why this priority**: this is the actual point of the feature, per its own stated purpose — a tag that
can be created but never read back delivers no portfolio-reporting value at all, so this ships alongside
User Story 1 as the real MVP, not as a later enhancement.

**Independent Test**: can be fully tested by creating tags via the API (or fixtures) and then reading
both a Theme's linked frameworks and a Framework's linked themes independently of any UI.

**Acceptance Scenarios**:

1. **Given** a Strategic Theme tagged against two Regulatory Frameworks, **When** its linked frameworks
   are listed, **Then** both frameworks appear.
2. **Given** a Regulatory Framework tagged by three Strategic Themes, **When** its linked themes are
   listed, **Then** all three themes appear.
3. **Given** a Strategic Theme or Regulatory Framework with no tags at all, **When** its linked
   counterparts are listed, **Then** an empty result is returned, not an error.

---

### User Story 3 - Remove a tag that no longer applies (Priority: P2)

An architect removes a Theme–Framework tag that was created in error or is no longer relevant (e.g. a
theme's focus shifted away from a particular regulatory area), without affecting the Theme or Framework
themselves.

**Why this priority**: correcting a mistaken or stale tag matters for keeping the coarse rollup
trustworthy, but the feature is still useful without it in the short term (a wrong tag is a data-quality
issue, not a blocker to the read-side value delivered by User Story 2).

**Independent Test**: can be fully tested by removing an existing tag via the API and confirming it no
longer appears from either the Theme's or the Framework's side, while both the Theme and Framework
themselves remain intact.

**Acceptance Scenarios**:

1. **Given** an existing tag between a Theme and a Framework, **When** an authorized user removes it,
   **Then** the tag is gone from both directions immediately, and the Theme and Framework both remain
   otherwise unchanged.
2. **Given** no tag exists between a given Theme and Framework, **When** an authorized user attempts to
   remove one, **Then** the request is rejected as not found.

---

### Edge Cases

- What happens when a Strategic Theme with active tags is deleted? The tags referencing it are removed
  along with it (cascade), not left dangling and not blocking the theme's deletion.
- What happens when a Regulatory Framework with active tags is deleted? Same cascade behavior, from the
  framework side.
- What happens when a user without write access to Strategy or Compliance data attempts to create or
  remove a tag? The request is rejected before any tag is created or removed.
- What happens when a user without read access to a specific Regulatory Framework's data (if such a
  restriction applies) looks up the frameworks tagged onto a Theme? Frameworks that user cannot otherwise
  see are excluded from the result, consistent with how similar reverse lookups elsewhere on the platform
  already filter by the caller's read access rather than exposing data through a lesser-gated shortcut.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an authorized user to tag an existing Strategic Theme against an
  existing Regulatory Framework.
- **FR-002**: System MUST reject an attempt to tag a Theme and Framework pair that is already tagged,
  leaving the existing tag unchanged.
- **FR-003**: System MUST reject an attempt to create a tag referencing a Strategic Theme or Regulatory
  Framework that does not exist.
- **FR-004**: System MUST allow any user permitted to read Strategic Themes to list every Regulatory
  Framework tagged onto a given Theme.
- **FR-005**: System MUST allow any user permitted to read Regulatory Frameworks to list every Strategic
  Theme tagged onto a given Framework.
- **FR-006**: System MUST support a single Strategic Theme being tagged against any number of Regulatory
  Frameworks, and a single Regulatory Framework being tagged by any number of Strategic Themes.
- **FR-007**: System MUST allow an authorized user to remove an existing Theme–Framework tag without
  affecting the Theme or Framework it referenced.
- **FR-008**: System MUST reject an attempt to remove a tag that does not exist.
- **FR-009**: System MUST remove all tags referencing a Strategic Theme or Regulatory Framework when
  that Theme or Framework is deleted, rather than leaving orphaned tags behind.
- **FR-010**: System MUST gate creating and removing tags behind the same write permission that already
  gates other Strategy and Compliance domain writes — this feature MUST NOT introduce a new, separately
  gated write path.
- **FR-011**: This pass MUST NOT require any user interface change — the tag editor and reverse-lookup
  display on the existing Theme and Framework screens are explicit follow-on work (tracked as a bead,
  not this spec's scope), matching the "data-model-and-API-only" precedent set by
  `926-framework-versioning-correction`. FR-001 through FR-009 are satisfied entirely at the API layer
  for this pass.

### Key Entities *(include if feature involves data)*

- **Theme–Framework Mapping**: the tag itself — a link between one Strategic Theme and one Regulatory
  Framework, with no fields of its own beyond the two references and when it was created. Carries no
  status, evidence, or assessment data — unlike `ControlMapping` (COMPLY-02), this is a coarse grouping
  tag, not an assessed relationship.
- **Strategic Theme** *(existing entity, referenced by this feature)*: a reusable, short strategic label
  (e.g. "Regulatory & Compliance") already usable across Strategic Objectives; this feature adds
  Regulatory Frameworks as a second thing a Theme can be reused against.
- **Regulatory Framework** *(existing entity, referenced by this feature)*: a named regulatory or
  compliance framework (e.g. GDPR, SOC 2 Type II) that an organization's estate is assessed against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can tag a Strategic Theme against a Regulatory Framework, and immediately
  confirm the tag from either the Theme's or the Framework's own perspective, in a single sitting with
  no indirection through another document or tracker.
- **SC-002**: A portfolio reviewer can determine, for any Regulatory Framework, every Strategic Theme it
  has been associated with (and the reverse, for any Theme) using only data already in ADP.
- **SC-003**: Removing a tag takes effect immediately in both read directions, with no stale or cached
  result surviving the removal.
- **SC-004**: Deleting a Strategic Theme or Regulatory Framework that carries existing tags leaves zero
  orphaned tag rows afterward.

## Assumptions

- This feature reuses the existing composite-key, cascade-delete join-table shape already established
  by `objective_control_links` (COMPLY-05) and the platform's other reusable-tag relationships (e.g. a
  Theme tagged onto an Objective) — no new linking paradigm is introduced.
- This feature reuses whichever write permission already gates Strategy and Compliance domain writes
  today; no new permission or action type is introduced, since a coarse theme/framework tag is no more
  sensitive than either side's own already-writable data.
- The relationship is genuinely many-to-many in both directions: a Theme may reasonably relate to
  several Frameworks (e.g. a "Data Privacy" theme touching both GDPR and a sector-specific privacy
  regulation), and a Framework may reasonably be tagged by several Themes.
- This pass delivers the tag itself (create, list both directions, remove) and does not introduce a new
  dedicated reporting or rollup endpoint (e.g. "compliance coverage by theme") — the source bundle's own
  scope for this link is limited to the link, and a dedicated rollup view is a natural, separate
  follow-on once a concrete reporting need is confirmed against real usage of this link, mirroring how
  the platform's existing rollup reporting was itself a distinct follow-on spec built after its
  underlying links already existed.
- No bulk-tagging or bulk-import capability is in scope — tags are created and removed one pair at a
  time, matching the "coarse, optional, lower-priority" framing this link was given in its source bundle.
- This pass is data-model-and-API-only (Clarifications, 2026-08-26) — no existing screen is modified.
  UI surfacing (a tag editor on the Theme screen, reverse-lookup display on the Framework screen) is
  filed as a separate follow-on bead, not built here.
