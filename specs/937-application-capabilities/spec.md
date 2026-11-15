# Feature Specification: Application Capabilities — the middle layer of the capability model

**Feature Branch**: `937-application-capabilities`
**Created**: 2026-11-15
**Status**: Draft
**Bead**: ADP-6et (spec A of 2)
**Input**: User description: "we should support business, application and technical capabilities. business capabilities should link to application capabilities and application capabilities to technical capabilities. Business capabilities should also be able to be supported without technical capabilities but application capabilities require technical capabilities. we need to make sure this is fully supported." Followed by the user's mapping-level guidance and a worked Store POS example (both recorded in ADP-6et's notes).

## Background and Resolved Decisions

ADP has business capabilities (Business screen, L1–L3) and technical capabilities (Technical Architecture screen, L1–L3). There is no **application capability** layer between them. Today an *application* (a system) links straight to a business capability and straight to a technical capability. No capability links to another capability.

This spec adds the application capability layer and its links, so the capability model reads:

> Business capability (L3) → Application capability (L3) → Technical capability (L2 or L3)

and each application capability L3 is **realized by** one or more applications.

Spec B (ADP-6et, follows this one) builds the analysis on top of this data: roll-ups of health, cost and risk, transitive impact analysis (for example, "offline sync reaches end of life → Process Checkout is exposed"), and gap/overlap rationalization views. This spec stores and shows the links, plus the one governance warning the user asked for.

Decisions confirmed with the user (2026-11-15):

| # | Decision |
|---|---|
| D1 | An application capability is a **new entity**, not the existing Application. |
| D2 | Application capabilities have a **three-level hierarchy** (L1–L3), like the other two layers. |
| D3 | An application capability L3 with no technical capability raises a **governance warning**. It **never blocks saving**. |
| D4 | **Shared enterprise catalog.** There is one tree of application capabilities. Each L3 can be realized by one or more applications (many-to-many). |
| D5 | The existing direct links (application ↔ business capability with a fit score, application ↔ technical capability with provides/consumes) are **kept unchanged**. The new layer is additive. Deriving or retiring the old links is a follow-on. |
| D6 | The warning appears as a **badge** on the capability (tree and detail) and in a **"missing technical capability" gaps list** on the Application Capabilities screen. |
| D7 | Two specs: this one (entity, links, warning, screens, search, export, seed), then spec B (roll-ups, impact, gap/overlap). |

Mapping rules from the user's guidance:
- **Business → Application:** L3 to L3 only. L1 and L2 mappings are too coarse to say anything.
- **Application → Technical:** an application L3 maps to a technical **L2 or L3**. Use L3 where the dependency is architecturally meaningful, L2 otherwise. Don't map incidental usage.
- **L1 is for navigation and grouping only** and is never mapped directly at any layer.
- Mappings are **many-to-many at the leaf level**, which is where overlaps and gaps show up.
- **No direct business → technical mapping.** A business-to-technology view is derived through the application layer (spec B).
- **Granularity must be comparable across layers.** Each layer's L3 should be roughly the same "size" of thing. Software can't enforce this, so it is guidance shown to the user.

