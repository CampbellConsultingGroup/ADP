# Feature Specification: Capability ↔ Org Unit Mappings — owners, performers and the footprint they reveal

**Feature Branch**: `941-capability-org-mappings`
**Created**: 2026-11-16
**Status**: Draft
**Bead**: ADP-55k.2 (spec 2 of 4 in epic ADP-55k; depends on 940, merged in PR #147)
**Input**: User description: "941 capability-org-mappings (ADP-55k.2)". The epic's notes hold the user's source notes and decisions.

## Background and Resolved Decisions

Spec 940 gave ADP a governed org-unit tree (enterprise → division → function) and a geography tree (global → region → country). This spec connects them to the single business capability model, so architects can answer three questions:
- **Who is accountable** for this capability?
- **Who actually does the work**, and where?
- **Where is the same work being done more than once**, and where is no one doing it at all?

The user's notes (2026-11-15, in ADP-55k) are firm on the shape. The capability model and the org model stay separate, and the *mapping* carries the relationship. A reorg then updates mappings, never capabilities.

| # | Decision |
|---|---|
| D5 (epic) | **Owner (accountable)**: at most **one** org unit per capability, set at **L2** (L1 also allowed, never L3). Ownership is **global**, with no per-region owner. A missing owner is a **warning, never a block**. |
| D5 (epic) | **Performer**: the org units that execute a capability, mapped at **L3** (the leaf), **many-to-many**. Each mapping may name **one geography** ("Stores performs Accept Payment *in Germany*"). The region travels on the performer, not on the owner. |
| D5 (epic) | **Contributor** (optional): units that depend on or feed an L3 capability. Recorded for completeness, and used by no finding. |
| N1 | **Findings and the footprint are derived on read, never stored** (the 937/938 convention). |

Ground-truth checks against the code (main at 8ae8f4b, migration head `048`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | Business capabilities have a fixed `level` 1–3 and a `parent_id`. Neither can be changed after creation; the update model has no parent or level field (`src/adp/business/models.py:121`) | A mapping's level rule, once satisfied, stays satisfied. There is no "capability moved" case |
| GT-2 | A business capability cannot be deleted while it has children (`src/adp/business/store.py:406`). A leaf L2, with no L3 under it, is allowed | Deleting a capability removes its mappings. A leaf L2 can have an owner but no performers (see Edge Cases) |
| GT-3 | Business capabilities have no owner or performer field of any kind today; `stakeholder` exists only on value streams | Everything here is new. Nothing has to be migrated |
| GT-4 | Org units (940) have a 3-level tree, a many-to-many link to geographies and an optional primary geography (`src/adp/organization/store.py`). Deleting an org unit with children is refused | Mappings point at org units and, optionally, geographies. Deleting an org unit or a geography removes or clears the mappings that use it |
| GT-5 | Writes under `/api/v1/business/` require `WRITE_BUSINESS_ARCH` (`src/adp/authz/enforcement.py:161`) | No new permission |
| GT-6 | The Business Architecture screen's Capabilities tab renders one row per capability (`web/src/business/CapabilityNode.tsx`); the Organization tab (940) has an org-unit detail panel (`web/src/business/OrganizationTab.tsx`) | Mappings are edited on the capability row. The org unit's footprint is shown in its detail panel |
| GT-7 | 938's analysis engine derives capability findings on read (`src/adp/application/cap_analysis.py`) and is guarded by a "not stored" test | The new findings follow the same pattern and get the same guard |

## Clarifications

### Session 2026-11-16

- Q: Are contributor mappings in scope? → A: Yes, on L3 capabilities only, with no geography and no effect on any finding.
- Q: Does a division's footprint include its child units' work? → A: Yes, always included, each entry attributed to the unit that performs it.
- Q: What if a performer's geography isn't one of the unit's "operates in" places? → A: Save it and show an informational note; never refuse, never auto-link.
- Q: Is an L3 performed by a division and by one of its own functions a shared-service candidate? → A: No. A unit and its descendants count as one performer; only work split across separate branches of the org tree is flagged.
- Q: Where do the findings appear? → A: On Business Architecture, each linked to its capability. Governance → Architecture Health tiles are a follow-on bead.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: capabilities and org units each stay in their own model; the mapping is the only place the relationship lives. Findings and footprints are computed from it, never copied.
- **ART-V** — Security by Design: writes use the existing `WRITE_BUSINESS_ARCH` gate. Mapping data isn't sensitive.
- **ART-IX** — Auditability: every mapping create, change and removal is logged with the actor.
- **ART-XIII** — Typed Contracts: the mapping role (owner / performer / contributor) is a closed set, and the level rules are enforced with a message naming the rule.
- **ART-XV** — Schema Evolution: one reversible migration (`049`).
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. Who owns and performs a business capability is ordinary architecture data, readable by every platform user like the rest of Business Architecture. Writes need `WRITE_BUSINESS_ARCH`. There is no bulk write: each mapping is created or removed one at a time, and each change is logged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Name the accountable owner (Priority: P1)

An enterprise architect opens "Inventory Management" (an L2) on the Capabilities tab and sets its owner to the Supply Chain division. Later they change it to the Logistics function. Each capability shows its owner, and an L3 shows the owner it inherits from its L2 or L1.

**Why this priority**: ownership clarity is the first view the user's notes ask for, and the "no owner" warning depends on it.

**Independent Test**: set, change and clear an owner on an L2 and an L1; confirm an L3 cannot take an owner, and that an L3 under an owned L2 shows that owner as inherited.

**Acceptance Scenarios**:

1. **Given** an L2 capability with no owner, **When** an architect sets the owner to an org unit, **Then** the capability shows that owner and the change is logged.
2. **Given** an L2 that already has an owner, **When** the architect sets a different owner, **Then** the new owner replaces the old one; there is never more than one.
3. **Given** an L3 capability, **When** someone tries to set an owner on it, **Then** it is refused with a message saying owners are set at L2 or L1.
4. **Given** an L1 owned by unit A and its L2 owned by unit B, **When** viewing an L3 under that L2, **Then** its effective owner is B (the nearest owned ancestor), shown as inherited.
5. **Given** an owned capability, **When** the owner is cleared, **Then** the capability has no owner of its own and falls back to its parent's owner, if any.

---

### User Story 2 — Record who performs the work, and where (Priority: P1)

The architect opens "Accept Payment" (an L3) and adds performers: Stores in Germany, Stores in France, and E-commerce with no geography. They also add Finance as a contributor.

**Why this priority**: performers are the core of the overlay. The shared-service and gap findings and the footprint all come from them.

**Independent Test**: add, list and remove performers on an L3, with and without a geography; confirm duplicates and non-L3 targets are refused.

**Acceptance Scenarios**:

1. **Given** an L3 capability, **When** an architect adds an org unit as performer with an optional geography, **Then** the mapping is saved and listed on the capability.
2. **Given** the same org unit already performs the capability with no geography, **When** it is added again with a geography, **Then** both mappings exist: performing it everywhere and performing it in one country are recorded separately.
3. **Given** an exact duplicate (same capability, unit, role and geography), **When** it is added, **Then** it is refused with a duplicate message.
4. **Given** an L1 or L2 capability, **When** someone adds a performer or contributor to it, **Then** it is refused with a message saying performers and contributors are mapped at L3.
5. **Given** the geography named is not one the org unit is linked to (940's "operates in"), **When** the performer is saved, **Then** it is saved anyway and flagged with an informational note, never blocked.
6. **Given** a performer mapping, **When** the architect removes it, **Then** it disappears and the removal is logged.

---

### User Story 3 — See the gaps and duplications (Priority: P1)

The architect opens a findings view and sees three lists:
- **No owner**: every L1 and L2 with no owner of its own and no owned ancestor.
- **Shared-service candidates**: every L3 performed by two or more independent org units (a unit and its own descendants count once), with the units and their geographies.
- **Unmapped L3s**: every L3 with no performer and no effective owner.

**Why this priority**: these three views are why the user wants the mapping. They turn it into decisions about standardization and accountability.

**Independent Test**: build a small model with an unowned L2, an L3 performed by two units and an L3 with nothing mapped; confirm each lands in exactly the right list, and that fixing the data removes it on the next view.

**Acceptance Scenarios**:

1. **Given** an L2 with no owner and an L1 parent with no owner, **When** findings are viewed, **Then** that L2 is listed under "No owner". An L2 whose L1 is owned is not listed.
2. **Given** an L3 performed by Stores (Germany) and Stores (France), **When** findings are viewed, **Then** it is **not** a shared-service candidate: one unit performing in two countries is one performer.
3. **Given** an L3 performed by Stores and by E-commerce, **When** findings are viewed, **Then** it is a shared-service candidate listing both units with their geographies.
4. **Given** an L3 performed by the Stores division and by its own Store Operations function, **When** findings are viewed, **Then** it is **not** a shared-service candidate: they are one branch.
5. **Given** an L3 with no performer and no effective owner, **When** findings are viewed, **Then** it is listed as unmapped. An L3 with an inherited owner but no performer is not unmapped. It is shown separately as "owned, no performer", so the gap is still visible.
6. **Given** contributors only, **When** findings are viewed, **Then** contributors change no finding.
7. **Given** any finding, **When** the underlying mapping is fixed, **Then** the finding is gone the next time the view loads; nothing is stored.

---

### User Story 4 — See an org unit's footprint (Priority: P2)

The architect opens the Stores division on the Organization tab and sees its footprint: the L3 capabilities it performs, grouped under their L2 and L1 with counts, plus the capabilities it owns. Its child functions' work is included and attributed to them.

**Why this priority**: the footprint is the reverse view of the mapping. It is useful for reorg and shared-service planning, but the mapping and findings come first.

**Independent Test**: map a division and one of its functions as performers of different L3s; confirm the division's footprint shows both, grouped L1 → L2 → L3, with the function's entry attributed to it.

**Acceptance Scenarios**:

1. **Given** an org unit that performs three L3s under two L2s in one L1, **When** its footprint is viewed, **Then** it shows L1 (3) → two L2s with their counts → the three L3s, each with the geographies it is performed in.
2. **Given** a division whose function performs an L3, **When** the division's footprint is viewed, **Then** that L3 is included and attributed to the function.
3. **Given** an org unit that owns capabilities, **When** its footprint is viewed, **Then** they appear in a separate "Owns" list.
4. **Given** an org unit with no mappings, **When** its footprint is viewed, **Then** it says so plainly.

---

### User Story 5 — Mappings travel with exports and the demo data (Priority: P3)

Exported capability files carry their owner, performers and contributors, and the retail seed includes a mapped example that shows each finding.

**Why this priority**: the file export is how AI tools and other consumers read the architecture; the seed is how the feature is demonstrated.

**Independent Test**: map a capability, run the export, and read the capability's file; reseed and confirm each finding list has at least one entry.

**Acceptance Scenarios**:

1. **Given** mapped capabilities, **When** the export runs, **Then** each capability's file lists its owner (or none), performers with geography, and contributors.
2. **Given** the retail seed, **When** it is loaded, **Then** there is at least one unowned L2, one shared-service candidate and one unmapped L3.

---

### Edge Cases

- **Leaf L2** (an L2 with no L3 children): it can have an owner. It cannot have performers, and it never appears as an unmapped L3. If it has no effective owner, it is listed under "No owner".
- **Deleting a capability** removes all its mappings.
- **Deleting an org unit** with no children removes all its mappings, and its owned capabilities fall back to their parent's owner. Units with children still can't be deleted (940).
- **Deleting a geography** removes the geography from performer mappings. If the same unit then has two performer mappings for the same L3 with no geography, they merge into one.
- **Owner and performer may be the same unit**: Supply Chain can own "Inventory Management" and perform one of its L3s. That's normal and raises no finding.
- **A performer at an enterprise-level unit** (level 1) is allowed. Small organizations may only have one level.
- **Shared-service count uses distinct branches of the org tree**, not distinct org unit and geography pairs. A division and its own function performing the same L3 count as **one** performer. Two functions under different divisions, or two sibling functions under one division, count as two.
- **Empty model**: with no mappings at all, every L2/L1 is "No owner" and every L3 is unmapped. The views say how many there are, rather than listing hundreds of rows with no context.

## Requirements *(mandatory)*

### Functional Requirements

**Mappings**

- **FR-001**: The system MUST let an authorized user set, change and clear the **owner** of a business capability at L1 or L2. A capability has at most one owner. Setting a new owner replaces the old one.
- **FR-002**: The system MUST refuse an owner on an L3 capability, with a message naming the rule.
- **FR-003**: The system MUST let an authorized user add and remove **performers** and **contributors** on an L3 business capability. Each mapping names one org unit and, for performers only, an optional geography.
- **FR-004**: The system MUST refuse performers and contributors on L1 or L2 capabilities, and refuse an exact duplicate mapping, each with a message naming the rule.
- **FR-005**: The system MUST compute each capability's **effective owner**: its own owner, else its nearest owned ancestor, shown as inherited.
- **FR-006**: The system MUST flag, without blocking and without changing the org unit, a performer whose geography is not among the org unit's operating geographies **or inside one of them** (a unit operating in Europe performing in Germany is not flagged). The flag is derived on read.
- **FR-007**: Mappings MUST be removed when their capability or org unit is deleted. Deleting a geography MUST clear it from performer mappings, merging any exact duplicates this creates.
- **FR-008**: Every mapping create, change and removal MUST be logged with the actor, capability, org unit, role and geography.

**Findings (derived, never stored)**

- **FR-009**: The system MUST list every L1 and L2 with no effective owner ("No owner").
- **FR-010**: The system MUST list every L3 performed by **two or more independent org units** ("Shared-service candidates"), with each unit, its geographies and its place in the org tree. Units are independent when neither is an ancestor of the other; performers that are descendants of another performer of the same L3 are folded into that ancestor for the count.
- **FR-011**: The system MUST list every L3 with no performer and no effective owner ("Unmapped"), and separately every L3 with an effective owner but no performer ("Owned, no performer").
- **FR-012**: Contributors MUST NOT affect any finding.
- **FR-013**: Findings MUST be computed from the current mappings on every read and MUST NOT be persisted, enforced by a guard test.

**Footprint (derived, never stored)**

- **FR-014**: For any org unit, the system MUST show the L3 capabilities it and its descendant org units perform, grouped L1 → L2 → L3 with counts at each level, each entry showing which unit performs it and in which geographies.
- **FR-015**: The footprint MUST also list the capabilities the org unit owns, and those it contributes to.

**Surfaces**

- **FR-016**: The Capabilities tab MUST show each capability's owner (own or inherited), and on L3s its performers and contributors, editable by users with write access and read-only otherwise.
- **FR-017**: The findings MUST be reachable from Business Architecture, each entry linking to the capability it is about.
- **FR-018**: The org unit detail panel on the Organization tab MUST show the footprint, each capability linking back to its row on the Capabilities tab.
- **FR-019**: The capability export MUST include owner, performers (with geography) and contributors.
- **FR-020**: The retail seed MUST include mappings that produce at least one entry in each finding list.

### Key Entities

- **Capability Org Mapping**: links one business capability to one org unit with a **role**:
  - **owner**: L1/L2 only, at most one per capability, no geography;
  - **performer**: L3 only, many per capability, optional geography;
  - **contributor**: L3 only, many per capability, no geography.

  It is unique on capability, org unit, role and geography.
- **Effective owner** (derived): a capability's own owner, else its nearest owned ancestor.
- **Finding** (derived): one of No owner, Shared-service candidate, Unmapped, Owned-no-performer, about one capability.
- **Footprint** (derived): an org unit's performed, owned and contributed capabilities, grouped by the capability hierarchy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can set a capability's owner, or add a performer with a geography, in under 30 seconds from its row on the Capabilities tab.
- **SC-002**: For any capability, a user can tell its accountable owner (own or inherited) at a glance, without opening another screen.
- **SC-003**: 100% of L3s performed by two or more independent org units appear as shared-service candidates, and none performed by a single unit or a single branch (a unit plus its own descendants) do.
- **SC-004**: Every finding reflects a mapping change the next time the view loads. No finding or footprint is ever persisted (guard test).
- **SC-005**: An org unit's footprint answers "what does this unit do?" for a tree of 300 business capabilities in under 2 seconds.
- **SC-006**: Changing org structure (adding, renaming or removing an org unit) never requires changing a business capability.

## Assumptions

- **Contributor is in scope** (confirmed 2026-11-16) as a recorded relationship at L3 only, with no geography and no findings. It can be widened later.
- **Owner at L1 is allowed**, per the notes ("ideally at L2"). An L1 owner is inherited by its L2s and L3s unless they have their own.
- **"No owner" is about L1 and L2 only.** L3s never have their own owner, so their accountability shows through the effective owner and the unmapped lists.
- **The footprint includes descendant org units** (confirmed 2026-11-16), attributed to the unit that performs the work, since a division's footprint is the sum of what its functions do.
- **A performer's geography is not restricted** to the org unit's operating geographies (confirmed 2026-11-16); a mismatch is flagged as information, because 940's operating links are descriptive and may lag reality.
- **Findings are shown on Business Architecture** (confirmed 2026-11-16). Adding them to Governance → Architecture Health (939) is a follow-on bead.
- Mapping volume is modest: hundreds of capabilities and org units, low thousands of mappings.

## Out of Scope (follow-ons)

- Per-region assessments and the regional heat map (spec 942).
- Rationale on application mappings (spec 943).
- Showing these findings on Governance → Architecture Health.
- Owners or performers on application or technical capabilities.
- Individual people or roles as owners (the notes keep those in an HR model).
- Mapping history (who owned what last year).
