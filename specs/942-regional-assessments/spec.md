# Feature Specification: Regional Assessments — capability maturity by region, on one capability model

**Feature Branch**: `942-regional-assessments`
**Created**: 2026-11-16
**Status**: Draft
**Bead**: ADP-55k.3 (spec 3 of 4 in epic ADP-55k; depends on 940, merged in PR #147)
**Input**: User description: "942 regional-assessments (ADP-55k.3)". The epic's notes hold the user's source notes and decisions.

## Background and Resolved Decisions

The user's notes (2026-11-15, in ADP-55k) say a capability is modelled once, and that how well it is performed can differ by region: "A capability can be L4 in North America and L2 in Southeast Asia, and the heat map shows it without duplicating the capability." Where a capability genuinely differs by region (tax compliance, e-invoicing, data privacy), they want a regional variant **note**, not a separate capability. A capability that only exists in some places (a country-specific regulatory function) is modelled once and **flagged region-specific**.

Spec 940 supplies the geography tree (global → region → country). This spec adds the per-region assessments on top.

| # | Decision |
|---|---|
| D6 (epic) | Per-region assessments in v1 are **maturity only**, on the same 1–5 scale as the capability's existing global maturity. Global maturity stays the **enterprise baseline**. Each assessment may carry a **regional variant note**. A capability can be flagged **region-specific**. A **regional heat map** shows capability × region. |
| N1 | Performance, cost and application support per region are **out of scope** for v1 (the epic's "maturity only" decision). |

Ground-truth checks against the code (main at 220ecb3, migration head `049`):

| # | Fact | Consequence |
|---|---|---|
| GT-1 | Business capabilities have `maturity_level`, 1–5, labelled Ad hoc / Emerging / Established / Advanced / World Class, and nullable "Not assessed" (`src/adp/business/models.py:34`) | Regional maturity uses the same scale and labels. The global value is the baseline and is not changed by this feature |
| GT-2 | Geographies (940) are a 3-level tree: Global (1) → 5 UN M49 regions (2) → about 250 countries (3), all editable (`src/adp/organization/store.py`) | An assessment can name a region or a country, never Global itself (that is the baseline) |
| GT-3 | The existing Heat Map tab (`web/src/business/CapabilityHeatMap.tsx`) is a one-dimensional grid of capability cells coloured by one metric. The codebase's two-dimensional matrices are `<table>` grids (`web/src/strategy/StrategyHeatMap.tsx`, `web/src/portfolio/CrossTabGrid.tsx`) | The regional heat map is a capability × geography matrix, reached from the Heat Map tab |
| GT-4 | Writes under `/api/v1/business/` require `WRITE_BUSINESS_ARCH` (`src/adp/authz/enforcement.py:161`) | No new permission |
| GT-5 | Business capabilities have no region-related field today | The region-specific flag and everything else here is new; nothing to migrate |
| GT-6 | 941 put owner and performer mappings on capabilities. A performer may name a geography | Regional assessments are independent of performers. The heat map can *show* which geographies have performers, but an assessment never requires one |

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies)
- **ART-IV** — Test-Driven Development: (always applies)
- **ART-II** — Single Source of Truth: one capability, one global baseline, and per-region assessments as an overlay. Nothing is copied per region.
- **ART-V** — Security by Design: writes use the existing `WRITE_BUSINESS_ARCH` gate. Maturity scores and notes aren't sensitive.
- **ART-IX** — Auditability: every assessment create, change and removal, and every change to the region-specific flag, is logged with the actor.
- **ART-XIII** — Typed Contracts: maturity is the closed 1–5 set; the note has a length limit.
- **ART-XV** — Schema Evolution: one reversible migration (`050`).
- **ART-VII** (AI grounding): not engaged.

## Threat Model *(mandatory — ART-V)*

Low risk. Maturity scores and free-text notes about how a capability differs by region are ordinary architecture data, readable by every platform user like the rest of Business Architecture. Writes need `WRITE_BUSINESS_ARCH`. Notes are plain text, rendered as text, never as markup.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Record maturity per region (Priority: P1)

An enterprise architect opens "Process Payroll" and records that it is Advanced (4) in Europe and Emerging (2) in Brazil, while the global baseline stays Established (3). They add a note on the Brazil assessment: "eSocial reporting is run manually."

**Why this priority**: the regional assessment is the core of this spec. The heat map and comparison only have something to show once assessments exist.

**Independent Test**: add, change and remove regional assessments on a capability for a region and a country; confirm the global maturity is untouched and that Global itself can't be assessed.

**Acceptance Scenarios**:

1. **Given** a capability with global maturity Established, **When** an architect records Advanced for Europe, **Then** the assessment is saved and shown with its region, and the global maturity is still Established.
2. **Given** an existing assessment for Europe, **When** the architect changes it to World Class, **Then** there is still exactly one Europe assessment for that capability, now World Class.
3. **Given** a country (Brazil), **When** the architect records Emerging with a note, **Then** both the score and the note are saved.
4. **Given** the Global geography, **When** someone tries to assess against it, **Then** it is refused with a message saying the global maturity is the capability's baseline.
5. **Given** an assessment, **When** it is removed, **Then** it disappears and the removal is logged.
6. **Given** an assessment with a note but no score, **When** it is saved, **Then** it is accepted as "not assessed" in that region, but with a recorded variant.

---

### User Story 2 — Flag a region-specific capability (Priority: P2)

The architect flags "Statutory eSocial Reporting" as region-specific, applying only in Brazil.

**Why this priority**: it stops a country-only capability looking like a gap everywhere else, but it's a smaller need than the assessments themselves.

**Independent Test**: flag a capability as region-specific with one or more applicable geographies, clear the flag, and confirm the heat map treats geographies outside its scope as "not applicable" rather than "not assessed".

**Acceptance Scenarios**:

1. **Given** any capability, **When** the architect marks it region-specific and picks the geographies it applies in, **Then** the flag and the geographies are saved and shown on the capability.
2. **Given** a region-specific capability, **When** it is viewed for a geography outside its scope, **Then** it is shown as "not applicable", not "not assessed".
3. **Given** a capability applying in Brazil, **When** it is viewed for the Americas region, **Then** it counts as applicable there, because Brazil is inside the Americas.
4. **Given** a region-specific flag with no geographies, **When** it is saved, **Then** it is refused: a region-specific capability must name at least one geography.
5. **Given** a region-specific capability, **When** the flag is cleared, **Then** its applicable geographies are removed too, and it applies everywhere again.

---

### User Story 3 — Compare regions on a heat map (Priority: P1)

The architect opens the regional heat map: capabilities down the side, in the usual L1 → L2 → L3 order; the five regions across the top; each cell coloured by that region's maturity. They add Germany and Brazil as extra columns to compare two countries.

**Why this priority**: the heat map is how the user wants to *see* regional differences ("the heat map shows it without duplicating the capability").

**Independent Test**: with assessments for two regions and one country, open the heat map, confirm each cell shows the right score, colour and state (assessed, not assessed, not applicable), add and remove a country column, and confirm the global baseline column is always shown.

**Acceptance Scenarios**:

1. **Given** assessments exist, **When** the heat map opens, **Then** it shows a baseline column (global maturity) plus one column per region, and each cell is coloured by that region's maturity with its label.
2. **Given** a cell with no assessment, **When** it is shown, **Then** it reads "Not assessed", visibly distinct from any score.
3. **Given** a region-specific capability, **When** shown in a column outside its scope, **Then** the cell reads "Not applicable".
4. **Given** a regional score differs from the baseline, **When** the cell is shown, **Then** it indicates whether it is above or below the baseline.
5. **Given** the column picker, **When** the architect adds Germany and Brazil, **Then** those columns appear, and the choice survives switching tabs during the session.
6. **Given** a cell with a variant note, **When** the architect hovers or focuses it, **Then** the note is shown; and clicking any cell lets an architect with write access record or change that assessment.
7. **Given** an L1 or L2 row, **When** the heat map shows it, **Then** it shows that capability's own assessment, if any, and never an average of its children.

---

### User Story 4 — Assessments travel with exports and the demo data (Priority: P3)

Exported capability files carry their regional assessments and region-specific scope, and the retail seed includes a regional example.

**Why this priority**: the file export is how AI tools and other consumers read the architecture; the seed is how the feature is demonstrated.

**Independent Test**: assess a capability, run the export and read its file; reseed and confirm the heat map shows at least two regions with differing scores and one region-specific capability.

**Acceptance Scenarios**:

1. **Given** assessed capabilities, **When** the export runs, **Then** each capability's file lists its regional assessments (geography, score, note) and its region-specific scope.
2. **Given** the retail seed, **When** it is loaded, **Then** the heat map shows differing regional scores and at least one region-specific capability.

---

### Edge Cases

- **Region and country both assessed** (Europe Advanced, Germany Emerging): both are shown as recorded. Neither overrides or averages the other; a country cell never inherits its region's score.
- **Deleting a geography** removes its assessments, and removes it from any region-specific scope. If that leaves a region-specific capability with no geographies, it stays flagged but is shown as "scope needs updating".
- **Deleting a capability** removes its assessments and scope.
- **A capability with no global maturity**: the baseline cell reads "Not assessed". Regional cells show their scores with no above/below indicator.
- **Applicability by containment**: a capability applying in Brazil is applicable in the Americas column. A capability applying in the Americas is applicable in its countries' columns too.
- **Many columns**: the picker allows up to 12 geography columns, and the matrix scrolls sideways inside its own area rather than widening the page.
- **Long notes** are truncated in cells and shown in full on hover or focus. Notes are limited to 1,000 characters.

## Requirements *(mandatory)*

### Functional Requirements

**Assessments**

- **FR-001**: The system MUST let an authorized user record, change and remove a **regional assessment** of a business capability for one geography at the region or country level. Each assessment holds a maturity score (1–5, the same scale as global maturity) and/or a variant note.
- **FR-002**: There MUST be at most one assessment per capability and geography. Recording again changes the existing one.
- **FR-003**: The system MUST refuse an assessment against the top-level Global geography, and an assessment with neither a score nor a note, each with a message naming the rule.
- **FR-004**: Regional assessments MUST NOT change the capability's global maturity, and the global maturity MUST NOT change any regional assessment.
- **FR-005**: Variant notes MUST be plain text of at most 1,000 characters.

**Region-specific scope**

- **FR-006**: The system MUST let an authorized user mark a capability **region-specific** and set the geographies (regions or countries) it applies in. A region-specific capability MUST name at least one geography; clearing the flag removes the geographies.
- **FR-007**: A region-specific capability is **applicable** in a geography when that geography is one of its geographies, is inside one of them, or contains one of them. Everywhere else it is **not applicable**.

**Heat map**

- **FR-008**: The system MUST provide a regional heat map: capabilities as rows in hierarchy order, a baseline column showing global maturity, and one column per chosen geography.
- **FR-009**: The default columns MUST be the regions. Users MUST be able to add or remove region and country columns, up to 12, and the choice MUST persist while the user stays in the session.
- **FR-010**: Each cell MUST show one of: an assessed score (coloured, labelled, with above/below-baseline indication when the baseline exists), "Not assessed", or "Not applicable". A cell with a note MUST show the note on hover or focus.
- **FR-011**: Users with write access MUST be able to record or change an assessment from a heat map cell. Read-only users see the same matrix without edit controls.
- **FR-012**: Each cell MUST reflect only that capability's own assessment for that exact geography. There is no roll-up across levels and no inheritance between regions and countries.

**Surfaces, audit, export, seed**

- **FR-013**: A capability's regional assessments and region-specific scope MUST also be viewable and editable from its row on the Capabilities tab.
- **FR-014**: Every assessment create, change and removal, and every region-specific flag or scope change, MUST be logged with the actor, capability and geography.
- **FR-015**: Deleting a geography MUST remove its assessments and its place in any region-specific scope. Deleting a capability MUST remove its assessments and scope.
- **FR-016**: The capability export MUST include its regional assessments (geography, score, note) and region-specific scope.
- **FR-017**: The retail seed MUST include assessments that differ by region and at least one region-specific capability.

### Key Entities

- **Regional Assessment**: one business capability × one geography (region or country): a maturity score (1–5, optional) and a variant note (optional, at least one present). Unique per capability and geography.
- **Region-specific scope**: a flag on a business capability plus the set of geographies it applies in (at least one when flagged).
- **Applicability** (derived): whether a capability applies in a given geography, from its scope and the geography tree.
- **Regional heat map cell** (derived): a capability × geography state: assessed (score, note, versus baseline), not assessed, or not applicable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An architect can record a regional maturity score and note for a capability in under 30 seconds, from either the heat map or the capability row.
- **SC-002**: The heat map for 300 capabilities and 12 geography columns opens in under 2 seconds.
- **SC-003**: For any capability and geography on the heat map, a user can tell at a glance whether it is assessed (and how it compares with the baseline), not assessed, or not applicable.
- **SC-004**: Recording or changing regional assessments leaves 100% of global maturity values unchanged (test-enforced).
- **SC-005**: No capability is ever duplicated to represent a region; the number of capabilities is unchanged by any regional activity.

## Assumptions

- **Assessments name a region or a country.** Global is excluded because it is what the capability's own maturity already describes.
- **No roll-up and no inheritance** (FR-012). A region's score is not derived from its countries, and a country does not inherit its region's score. This keeps the data honest: an assessment is only shown where someone made it.
- **A note can exist without a score**, so an architect can record a variant ("eSocial reporting is manual") before assessing maturity there.
- **Region-specific scope uses the same geography tree** and containment rules in both directions (FR-007), so a Brazil-only capability shows as applicable in the Americas column.
- **Column choice persists for the session only**, as a per-viewer convenience; saved views are out of scope.
- **The heat map lives with the existing Heat Map tab** on Business Architecture, as a second, regional view.
- Volume: hundreds of capabilities, up to a few thousand assessments.

## Out of Scope (follow-ons)

- Regional performance, cost and application-support scores (epic N1; maturity only in v1).
- Roll-ups of regional maturity from L3 to L2/L1, or from countries to regions.
- Assessment history or dated assessments.
- Linking regional assessments to 941's performer geographies, beyond optionally showing them.
- Mapping rationale on application realizations (spec 943).
