# Data Model: Regional Assessments (942)

## Stored (migration `050`, `down_revision = "049"`)

### `capability_regional_assessments`
| Column | Type | Rules |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `capability_id` | String(36) NOT NULL | FK `business_capabilities.id` ON DELETE CASCADE |
| `geography_id` | String(36) NOT NULL | FK `geographies.id` ON DELETE CASCADE |
| `maturity_level` | SmallInteger NULL | CHECK `maturity_level BETWEEN 1 AND 5` (`ck_regional_assessment_maturity`) |
| `note` | Text NULL | ≤ 1,000 chars (model); CHECK `note IS NULL OR length(note) <= 1000` |
| `created_at`, `updated_at` | timestamptz NOT NULL | |

- UNIQUE `uq_regional_assessment` `(capability_id, geography_id)`.
- CHECK `ck_regional_assessment_content`: `maturity_level IS NOT NULL OR note IS NOT NULL`.
- Index `ix_regional_assessment_geography` on `geography_id`.
- Store rule: the geography's `level` must be 2 or 3 (not Global).

### `region_specific_capabilities`
| Column | Type | Rules |
|---|---|---|
| `capability_id` | String(36) PK | FK `business_capabilities.id` ON DELETE CASCADE |
| `created_at` | timestamptz NOT NULL | |

### `region_specific_capability_geographies`
| Column | Type | Rules |
|---|---|---|
| `capability_id` | String(36) | FK `region_specific_capabilities.capability_id` ON DELETE CASCADE |
| `geography_id` | String(36) | FK `geographies.id` ON DELETE CASCADE |
| `created_at` | timestamptz NOT NULL | |

- PK `(capability_id, geography_id)`.
- Store rule: geography level 2 or 3; at least one geography when flagged (checked on PUT; a later geography delete may leave none, giving "scope needs updating").

The mirror `business_capabilities` on the organization metadata gains `maturity_level` (Integer, nullable).

## Pydantic models (`adp.organization.models`)

```text
GeoRef                  id, name, level, code: str | None
RegionalAssessment      id, capability_id, geography: GeoRef, maturity_level: 1..5 | None,
                        note: str | None, updated_at
SetRegionalAssessment   maturity_level: Literal[1..5] | None = None, note: str | None (max_length 1000,
                        blank -> None); validator: at least one present          # extra="forbid"
RegionalAssessmentListResponse  items, total
SetRegionScope          region_specific: bool, geography_ids: list[str] = []
                        validator: region_specific -> geography_ids non-empty; not region_specific -> []
RegionScope             capability_id, region_specific: bool, geographies: list[GeoRef], scope_needs_update: bool
```

Heat map (derived):

```text
HeatmapCell     geography_id, state: "assessed" | "not_assessed" | "not_applicable",
                maturity_level: int | None, note: str | None, delta: int | None
HeatmapRow      capability: {id, name, level, parent_id}, baseline: int | None,
                region_specific: bool, scope_needs_update: bool, cells: list[HeatmapCell]  # one per column, in column order
RegionalHeatmap columns: list[GeoRef], rows: list[HeatmapRow], max_columns: 12
```

## Snapshot (`regional.build_snapshot`, 4 queries)

```text
RegionalSnapshot(frozen):
  capabilities: {id: CapNode(+ baseline)}      geographies: {id: GeoNode(+ code)}
  assessments: {(cap_id, geo_id): (id, maturity, note, updated_at)}
  scopes: {cap_id: frozenset[geo_id]}          # key present = region-specific
```

## Export (`business-architecture/capabilities/<id>.json`)

```json
"regional": {
  "region_specific": false,
  "scope": [{"id": "geo-BR", "name": "Brazil"}],
  "scope_needs_update": false,
  "assessments": [{"geography": {"id": "geo-m49-150", "name": "Europe", "code": null},
                   "maturity_level": 4, "note": null}]
}
```
