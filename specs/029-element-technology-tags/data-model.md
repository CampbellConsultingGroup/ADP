# Data Model: Element Technology Tagging (ADP-SPEC-029)

## New: `TechnologyMetadata` (Pydantic model — embedded in Element)

Nested object added to the canonical `Element` model. Stored as part of the element within the design's JSONB content column. Source of truth for exports.

| Field | Type | Required | Constraints | Notes |
|---|---|---|---|---|
| technology | string | No | max 200 chars | Primary technology name (e.g. "Apache Kafka") |
| vendor | string | No | max 200 chars | Technology vendor (e.g. "Confluent") |
| platform | string | No | max 200 chars | Hosting platform (e.g. "AWS EKS") |
| version | string | No | max 50 chars | Technology version (e.g. "3.4.1") |
| owner_team | string | No | max 200 chars | Responsible team (e.g. "Platform Engineering") |

The `Element.tags: list[str]` field already on the model serves as the free-form tags from US2 (max 50 chars each per FR-002). No change to that field needed.

`TechnologyMetadata` is optional on `Element` — absence means no technology metadata has been set (backward compatible, ART-XV).

## New: `element_technology_tags` (PostgreSQL table — queryable index)

Derived from the canonical model; populated/updated whenever tags are saved. Not the source of truth — the JSONB in `design_versions` is. Enables FR-009 cross-portfolio queries.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| design_id | TEXT | NOT NULL | Design that owns this element |
| element_id | TEXT | NOT NULL | Element within the design |
| technology | TEXT | nullable | Indexed (B-tree) |
| vendor | TEXT | nullable | |
| platform | TEXT | nullable | Indexed (B-tree) |
| version | TEXT | nullable | |
| owner_team | TEXT | nullable | Indexed (B-tree) |
| free_tags | JSONB | NOT NULL DEFAULT '[]' | Indexed (GIN) — free-form tag list |
| updated_at | TIMESTAMPTZ | NOT NULL | |

**Primary key**: `(design_id, element_id)`
**Indexes**:
- B-tree on `technology` — "find all elements using Kafka"
- B-tree on `platform` — "find all elements on AWS EKS"
- B-tree on `owner_team` — "find all elements owned by Platform Engineering"
- GIN on `free_tags` — "find all elements tagged 'legacy'"

## Changes to Existing Models

### `Element` (src/adp/models.py)

**Add** optional field:
```
technology_metadata: TechnologyMetadata | None = None
```

The existing `tags: list[str]` field on `Element` is unchanged and continues as the free-form tags.

### `ArchitectureDescription`

No changes. Technology metadata travels with elements inside the JSONB content.

## Relationships

```
ArchitectureDescription (1) ──── (many) Element
Element (1) ──────────────────── (0..1) TechnologyMetadata  [nested in JSONB]
Element (1) ──────────────────── (0..1) element_technology_tags row  [indexed table]
```

The `element_technology_tags` table row is always in sync with the `TechnologyMetadata` in the corresponding JSONB version. Sync happens on every `PUT /tags` write.
