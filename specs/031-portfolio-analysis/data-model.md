# Data Model: Portfolio Analysis Screen (ADP-SPEC-031)

## Read-Only Aggregated Entities (no new tables)

All portfolio data is derived from existing tables. No new schema migrations required.

### TechnologyCount

Aggregated from `element_technology_tags`. Returned by `GET /api/v1/portfolio/technologies`.

| Field | Type | Source |
|---|---|---|
| technology | string | `element_technology_tags.technology` |
| design_count | int | `COUNT(DISTINCT design_id)` per technology |
| platform | string \| null | Most common platform value for this technology (optional enrichment) |

### PortfolioDesignSummary

Returned by `GET /api/v1/portfolio/designs`. Joins `designs` table (lifecycle fields) with `element_technology_tags` (technology match).

| Field | Type | Source |
|---|---|---|
| id | string | `designs.id` |
| title | string | `designs.title` |
| lifecycle_status | string | `designs.lifecycle_status` |
| overdue_review | bool | computed: status='current' AND review_due < now() |
| element_count | int | `COUNT(elements)` from design JSONB or cached |
| primary_technology | string \| null | First technology value in `element_technology_tags` for this design |
| matched_elements | list[string] | Only in search results — element names that matched the search term |

### PortfolioSummary

Returned by `GET /api/v1/portfolio/summary`. Pure aggregation over `designs` table.

| Field | Type | Source |
|---|---|---|
| total_designs | int | `COUNT(*)` from `designs` |
| by_status | dict[str, int] | `GROUP BY lifecycle_status` |
| overdue_review_count | int | `WHERE lifecycle_status='current' AND review_due < now()` |

## Data Sources (no migrations needed)

| Source Table | Used For |
|---|---|
| `element_technology_tags` | Technology landscape, technology filter in design list, dependency search |
| `designs` | Lifecycle status filter, summary counts, overdue indicator |
| `design_versions.content` (JSONB) | Element name search only (dependency search stage 2) |

## TypeScript Interfaces

```typescript
// web/src/api/portfolio.ts (new file)
interface TechnologyCount { technology: string; design_count: number; }
interface PortfolioDesignSummary {
  id: string; title: string; lifecycle_status: string;
  overdue_review: boolean; element_count: number;
  primary_technology: string | null;
  matched_elements?: string[];  // only in search results
}
interface PortfolioSummary {
  total_designs: number;
  by_status: Record<string, number>;
  overdue_review_count: number;
}
```