Ground-truth checks against the code (migration head `045`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | Business capabilities: `BusinessCapability`, `level` 1–3, `parent_id`, `position`, domain on L1 only (`src/adp/business/models.py:70`). Deleting one with children is blocked (`src/adp/business/store.py:407`) | Business-capability deletes stay as they are. Deleting a business L3 removes its links to application capabilities |
| GT-2 | Technical capabilities: `level` derived from the parent, max depth 3 (`src/adp/application/store.py:1517-1526`), delete with children blocked (`store.py:1586`). No `position` field | Application capabilities follow the same derived-level, max-depth-3, block-delete-with-children rules |
| GT-3 | `application_capability_links` (app ↔ business capability, `fit_score` 1–5) and `application_tech_cap_links` (app ↔ technical capability, `usage_type` provides/consumes) exist, with `ON DELETE CASCADE` (migration 010) | Untouched (D5). The new links are separate tables |
| GT-4 | Technical capability writes ride the `("/api/v1/technical-capabilities", WRITE_APPLICATION)` prefix rule (`src/adp/authz/enforcement.py:163`) | Application capability writes use `WRITE_APPLICATION` too. No new permission |
| GT-5 | The Applications screen has Registry / Rationalization / Roadmap tabs (`web/src/application/ApplicationPage.tsx:89-95`) | Application Capabilities is a fourth tab there, not a new nav entry |
| GT-6 | Search indexes business and technical capabilities (`src/adp/search/index.py:36-37`). Export writes business and application trees (`src/adp/export/business_arch.py`, `application_arch.py`) | A new search entity type, and application capabilities and their links in the application export |
| GT-7 | The EA pattern metamodel has no `application_capability` element type (`src/adp/patterns/models.py:70`) | Out of scope here (see Out of Scope) |

## Clarifications

### Session 2026-11-15

- Q: Is an application capability a new entity, or does the Application play that role? → A: New entity (D1).
- Q: Hierarchy? → A: Three levels (D2).
- Q: Hard rule or warning when an application capability has no technical capability? → A: Governance warning only; saving is never blocked (D3).
- Q: How do application capabilities relate to applications? → A: Shared catalog, each L3 realized by one or more applications (D4).
- Q: What happens to the existing direct links? → A: Kept unchanged (D5).
- Q: Where does the warning appear? → A: Badge in the tree and detail, and a gaps list on the screen (D6).
- Q: How should the work be split? → A: Two specs (D7).
- Q: Where are links between layers edited? → A: **Only on the application capability's detail.** The business capability, technical capability and application screens show them read-only, with a link back.
- Q: How should a business L3 show the old direct application links next to the new layer? → A: **Both, labelled separately, never merged.** Checking the code showed the Business screen's capability rows (`web/src/business/CapabilityNode.tsx`) show no application links today, so the new "Application capabilities" section is the only application information there. The old links stay visible where they are now, on the application screen.
- Q: Who may edit? → A: **`WRITE_APPLICATION`**, as for technical capabilities. Business-only roles can view links but not change them.

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: each link is stored once. The warning is derived on read and never stored.
- **ART-V** — Security by Design: writes are gated by the existing `WRITE_APPLICATION` permission. No sensitive data is added.
- **ART-IX** — Auditability: actor-attributed log lines for every create, update, delete and link change (the domain-package precedent).
- **ART-XI** — Traceability: the business → application → technical chain is navigable from every layer.
- **ART-XIII** — Typed Contracts: level and link rules are closed and validated.
- **ART-XV** — Schema Evolution: one reversible migration (`046`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Build the application capability catalog (Priority: P1)

An Enterprise or Solution Architect opens Applications → **Capabilities** and builds the application capability tree. For example: L1 "Transaction Processing", L2 "Checkout", "Pricing", "Payments", "Returns", and L3 leaves "Basket Calculation", "Price Rule Evaluation", "Tender Authorization", "Return Authorization" and "Receipt Generation".

**Why this priority**: every link and view depends on the catalog existing.

**Independent Test**: create the POS branch through the screen and see it in the tree after a reload. The level is derived from the parent, and a fourth level is refused.

**Acceptance Scenarios**:

1. **Given** no application capabilities, **When** the architect creates "Transaction Processing" with no parent, **Then** it is an L1.
2. **Given** an L1, **When** they add a child, **Then** it is an L2. A child of an L2 is an L3.
3. **Given** an L3, **When** they try to add a child, **Then** it is refused with a message that the maximum depth is 3.
4. **Given** a capability with children, **When** they try to delete it, **Then** it is refused until the children are removed.
5. **Given** a reviewer (no `WRITE_APPLICATION`), **When** they open the tab, **Then** they see the tree but no create, edit, delete or link controls.
6. **Given** two siblings, **When** the tree renders, **Then** siblings are sorted alphabetically (matching the technical capability tree).

---

### User Story 2 — Link the three layers at the right levels (Priority: P1)

The architect links each application capability L3 to the business capability L3s it supports and to the technical capabilities (L2 or L3) it depends on. They also record which applications realize it. In the POS example, "Tender Authorization" supports "Accept Payment", depends on "Payment Tokenization (P2PE)" and "API Gateway Services", and is realized by Store POS.

**Why this priority**: the links are the feature. Without them the new layer is just a list.

**Independent Test**: create the five POS chains and see each link from both ends: on the application capability, on the business capability, on the technical capability, and on the application.

**Acceptance Scenarios**:

1. **Given** an application capability L3 and a business capability L3, **When** they are linked, **Then** the link shows on both.
2. **Given** a business capability L1 or L2, **When** someone tries to link it to an application capability, **Then** it is refused with the reason ("business capabilities are mapped at L3").
3. **Given** an application capability L1 or L2, **When** someone tries to link it to a business or technical capability, **Then** it is refused ("application capabilities are mapped at L3; L1 and L2 are for grouping").
4. **Given** a technical capability L1, **When** someone tries to link an application capability to it, **Then** it is refused ("map to a technical L2 or L3"). L2 and L3 targets are accepted.
5. **Given** "Tender Authorization", **When** it is linked to two technical capabilities, **Then** both links are kept (many-to-many is normal).
6. **Given** a link that already exists, **When** it is added again, **Then** it is refused as a duplicate and the existing link is unchanged.
7. **Given** an application capability L3, **When** an application is recorded as realizing it, **Then** the application's page lists the capability, and the capability lists the application. Only L3s can be realized.
8. **Given** a business capability L3 with no application capability, **Then** that is allowed and raises no warning. Business capabilities can stand alone.
9. **Given** any of the three ends is deleted, **When** the page is reloaded, **Then** links to it are gone and nothing else is affected.

---

### User Story 3 — See which application capabilities lack a technical capability (Priority: P1)

The architect sees at a glance which application capability L3s have no technical capability behind them: a warning badge in the tree and on the detail, and a "Missing technical capability" list on the screen. The warning never stops them saving.

**Why this priority**: it is the one rule the user named. It is a governance check, not a validation error.

**Independent Test**: create an L3 with no technical link. It saves, shows the badge, and appears in the list. Add a technical link and the badge and list entry disappear. Delete that technical capability and they come back.

**Acceptance Scenarios**:

1. **Given** a new application capability L3 with no technical link, **When** it is saved, **Then** the save succeeds and the capability shows the warning badge.
2. **Given** the gaps list, **Then** it shows every L3 without a technical link, with its L1/L2 path, and is empty when there are none.
3. **Given** a flagged L3, **When** a technical link is added, **Then** the badge and list entry disappear without a reload.
4. **Given** an L3 whose only technical capability is deleted, **Then** the warning reappears.
5. **Given** an L1 or L2 application capability, **Then** it never shows the warning (they are never mapped).
6. **Given** the warning, **Then** it is computed from the current links every time and never stored.

---

### User Story 4 — Follow the chain from any layer (Priority: P2)

From a business capability L3 the architect sees the application capabilities that support it and the applications realizing them. From a technical capability they see the application capabilities that depend on it. From an application they see the application capabilities it realizes.

**Why this priority**: traceability across layers is what makes the model useful. The analysis on top of it is spec B.

**Independent Test**: with the POS example loaded, open "Accept Payment", "API Gateway Services" and Store POS, and confirm each shows the expected linked items.

**Acceptance Scenarios**:

1. **Given** "Accept Payment" (business L3), **Then** its row or detail lists "Tender Authorization" and the realizing application, Store POS.
2. **Given** "API Gateway Services" (technical L3), **Then** it lists "Tender Authorization" and "Return Authorization".
3. **Given** Store POS, **Then** its page lists the five application capabilities it realizes.
4. **Given** any listed item, **When** it is clicked, **Then** the user goes to that item.

---

### User Story 5 — The new layer is searchable, exported and seeded (Priority: P2)

Application capabilities can be found in search, appear in the file export with their links, and the retail seed loads the Store POS example so the model can be demonstrated.

**Independent Test**: search for "Tender", find the application capability. Run the export and see its file with its links. Reseed and see the POS branch on all three layers, linked as in the example.

**Acceptance Scenarios**:

1. **Given** an application capability, **When** a user searches for its name, **Then** it is returned. Renaming or deleting it updates or removes the search entry.
2. **Given** the export runs, **Then** each application capability is written with its parent, level, linked business capabilities, technical capabilities and realizing applications. Deleted ones disappear from the export.
3. **Given** a fresh reseed, **Then** the three POS branches and the five chains from the example exist. At least one seeded L3 has no technical capability, so the warning can be demonstrated.

### Edge Cases

- **Levels never change:** no layer allows a parent or level change after creation, so a valid link stays valid for its lifetime.
- **Deleting a business L3 that has links:** it is deleted (existing rules), and its links go with it.
- **Deleting a technical capability linked to application capabilities:** it is deleted (existing rules), the links go, and any L3 left with no technical link starts showing the warning.
- **Deleting an application:** its realization links go. The application capabilities stay.
- **Name collisions:** two application capabilities may share a name in different branches. Siblings may not share a name.
- **Granularity mismatch:** can't be detected. The screen shows a short guidance note ("each layer's L3 should be about the same size of thing").

## Requirements *(mandatory)*

### Functional Requirements

**Catalog**
- **FR-001**: Users with `WRITE_APPLICATION` MUST be able to create, rename, describe and delete application capabilities. Everyone with platform read access MUST be able to view them.
- **FR-002**: The level MUST be derived from the parent (no parent = L1), with a maximum depth of 3. Creating a fourth level MUST be refused.
- **FR-003**: Deleting a capability that has children MUST be refused until the children are removed.
- **FR-004**: Sibling names MUST be unique. The same name in different branches is allowed.
- **FR-005**: A capability's parent and level MUST be fixed after creation, matching business and technical capabilities. Moving one means deleting and recreating it.

**Links**
- **FR-006**: An application capability L3 MUST be linkable to any number of business capability L3s, and each business L3 to any number of application capability L3s.
- **FR-007**: An application capability L3 MUST be linkable to any number of technical capabilities at L2 or L3.
- **FR-008**: An application capability L3 MUST be linkable to any number of applications that realize it, and an application to any number of application capability L3s.
- **FR-009**: Every link MUST be refused if either end is at a level the rules don't allow (business L1/L2, application L1/L2, technical L1), with a message naming the rule.
- **FR-010**: Duplicate links MUST be refused without changing the existing link.
- **FR-011**: Deleting any linked item MUST remove its links and nothing else.
- **FR-012**: There MUST be no direct business → technical capability link.
- **FR-013**: The existing application ↔ business capability and application ↔ technical capability links MUST keep working unchanged.

**Governance warning**
- **FR-014**: An application capability L3 with no technical capability link MUST show a "missing technical capability" warning in the tree and on its detail.
- **FR-015**: The Application Capabilities screen MUST provide a list of all L3s with that warning, showing each one's L1/L2 path.
- **FR-016**: The warning MUST never block creating, editing or saving anything.
- **FR-017**: The warning MUST be computed from the current links when read and never stored.

**Traceability**
- **FR-018**: A business capability MUST show the application capabilities linked to it and their realizing applications.
- **FR-019**: A technical capability MUST show the application capabilities that depend on it.
- **FR-020**: An application MUST show the application capabilities it realizes.
- **FR-021**: Every listed related item MUST navigate to that item.

**Platform integration**
- **FR-022**: Application capabilities MUST be indexed for search and kept in sync on create, rename and delete. The existing search backfill MUST cover them.
- **FR-023**: The file export MUST include each application capability with its hierarchy and all three kinds of links, and remove files for deleted ones.
- **FR-024**: The retail seed MUST load the Store POS example on all three layers, including the five chains and at least one L3 without a technical capability.
- **FR-025**: Every write MUST produce an actor-attributed log line.
- **FR-026**: The screen MUST show short guidance on mapping levels and comparable granularity.

### Key Entities

- **Application Capability**: a logical capability delivered by software ("Price Rule Evaluation"). Name, optional description, parent, derived level 1–3. Part of one shared enterprise tree.
- **Business ↔ Application Capability link**: a business capability L3 supported by an application capability L3. No attributes of its own.
- **Application ↔ Technical Capability link**: an application capability L3 depending on a technical capability L2/L3. No attributes of its own.
- **Application Capability Realization**: an application that realizes an application capability L3. No attributes of its own.
- **Missing-technical-capability warning** (derived, not stored): present on an application capability L3 that has no technical link.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can enter the Store POS example (three branches, five chains, Store POS realizing five capabilities) through the screens in under 15 minutes.
- **SC-002**: 100% of link attempts that break a level rule are refused with a message naming the rule. 100% of valid ones succeed.
- **SC-003**: The warning is correct for every application capability L3 after every link change and delete, with no stale badges after a reload.
- **SC-004**: From any one of the five POS chains, a user reaches the other two layers and the realizing application in at most two clicks.
- **SC-005**: No existing screen, report or test that uses the old application ↔ capability links changes behavior.
- **SC-006**: Searching for any seeded application capability by name finds it as the top application-capability result.

## Assumptions

- The links carry no attributes (no fit score, no significance). Users choose the technical level (L2 vs L3) to express significance, as the guidance says.
- Business capability L3s and technical capabilities are unchanged except for showing their new links.
- The tree uses the technical capability tree's alphabetical sibling order. No manual ordering.

## Out of Scope (follow-ons)

- **Spec B (ADP-6et):** roll-ups of health, cost and risk from leaf links; transitive impact analysis; gap/overlap and rationalization views; the business → technology derived view; technical capability end-of-life.
- Showing the warning on the Governance screen or the Overview.
- Deriving or retiring the existing application ↔ business and application ↔ technical links.
- An `application_capability` element type in the EA pattern metamodel and conformance snapshot.
- Chat assistant retrieval and Agent Review context for application capabilities.
- Generating diagrams from the three layers.
