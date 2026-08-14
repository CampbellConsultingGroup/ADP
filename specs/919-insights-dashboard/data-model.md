# Data Model: Insights Dashboard — Non-Architect Applications Heat Map

No new entities, tables, or columns. This feature is a read-only projection over two existing tables
(`applications`, `application_cost`, both from ADP-SPEC-038) via one new response model.

## Response model: `ApplicationHeatmapResponse`

Returned by the new `GET /api/v1/portfolio/applications-heatmap` endpoint.

| Field | Type | Source | Notes |
|---|---|---|---|
| `items` | `list[ApplicationHeatmapEntry]` | derived | One entry per application, unfiltered, unpaginated (demo scale). |
| `cost_permitted` | `bool` | derived | Whether the requesting user holds `READ_APPLICATION_COST` — decides whether "cost" is offered as a selectable dimension client-side (FR-004). |

### `ApplicationHeatmapEntry`

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | `str` | `applications.id` | |
| `name` | `str` | `applications.name` | Used for cell labeling and default sort order (Decision 5). |
| `health_score` | `int \| None` (1–5) | `applications.health_score` | `None` = unclassified (FR-005). |
| `business_criticality` | `int \| None` (1–5) | `applications.business_criticality` | `None` = unclassified. |
| `time_classification` | `str \| None` | `applications.time_classification` | One of `Tolerate`/`Invest`/`Migrate`/`Eliminate`; `None` = unclassified. |
| `cost` | `Decimal \| None` | `application_cost` (computed `tco`, Decision 4) | Always `None` when `cost_permitted` is `false` at the response level (FR-004), regardless of whether the application actually has a cost record — the caller must not be able to distinguish "no cost data" from "no permission" by field shape alone at this level (that distinction is only meaningful once `cost_permitted` is `true`). |

Both models use Pydantic v2 with `model_config = ConfigDict(extra="forbid")`, matching every existing router
model in this codebase (ART-XIII).

## Validation rules

- No new validation — every underlying field already validates at write time via the existing `Application`/
  `ApplicationCostUpdate` models (ADP-SPEC-038). This feature only reads.

## State transitions

- None — this feature has no lifecycle or mutable state of its own.
