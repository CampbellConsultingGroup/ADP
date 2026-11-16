# Feature Specification: Org Units and Geography — reference models for the capability overlays

**Feature Branch**: `940-org-units-geography`
**Created**: 2026-11-15
**Status**: Draft
**Bead**: ADP-55k.1 (spec 1 of 4 in epic ADP-55k)
**Input**: User description: "ADP-55k". The epic's notes hold the user's source notes and decisions.

## Background and Resolved Decisions

ADP has one enterprise business capability model. The user wants to know who performs and owns each capability, and where. Their notes are firm that organization and geography are **overlays on the single model, never copies of capabilities**: five regional copies of "Process Payroll" would hide five applications doing one job.

ADP has nothing to hang those overlays on. Organization is free text in several places, and there is no geography at all. This spec builds the two reference models. Later specs in the epic use them:
- 941 maps owners and performers to capabilities;
- 942 adds per-region assessments;
- 943 adds the reason on each application mapping.

Decisions confirmed with the user (2026-11-15; full text in ADP-55k's notes):

| # | Decision |
|---|---|
| D1 | A governed **Org Unit** model with 3 levels: enterprise → division/business unit → function/department. No teams or individual roles; those belong in an HR model. |
| D2 | A separate **Geography** model, global → region → country, **seeded from the full ISO 3166 country list grouped into UN M49 regions**. Every entry is editable. Region is its own axis, not a level in the org tree, so "what do we do in EMEA across all business units?" can be asked directly. |
| D3 | An org unit **operates in** any number of geographies (many-to-many), and may have one **primary geography**. That serves companies whose business units are themselves geographic ("Europe Retail"). Legal entity is deferred. |
| D4 | Moving existing free text onto org units is a **review queue**, and only `applications.owning_business_unit` is in scope. Each distinct value is listed as unmatched until an architect maps it to an org unit or creates one. **Nothing is created silently, and the free text is kept.** Other free-text organization fields stay as they are in this epic. |

Ground-truth checks against the code (main at 8c8c65d, migration head `047`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | There is no organization or geography entity. The nearest thing is free-text `jurisdiction` on compliance frameworks | Both models are new |
| GT-2 | `applications.owning_business_unit` is free text (`src/adp/application/store.py:125`). It is filtered by exact match (:545), grouped as raw strings in the cost roll-up, and bucketed by distinct value on the Portfolio screen (`web/src/portfolio/groupApplications.ts:152`). The retail seed never sets it | It gains an org-unit link. Grouping uses the link when present. The seed gains values so the review queue can be demonstrated |
| GT-3 | Compliance already uses "organization" to mean an estate-wide control mapping (`src/adp/compliance/store.py:169`) | The new entity is called **Org Unit** everywhere, to avoid confusion |
| GT-4 | 937's application capability catalog is the latest 3-level governed hierarchy. Its rules: level derived from the parent, max depth 3, parent and level fixed once set, no delete while children exist, sibling names unique ignoring case (`src/adp/application/app_capabilities.py`) | Org units and geographies follow the same rules |
| GT-5 | Writes under `/api/v1/business/` already require `WRITE_BUSINESS_ARCH` (`src/adp/authz/enforcement.py:161`) | Both models live under Business Architecture. No new permission |
| GT-6 | The Business Architecture screen has the tabs Domains, Capabilities, Value Streams and Heat Map (`web/src/business/BusinessPage.tsx:11`) | A new **Organization** tab holds both trees and the review queue |

## Clarifications

### Session 2026-11-15

- Q: How is the existing free text migrated? → A: A review queue, never silent creation (D4).
- Q: Which fields are in scope? → A: Only `applications.owning_business_unit` (D4).
- Q: How is geography seeded? → A: The full ISO 3166 list grouped into UN M49 regions, editable (D2).
- Q: Is region part of the org hierarchy? → A: No, it is a separate axis (D2, D3).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: organization and geography each get one governed model. The free text stays as the historical record, and the link becomes the source for grouping.
- **ART-V** — Security by Design: writes use the existing `WRITE_BUSINESS_ARCH` gate. Org names and country lists aren't sensitive.
- **ART-IX** — Auditability: every create, update, delete, link change and review-queue resolution is logged with the actor.
- **ART-XIII** — Typed Contracts: levels and kinds are closed sets. Country codes are validated.
- **ART-XV** — Schema Evolution: one reversible migration (`048`), including the seeded geography.
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. The new data (org structure, a public country list) isn't sensitive. Writes need `WRITE_BUSINESS_ARCH`, like the rest of Business Architecture. The review queue's bulk action changes only the org-unit link on applications whose free text matches exactly, and it is logged. It never changes the free text, so it can always be traced and undone by hand.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Build the organization model (Priority: P1)

An enterprise architect opens Business Architecture → **Organization** and builds the org tree. For example: enterprise "Retail Co"; divisions "Stores", "Digital", "Supply Chain" and "Corporate"; under Corporate, the functions "Finance" and "HR".

**Why this priority**: every later spec in the epic maps capabilities to org units.

**Independent Test**: build that tree, reload, and see it. A fourth level is refused, and so is deleting a unit that has children.

**Acceptance Scenarios**:

1. **Given** no org units, **When** "Retail Co" is created with no parent, **Then** it is level 1 (enterprise).
2. **Given** an enterprise, **When** a child is added, **Then** it is level 2 (division), and its child is level 3 (function).
3. **Given** a function, **When** a child is attempted, **Then** it is refused with a message that the maximum depth is 3.
4. **Given** two siblings named "Finance" and "finance", **When** the second is saved, **Then** it is refused as a duplicate.
5. **Given** a unit with children, **When** deletion is attempted, **Then** it is refused until the children are removed.
6. **Given** a reviewer (no `WRITE_BUSINESS_ARCH`), **When** they open the tab, **Then** they see the tree but no editing controls.

---

### User Story 2 — Use a standard geography (Priority: P1)

The geography tree is ready on first use: Global, then regions (Europe, Americas, Asia, Africa, Oceania) with their sub-regions folded in, then every ISO 3166 country with its two-letter code. Architects can rename entries, add entries, or remove ones they don't need.

**Why this priority**: per-region work in 941–943 needs a stable, shared geography.

**Independent Test**: after the migration, "Germany (DE)" sits under Europe, and "Brazil (BR)" under the Americas. Renaming a region keeps its countries.

**Acceptance Scenarios**:

1. **Given** a fresh database, **When** the migration runs, **Then** the geography tree holds Global, the M49 regions and about 250 countries, each country with a unique ISO 3166 alpha-2 code.
2. **Given** a country, **When** its code is changed to one another country already uses, **Then** the change is refused.
3. **Given** a region with countries, **When** deletion is attempted, **Then** it is refused until its countries are moved or removed.
4. **Given** the migration is reversed, **When** it completes, **Then** the geography tables and their seeded rows are gone.

---

### User Story 3 — Say where an org unit operates (Priority: P2)

An architect records that "Stores" operates in the United States, Canada and Germany, and that "Europe Retail" has Europe as its primary geography.

**Why this priority**: it answers "which business units operate in APAC?". It is less critical than the trees themselves.

**Independent Test**: link "Stores" to three countries. The org unit shows them, and each country shows "Stores" in its list of org units.

**Acceptance Scenarios**:

1. **Given** an org unit and a geography, **When** they are linked, **Then** the link shows on both, and a duplicate link is refused.
2. **Given** an org unit, **When** its primary geography is set, **Then** it is shown, and it needn't be one of its linked geographies.
3. **Given** a linked geography is deleted, **When** the deletion completes, **Then** its links are removed, and any primary geography pointing at it is cleared.

---

### User Story 4 — Resolve free-text business units (Priority: P1)

The **Unmatched** list shows each distinct `owning_business_unit` value that has no org-unit link, with how many applications use it. For each value, the architect either picks an existing org unit or creates one. Every application with that exact value is then linked to it.

**Why this priority**: this is how existing data joins the governed model without anything being created silently.

**Independent Test**: seed three applications with "Store Systems" and one with "Store systems". Both values appear separately. Mapping both to the "Stores" org unit links all four applications, and both values leave the list.

**Acceptance Scenarios**:

1. **Given** applications with free-text business units and no link, **When** the Unmatched list opens, **Then** each distinct exact value appears once, with its application count, largest first.
2. **Given** an unmatched value, **When** it is mapped to an existing org unit, **Then** every application with exactly that value gets the link, and its free text is unchanged.
3. **Given** an unmatched value, **When** "create" is chosen with a name and parent, **Then** the org unit is created and linked in one step.
4. **Given** an application linked to an org unit, **When** its free text is later edited, **Then** the link stays, until it is changed on the application itself.
5. **Given** a resolution, **When** it completes, **Then** a log line records the actor, the value, the org unit and the number of applications updated.

---

### User Story 5 — Use the org unit on applications (Priority: P2)

The application form has an **Owning org unit** picker beside the free-text field. On the Portfolio screen, "Ownership / Business Unit" groups by org unit where an application is linked. Otherwise it groups by the free text, marked unmatched.

**Why this priority**: it puts the governed model to work immediately on the screen that groups by business unit today.

**Independent Test**: link two of three applications that share a free-text value. Portfolio grouping shows the org unit's bucket with two applications, and an "unmatched" bucket with the third.

**Acceptance Scenarios**:

1. **Given** an application, **When** an org unit is picked on its form, **Then** the link is saved, and clearing it removes the link.
2. **Given** linked and unlinked applications, **When** Portfolio groups by business unit, **Then** linked ones group under the org unit's name, and unlinked ones under their free text marked "(unmatched)".

### Edge Cases

- **Exact match only.** Free-text values that differ only in case or spacing are listed separately (scenario 1 of US4), so the architect decides whether they are the same unit. Nothing is merged automatically.
- **Deleting a linked org unit.** Deleting an org unit that applications are linked to is allowed. The applications' links are cleared and their free text remains, so they show as unmatched again.
- **Name collisions.** A geography and an org unit may share a name ("Europe"). They are different things.
- **Country with no region.** A country's M49 region assignment can't be found for a few codes in the source list. Those countries are placed directly under Global, never dropped.
- **Empty states.** No org units: the tab says how to start. No unmatched values: the Unmatched list says everything is resolved.

## Requirements *(mandatory)*

### Functional Requirements

**Org units**

- **FR-001**: The system MUST store org units in a hierarchy of at most 3 levels: enterprise (1), division/business unit (2), function/department (3). The level is derived from the parent.
- **FR-002**: An org unit's parent and level MUST NOT change after creation. Deleting an org unit with children MUST be refused. Sibling names MUST be unique ignoring case, including among top-level units.
- **FR-003**: Users with `WRITE_BUSINESS_ARCH` MUST be able to create, rename, describe and delete org units. Everyone who can read Business Architecture MUST be able to view them.

**Geography**

- **FR-004**: The system MUST store geographies in a hierarchy of at most 3 levels: global (1), region (2), country (3). It follows the same structural rules as FR-002.
- **FR-005**: The migration MUST seed Global, the UN M49 regions (sub-regions folded into their region) and every ISO 3166-1 country with its alpha-2 code. Countries with no region in the source go directly under Global.
- **FR-006**: Country codes MUST be unique and MUST be two uppercase letters. Region and Global entries have no ISO code (they may carry the M49 numeric code).
- **FR-007**: Users with `WRITE_BUSINESS_ARCH` MUST be able to rename, add and delete geographies, including seeded ones, under FR-004.

**Org unit ↔ geography**

- **FR-008**: An org unit MUST be linkable to any number of geographies, and a geography to any number of org units. A duplicate link MUST be refused.
- **FR-009**: An org unit MAY have one primary geography. Deleting that geography MUST clear it. Deleting either side of a link MUST remove the link.

**Applications and the review queue**

- **FR-010**: An application MUST have an optional link to an org unit (its owning org unit), separate from the free-text `owning_business_unit`, which is kept unchanged.
- **FR-011**: The system MUST list each distinct, non-empty `owning_business_unit` value among applications without an owning org unit, with its application count.
- **FR-012**: Resolving an unmatched value MUST link every application with exactly that value, and no owning org unit, to the chosen org unit, which may be created in the same action. It MUST report how many applications were updated and log the actor, value, org unit and count.
- **FR-013**: Deleting an org unit MUST clear the owning-org-unit link on its applications, leaving their free text.
- **FR-014**: The application form MUST offer an owning-org-unit picker. Portfolio's business-unit grouping MUST group linked applications by org unit and unlinked ones by their free text, marked unmatched.

**General**

- **FR-015**: Org units MUST be searchable. Org units and geographies MUST be included in the business architecture export. Geography is not indexed for search: about 250 static country names would crowd global search (plan R7).
- **FR-016**: The retail seed MUST add an org tree, operating geographies for some units, and free-text `owning_business_unit` values on some applications (including a near-duplicate), so the review queue can be demonstrated.

### Key Entities

- **Org Unit**: name, description, level (1 enterprise / 2 division / 3 function), parent, optional primary geography.
- **Geography**: name, optional code (ISO 3166 alpha-2 for countries; optional M49 code for regions), level (1 global / 2 region / 3 country), parent.
- **Org Unit Geography**: an org unit operates in a geography (many-to-many).
- **Application.owning org unit**: an optional link, alongside the existing free text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fresh database, the geography tree is complete (about 250 countries, each under a region or Global) with no manual steps.
- **SC-002**: An architect can turn every seeded free-text business-unit value into an org-unit link in under 2 minutes, without editing applications one by one.
- **SC-003**: After resolution, Portfolio's business-unit grouping shows no unmatched buckets for the resolved values.
- **SC-004**: No free-text value is changed by any action in this feature, and no org unit is created except by an explicit user action.
- **SC-005**: Every acceptance scenario is covered by an automated test. The migration reverses cleanly, including the seeded rows.

## Assumptions

- **UN M49 regions**, with sub-regions folded into their parent, give the 3-level global → region → country shape. If an organization uses its own regions (e.g. EMEA, APAC), they can be added or restructured by editing, since everything is editable.
- **The ISO 3166 / M49 list is stored as a data file in the repo** and loaded by the migration. No new package is needed, and nothing is downloaded.
- **Owners, performers and per-region data are not in this spec** (941–943). Neither is legal entity.

## Out of Scope (follow-ons)

- Capability owner and performer mappings, and their findings (941).
- Per-region assessments and the regional heat map (942).
- Mapping rationale and region-level realization (943).
- Migrating `business_domains.org_unit`, `primary_owner`, the governance owner fields, and strategy and agent owners.
- Legal entity, and linking compliance frameworks to geography (e.g. GDPR → EU countries).
