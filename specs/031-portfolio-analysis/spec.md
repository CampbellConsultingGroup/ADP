# Feature Specification: Portfolio Analysis Screen

**Feature Branch**: `031-portfolio-analysis`
**Created**: 2026-07-05
**Status**: Draft
**Depends on**: ADP-SPEC-029 (Element Technology Tagging), ADP-SPEC-030 (Design Lifecycle)
**Prerequisite for**: ADP-SPEC-032 (Governance Reporting Dashboard) — shares the portfolio navigation pattern

## Context

ADP now has 029 and 030 deployed: every element can carry structured technology metadata, and every design has a lifecycle status. But this data is currently invisible at the portfolio level — an architect must open each design individually to discover what technologies it uses or what its lifecycle status is.

Enterprise architects need portfolio-level visibility: "what does our technology landscape look like?", "which designs are still in draft and should be proposed?", "which designs share a dependency on our legacy authentication service?". These questions cannot be answered by looking at one design at a time.

This spec adds a Portfolio Analysis screen — a fifth view in the ADP navigation — that aggregates data from all designs and surfaces it in three panels: a technology landscape view, a combined filter on technology + lifecycle status, and a cross-design dependency panel.

## Constitutional Articles Touched

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — Model is Source of Truth: all data in the portfolio view is read from the canonical model and its derived indexes (element_technology_tags, designs table lifecycle columns); no separate portfolio data store
- **ART-IV** — Test-Driven Development: always applies
- **ART-VII** — Grounded AI: portfolio queries surface which designs are grounded in which knowledge items (via grounded_on citations from accepted recommendations)

## Threat Model

**Assets at risk**: The portfolio view reveals the full technology estate — platform choices, team ownership, end-of-life systems — which is sensitive infrastructure intelligence.

**Trust boundaries crossed**: Browser → ADP API (portfolio query endpoints). No new external boundaries.

**Abuse cases**:
- Mass extraction of the technology landscape: mitigated by requiring authentication (ADP-SPEC-026) on all portfolio endpoints.
- Denial of service via expensive cross-portfolio queries: mitigated by query result caps (max 500 designs per query, indexed columns only — no JSONB full-scans).

**Residual risk**: No per-design access control in v1. Any authenticated user can see the full portfolio. Accepted for single-tenant deployment.

## User Scenarios & Testing

### User Story 1 — View the Technology Landscape Across All Designs (Priority: P1)

An enterprise architect opens the Portfolio screen and immediately sees a summary of every technology in use across the architecture estate, sorted by the number of designs that use it. She can see "Apache Kafka appears in 7 designs, AWS EKS in 12 designs, Kong in 3 designs". Clicking a technology filters the design list to only those designs.

**Why this priority**: The technology landscape is the single most requested portfolio view from enterprise architecture practices — it directly enables technology standardisation and deduplication decisions.

**Independent Test**: With 3 designs tagged with `technology=Kafka` and 2 with `technology=RabbitMQ`, the technology landscape shows Kafka (3) and RabbitMQ (2); clicking Kafka filters the list to 3 designs.

**Acceptance Scenarios**:

1. **Given** elements across multiple designs have technology metadata, **When** the Portfolio screen loads, **Then** the technology landscape panel shows each distinct technology value with a count of how many designs contain at least one element with that technology.
2. **Given** a technology is shown in the landscape, **When** an architect clicks it, **Then** the design list below filters to only designs containing an element with that technology.
3. **Given** no designs have technology tags, **Then** the landscape panel shows "No technology tags recorded yet — add tags to elements using the Canvas inspection panel."

---

### User Story 2 — Filter Designs by Technology and Lifecycle Status (Priority: P1)

An architect wants to find all Current designs using Kong. She selects "Current" from the lifecycle filter and clicks "Kong" in the technology landscape. The design list narrows to only Current designs that contain a Kong-tagged element.

**Why this priority**: Combined filters are the primary portfolio rationalization workflow — technology alone or lifecycle alone tells half the story.

**Acceptance Scenarios**:

1. **Given** designs in multiple lifecycle states with various technology tags, **When** an architect selects a lifecycle status AND a technology, **Then** only designs matching both criteria are shown.
2. **Given** a combined filter is active, **When** the architect clears one filter, **Then** only the other filter remains active.
3. **Given** a combined filter returns zero results, **Then** a clear "No designs match these filters" empty state is shown with instructions to clear filters.

---

### User Story 3 — Cross-Design Dependency Search (Priority: P2)

An architect is planning the decommission of a shared authentication service. She wants to know which designs reference it. She types "Auth Service" in the dependency search box and sees a list of all designs that contain an element with that name (or a name containing that string).

**Why this priority**: Dependency impact analysis is the second most common portfolio query. It requires cross-design search by element name, which the element_technology_tags index supports.

**Acceptance Scenarios**:

