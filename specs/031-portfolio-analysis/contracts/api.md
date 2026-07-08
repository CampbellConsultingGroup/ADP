# API Contracts: Portfolio Analysis Screen (ADP-SPEC-031)

All endpoints are read-only. No schema migrations required.

---

## GET /api/v1/portfolio/technologies

Returns top 50 technologies aggregated from `element_technology_tags`.

**Auth**: Bearer token required.

**Response 200**:
```json
{
  "technologies": [
    { "technology": "Apache Kafka", "design_count": 7 },
    { "technology": "AWS EKS", "design_count": 12 },
    { "technology": "Kong", "design_count": 3 }
  ],
  "total_unique": 23
}
```

**Notes**: Technologies with null values excluded. Sorted by `design_count` descending. Capped at 50.

---

## GET /api/v1/portfolio/designs

Returns designs matching optional technology and/or lifecycle status filter.

**Auth**: Bearer token required.

**Query parameters**:
- `technology` (optional, string): case-insensitive partial match on technology value in `element_technology_tags`
- `status` (optional, string): exact match on `designs.lifecycle_status`
- `page` (optional, integer, default 1, max 10000)
- `page_size` (optional, integer, default 50, max 200)

**Response 200**:
```json
{
  "designs": [
    {
      "id": "DSN-001",
      "title": "Payment Platform",
      "lifecycle_status": "current",
      "overdue_review": true,
      "element_count": 8,
      "primary_technology": "Kong"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 50
}
```

---

## GET /api/v1/portfolio/search

Cross-design element search by name or technology.

**Auth**: Bearer token required.

**Query parameters**:
- `q` (required, string, min 2 chars): search term matched case-insensitively against element names and technology values

**Response 200**:
```json
{
  "designs": [
    {
      "id": "DSN-002",
      "title": "Auth Platform",
      "lifecycle_status": "deprecated",
      "overdue_review": false,
      "element_count": 5,
      "primary_technology": "Keycloak",
      "matched_elements": ["Auth Service (technology: Keycloak)", "User DB (name match)"]
    }
  ],
  "total": 2,
  "truncated": false
}
```

**Response 422**: `q` is missing or shorter than 2 characters.

**Notes**: Results capped at 200 unique designs. `truncated: true` when cap is hit.

---

## GET /api/v1/portfolio/summary

Portfolio health summary — aggregated counts.

**Auth**: Bearer token required.

**Response 200**:
```json
{
  "total_designs": 15,
  "by_status": {
    "draft": 3,
    "proposed": 2,
    "current": 8,
    "deprecated": 1,
    "decommissioned": 1
  },
  "overdue_review_count": 2
}
```
