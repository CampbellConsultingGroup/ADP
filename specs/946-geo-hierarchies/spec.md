# Feature Specification: GEO-01 — Places, typed hierarchies, nodes and effective-dated memberships

**Feature Branch**: `946-geo-hierarchies`
**Created**: 2026-11-20
**Status**: Draft
**Bead**: ADP-bo1.1 (first of four in epic ADP-bo1 "GEO"); unblocks ADP-bo1.2/.3/.4 and ADP-4hg
**Input**: User description: "start on ADP-bo1.1" — the epic holds the user's design (several independent geographic hierarchies over one shared vocabulary of atomic places).

## Background and Resolved Decisions

A global corporation runs on several geographic hierarchies at once: regulatory (EU, EEA, Eurozone), data residency (EU/EEA zone, UK zone), infrastructure (Azure geography → region), sales (Americas → NA → US-East), tax (US nexus states), operational (Support hub EMEA) and custom ones. They group the same countries differently, some are strict trees and some are DAGs (Ireland is in the EU, the EEA and the Eurozone at once), and their membership changes over time (the UK left the EU on 2020-01-31).

ADP today (940) has one editable tree: Global → 5 UN M49 regions → 249 countries. This spec replaces it with the foundation of the epic's model: atomic **places**, any number of typed **hierarchies** with their own **nodes**, and **dated memberships**.

Decisions (epic ADP-bo1, user, 2026-11-20):

| # | Decision |
|---|---|
| D1 | Spec 945 (flat custom regions, one region per country) is parked; this spec reuses its country-set containment, not its schema. |
| D2 | Memberships are effective-dated from the start; reads are evaluated as of a date (today by default). |
| D3 | Places in this cut are countries only. Subdivisions (selectively, only those needed) and governed custom places come with GEO-04. |
| D4 | The M49 tree becomes one read-only **reference** hierarchy; existing links to its regions keep working. |
| Q1 | Today's geography links (org unit operating and primary geography, capability performer geography, regional assessments, region-specific scope, realization geography) may point at **any place or any node of any hierarchy**. |
| Q2 | Write permission **by kind**: regulatory, data residency and tax hierarchies need `write_compliance`; the others need `write_business_arch`. |
| Q3 | Managed on **Business → Organization → Geography**, replacing today's editable tree. |
| Q4 | Rows users added to today's tree move into a **"Custom (migrated)"** hierarchy; nothing is lost and links keep working. |