1. **Given** a search term is typed in the dependency search box, **When** results load, **Then** the design list shows only designs containing at least one element whose name or technology value contains the search term (case-insensitive).
2. **Given** search results show designs, **Then** each result row shows which element(s) matched and their technology metadata.
3. **Given** no elements match the search term, **Then** an empty state is shown.

---

### User Story 4 — Portfolio Summary Header (Priority: P2)

At the top of the Portfolio screen, a summary row shows: total designs, count by each lifecycle status, and count of designs with overdue reviews. This gives an at-a-glance health check of the architecture estate.

**Acceptance Scenarios**:

1. **Given** designs in various lifecycle states, **When** the Portfolio screen loads, **Then** the summary header shows total designs and a count for each of the five lifecycle statuses.
2. **Given** designs with overdue `review_due` dates, **Then** the summary shows "N overdue" in amber with a count.
3. **Given** no designs exist, **Then** the header shows zeroes for all counts without error.

---

### Edge Cases

- Portfolio with 0 designs: all panels show appropriate empty states; no errors.
- Technology values with special characters (slashes, quotes): filtered correctly; no injection.
- Portfolio with 500+ designs: queries return paginated results (default 50); load-more or pagination controls shown.
- Designs without any technology tags: appear in the design list but not in the technology landscape.
- Search with very short terms (1 character): permitted but results may be large; result cap (200) shown as notice.

## Requirements

### Functional Requirements

**Portfolio Query API (FR-001 to FR-005)**

- **FR-001**: `GET /api/v1/portfolio/technologies` MUST return a list of `{technology: string, design_count: int}` objects aggregated from the `element_technology_tags` table, ordered by `design_count` descending, capped at the 50 most-used technologies.
- **FR-002**: `GET /api/v1/portfolio/designs` MUST accept optional query parameters `technology` (string, partial match) and `status` (lifecycle status, exact match) and return matching design summaries including lifecycle fields and element count. Queries use indexed columns only — no JSONB scans.
- **FR-003**: `GET /api/v1/portfolio/search?q=` MUST accept a search term and return designs containing elements whose `name` or `technology` value contains the term (case-insensitive, using the indexed `element_technology_tags` table and design element JSONB for name matching). Returns at most 200 results.
- **FR-004**: `GET /api/v1/portfolio/summary` MUST return counts by lifecycle status, total designs, and count of designs with `review_due < now()` and `lifecycle_status = 'current'`.
- **FR-005**: All portfolio endpoints MUST respond in under 2 seconds for a portfolio of up to 500 designs.

**Portfolio Screen (FR-006 to FR-012)**

- **FR-006**: A new "Portfolio" navigation tab MUST be added as a fifth item in the `NavBar` component, visible to all authenticated users.
- **FR-007**: The Portfolio screen MUST display a summary header showing total designs and counts per lifecycle status (FR-004).
- **FR-008**: The Portfolio screen MUST display a technology landscape panel showing the top technologies across the portfolio (FR-001), each as a clickable chip that activates a technology filter.
- **FR-009**: The Portfolio screen MUST display a design list (FR-002) that responds to active technology and lifecycle status filters. Each row shows design title, lifecycle status badge, element count, and the primary technology tag (if set on any element).
- **FR-010**: The Portfolio screen MUST provide a lifecycle status filter dropdown (same options as the Designs screen from ADP-SPEC-030).
- **FR-011**: The Portfolio screen MUST provide a dependency search input (FR-003) that shows matching designs with the matched element names highlighted.
- **FR-012**: Each design row in the Portfolio screen MUST have an "Open" button that navigates the user to the Intake view for that design (consistent with the Designs screen behaviour).

### Key Entities

- **TechnologyCount**: `technology: str`, `design_count: int`
- **PortfolioDesignSummary**: `id`, `title`, `lifecycle_status`, `element_count`, `primary_technology` (the first technology value found on any element), `overdue_review: bool`
- **PortfolioSummary**: `total_designs`, `by_status: dict[str, int]`, `overdue_review_count: int`

## Success Criteria

- **SC-001**: An architect can answer "which designs use Kafka?" by clicking the Kafka chip in the technology landscape in under 3 clicks and under 2 seconds.
- **SC-002**: All portfolio query API endpoints respond in under 2 seconds for a portfolio of 500 designs.
- **SC-003**: The dependency search correctly identifies all designs containing a matching element name when tested against a seeded portfolio.
- **SC-004**: The technology landscape counts are accurate — each technology's count reflects the actual number of distinct designs with at least one element tagged with that technology.

## Assumptions

- Technology landscape shows the top 50 technologies only (long tail is accessible via dependency search).
- The `element_technology_tags` table from ADP-SPEC-029 is the data source for all technology queries — no JSONB scanning of design content for technology data.
- Element name search for the dependency panel queries the JSONB content (since element names are not indexed separately). This is acceptable as the search is user-initiated and result-capped at 200.
- Pagination is 50 designs per page in the filtered design list; a "Load more" button is sufficient for v1.
- The Portfolio screen does not support editing — it is a read-only view. All edits happen via the Canvas and Designs screens.
