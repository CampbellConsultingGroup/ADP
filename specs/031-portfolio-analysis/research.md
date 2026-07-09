# Research: Portfolio Analysis Screen (ADP-SPEC-031)

## Decision 1: Backend Query Strategy for Technology Landscape (FR-001)

**Decision**: Use `GROUP BY technology, design_id` on `element_technology_tags`, then count distinct `design_id` per technology. Limit to 50. No JSONB scanning.

**Rationale**: The `element_technology_tags` table has a B-tree index on `technology`. A `SELECT technology, COUNT(DISTINCT design_id) AS design_count FROM element_technology_tags WHERE technology IS NOT NULL GROUP BY technology ORDER BY design_count DESC LIMIT 50` uses the index and returns in O(n) per unique technology. This satisfies SC-002 (under 2 seconds for 500 designs).

**Alternatives considered**: Scanning the JSONB content of design_versions to extract technology metadata on the fly — rejected because it requires a full table scan and defeats the purpose of the indexed table.

## Decision 2: Combined Filter Query Strategy (FR-002)

**Decision**: `GET /api/v1/portfolio/designs?technology=&status=` queries a JOIN between `element_technology_tags` (technology filter, indexed) and `designs` (lifecycle status filter, indexed). Returns `design_id` list, then loads `DesignSummary` data.

**Rationale**: Both filter columns have B-tree indexes. The JOIN is small (one row per design in `designs`, many rows per design in `element_technology_tags`). The combined query returns matching design IDs, then the API layer loads lifecycle fields from `designs` directly without JSONB parsing.

**SQL shape**:
```sql
SELECT DISTINCT ett.design_id
FROM element_technology_tags ett
JOIN designs d ON d.id = ett.design_id
WHERE ($technology IS NULL OR ett.technology ILIKE '%' || $technology || '%')
  AND ($status IS NULL OR d.lifecycle_status = $status)
ORDER BY d.created_at DESC LIMIT 50
```

## Decision 3: Dependency Search Implementation (FR-003)

**Decision**: Two-stage search. Stage 1: query `element_technology_tags` WHERE technology ILIKE `%term%` (indexed partial match). Stage 2: query design JSONB for element names containing the term (necessary since element names are not in the tags table). Merge results, cap at 200 unique design IDs.

**Rationale**: Technology values are in the indexed table (fast). Element names are only in JSONB (slow but bounded by the 200-result cap and the fact that this is a user-initiated one-time query, not a background process). The spec explicitly acknowledges this tradeoff in the assumptions.

## Decision 4: Portfolio Summary (FR-004)

**Decision**: Single SQL query: `SELECT lifecycle_status, COUNT(*) FROM designs GROUP BY lifecycle_status UNION ALL SELECT 'overdue_review', COUNT(*) FROM designs WHERE lifecycle_status = 'current' AND review_due < now()`.

**Rationale**: Both `lifecycle_status` and `review_due` have indexes. This is a single read pass over the `designs` table — sub-10ms for 500 designs.

## Decision 5: New App Route — "Portfolio" as Fifth View

**Decision**: Add `"portfolio"` to the `AppView` type in `web/src/shell/NavBar.tsx` and `App.tsx`. Portfolio screen is a fifth tab in the NavBar. The `currentDesignId` context is preserved but not required to access the Portfolio view.

**Rationale**: Portfolio analysis is design-agnostic (spans all designs). It fits as a peer to Designs, Intake, Recommendations, Canvas, and Knowledge rather than a sub-page of one design.

## Decision 6: No New Python Packages

**Decision**: Zero new packages. SQLAlchemy raw SQL with `sa.text()` for the aggregate queries, existing FastAPI pattern.

## Decision 7: Portfolio Page Component Structure

```
web/src/portfolio/
  PortfolioPage.tsx       — main layout, summary header, three panels
  TechnologyLandscape.tsx — technology chip grid
  PortfolioDesignList.tsx — filtered design list with lifecycle badges
  DependencySearch.tsx    — search input + results
```

Reuses `LifecycleTransitionButton` from ADP-SPEC-030 and `NavBar` from ADP-SPEC-025.