Ground truth (main at e8c16dd, migration head `056`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | `geographies` holds every row; six tables reference `geographies.id` (org unit primary geography and operating geographies, performer mappings, regional assessments, region-specific scope, realizations). Ids are stable strings (`geo-001`, `geo-m49-150`, `geo-DE`). | Keep `geographies` as the one addressable table and keep every id. Each row becomes a place or a node; no referencing table changes. |
| GT-2 | Parent/level live on the row (`parent_id`, `level`). | Parenthood moves into dated memberships; level is derived for display. |
| GT-3 | "Contains" is computed by walking `parent_id` in 941 (performer note), 942 (applicability, heat map columns) and 943 (overlap of realization scopes); Global is refused for assessments and realizations by level. | All three use one resolver over memberships as of today; Global stays refused (it is the root of the reference hierarchy, `geo-001`). |
| GT-4 | The `write_business_arch` and `write_compliance` actions are held by the same roles today. | The per-kind rule adds a compliance check for three kinds; nobody's access changes today. |

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development; **ART-IV** — Test-Driven Development (always apply).
- **ART-II** — Single Source of Truth: a country exists once as a place; hierarchies reference it. Containment and applicability are derived on read.
- **ART-V** — Security by Design: per-kind write permission; read-only hierarchies (system of record set) refuse writes.
- **ART-IX** — Auditability: every hierarchy, node and membership change is logged with the actor.
- **ART-XIII** — Typed Contracts: kind, shape and dates are closed types.
- **ART-XV** — Schema Evolution: one reversible migration (`057`) that keeps every existing id and link.
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low to moderate. Geography is reference data readable by all users. Regulatory, data residency and tax hierarchies will drive compliance applicability (GEO-03), so a wrong membership could hide an obligation: writes to those kinds require `write_compliance`, every change is logged with the actor and dates, and history is kept by dating memberships rather than deleting them. Hierarchies with a system of record are read-only through the API.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Existing geography keeps working (Priority: P1)

After the upgrade, everything that pointed at a country, a UN region or Global still does, and every derived view (performer notes, regional heat map, competing targets) gives the same answers.

**Independent Test**: apply the migration to a database with org unit links, performer geographies, assessments, region scope and realization geographies; compare every read before and after.

**Acceptance Scenarios**:

1. **Given** the seeded geography, **Then** there are 249 places (countries) and a reference hierarchy "UN M49" with Global, 5 regions and memberships matching the old tree.
2. **Given** existing links to `geo-m49-150` (Europe) and `geo-DE`, **Then** they resolve to the same names and Europe still contains Germany.
3. **Given** a user-added region with countries under it, **Then** it becomes a node in a "Custom (migrated)" hierarchy with those countries as members, and links to it still work.
4. **Given** the reference hierarchy, **When** anyone tries to change it, **Then** it is refused as read-only.

---

### User Story 2 — Define a hierarchy with nodes and dated memberships (Priority: P1)

A compliance lead creates a regulatory hierarchy (DAG) with nodes EU, EEA and Eurozone. EEA contains EU plus Norway, Iceland and Liechtenstein; Ireland is in EU and Eurozone. The United Kingdom is a member of EU until 2020-01-31.

**Independent Test**: create the hierarchy, nodes and memberships; read it as of 2019-06-01 and as of today.

**Acceptance Scenarios**:

1. **Given** a DAG hierarchy, **When** Ireland is added to EU and to Eurozone, **Then** both are accepted.
2. **Given** a strict-tree hierarchy (sales), **When** a country already under NA is added under EMEA for an overlapping period, **Then** it is refused, naming NA; for a non-overlapping period it is accepted.
3. **Given** EEA contains EU, **When** someone adds EEA under EU, **Then** it is refused as a cycle.
4. **Given** UK in EU until 2020-01-31, **Then** reading as of 2019-06-01 shows UK under EU, and as of today does not.
5. **Given** a membership with an end date on or before its start date, **Then** it is refused.
6. **Given** a regulatory hierarchy, **When** a user without `write_compliance` writes to it, **Then** it is refused.
7. **Given** a hierarchy with a system of record, **Then** node and membership writes are refused.

---

### User Story 3 — Use any node anywhere a geography is used (Priority: P1)

An architect sets an org unit's operating geography to the sales node "APAC", records a regional assessment for the regulatory node "EU", and scopes a realization to a data-residency zone.

**Independent Test**: link nodes of several hierarchies in each place a geography is used, and check the derived views.

**Acceptance Scenarios**:

1. **Given** APAC (sales) containing Japan, **Then** a performer in Japan for an org unit operating in APAC has no outside-geography note.
2. **Given** a capability region-specific to Japan, **Then** it applies in an APAC column of the regional heat map and not in an EU column.
3. **Given** two target realizations scoped to EU (regulatory) and Germany, **Then** they are competing; EU and Brazil are not.
4. **Given** pickers, **Then** nodes are listed with their hierarchy ("APAC · Sales").

---

### User Story 4 — Browse hierarchies on the Geography screen (Priority: P2)

On Business → Organization → Geography the architect sees hierarchies grouped by kind, opens one, sees its nodes and members as of a chosen date, and (with permission) adds nodes and memberships with dates.

**Acceptance Scenarios**:

1. **Given** the screen, **Then** the reference hierarchy is shown read-only and other hierarchies are editable by those allowed.
2. **Given** an "as of" date, **Then** the tree/DAG shows only memberships valid on that date.

### Edge Cases

- A membership with no start date is valid since always; with no end date, open-ended. End dates are exclusive.
- Changing a hierarchy from DAG to strict tree is refused while any place or node has two parents at the same time.
- Deleting a node removes its memberships and cleans up its links exactly as deleting a geography does today; a hierarchy with nodes cannot be deleted.
- A node with no members covers no countries: it contains nothing and overlaps nothing (except itself and its descendants).
- A place is only "inside" a node through memberships (direct or via descendant nodes), never the other way round, so a region with one country does not count as contained by that country.
- Places cannot be created, renamed or deleted through the API (D3; GEO-04 seeds more).
- Global (`geo-001`, root of the reference hierarchy) stays refused where it is refused today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every existing geography id MUST keep resolving; countries become places, Global and the UN regions become nodes of a read-only reference hierarchy, and the old parent links become memberships with no dates.
- **FR-002**: Users MUST be able to create, rename, describe and delete hierarchies with a kind (regulatory, data residency, infrastructure, sales, tax, operational, custom) and a shape (strict tree or DAG). The reference kind is reserved for the seeded hierarchy.
- **FR-003**: Users MUST be able to create, rename and delete nodes in a hierarchy.
- **FR-004**: Users MUST be able to add memberships (a node or a place under a node of the same hierarchy) with optional start and end dates, change their dates, and remove them; several members can be added in one request.
- **FR-005**: Every write MUST keep the hierarchy valid: no cycles; in a strict tree at most one parent per member at any instant; end after start; no two overlapping memberships of the same pair.
- **FR-006**: Hierarchies with a system of record MUST refuse node and membership writes through these routes.
- **FR-007**: Writes to regulatory, data residency and tax hierarchies MUST require `write_compliance`; writes to the others require `write_business_arch`.
- **FR-008**: Reads MUST accept an "as of" date (default today) and show only memberships valid on it.
- **FR-009**: "Contains" and "overlaps" MUST be decided from memberships as of today, across all hierarchies: a place contains only itself; a node contains its descendants and any node whose countries are all among its own; two geographies overlap when one contains the other or they share a country.
- **FR-010**: The 941, 942 and 943 derived views MUST use FR-009, and MUST give unchanged results for data that only uses the old tree.
- **FR-011**: Today's link targets MUST accept any place or node (Q1). Global stays refused where it is refused today.
- **FR-012**: The Geography screen MUST list hierarchies by kind, show a hierarchy as of a date, and (for permitted users, writable hierarchies) edit nodes and memberships.
- **FR-013**: The organization export MUST include hierarchies, nodes and memberships with dates.
- **FR-014**: Every hierarchy, node and membership change MUST be logged with the actor.

### Key Entities

- **Place**: an atomic geography (a country in this cut), referenced by everything else.
- **Hierarchy**: a named, typed (kind) and shaped (strict tree or DAG) grouping, optionally mastered elsewhere (system of record).
- **Node**: a named grouping inside one hierarchy (Global, Europe, EU, APAC).
- **Membership**: a node or place under a node of the same hierarchy, valid from a date until a date.

## Success Criteria *(mandatory)*

- **SC-001**: After the upgrade, every pre-existing link and every derived view gives the same answer (existing test suites pass with only fixture changes).
- **SC-002**: An architect can model EU/EEA/Eurozone with Ireland in all three and the UK leaving the EU in 2020, and read it correctly as of any date, in under ten minutes.
- **SC-003**: No write can leave a cycle, or two simultaneous parents in a strict tree.

## Assumptions

- Dates are calendar dates (no time of day); end dates are exclusive.
- Cycles are checked over all memberships regardless of dates (simpler and stricter).
- Nodes have no ISO code; codes stay on places.
- The display "level" in API responses is kept for compatibility: 1 for Global, 2 for any other node, 3 for places.
- The import write path for system-of-record hierarchies is GEO-04.
