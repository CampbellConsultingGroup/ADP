# REST contract: Org Units and Geography (940)

Every route is under `/api/v1/business/`. Writes need `WRITE_BUSINESS_ARCH` (the existing prefix rule); reads are open. Literal routes (`/org-units/unmatched…`) are declared before `/org-units/{id}`.

## Org units
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/org-units` | — | `{items: OrgUnit[], total}` |
| POST | `/org-units` | OrgUnitCreate | 201 OrgUnit · 404 parent/geography · 409 duplicate sibling · 422 depth |
| GET | `/org-units/{id}` | — | OrgUnit, with `applications: [{id,name}]` |
| PATCH | `/org-units/{id}` | OrgUnitUpdate | OrgUnit |
| DELETE | `/org-units/{id}` | — | 204 · 409 has children (applications' links are cleared) |
| POST | `/org-units/{id}/geographies` | `{geography_id}` | 201 OrgUnit · 404 · 409 duplicate |
| DELETE | `/org-units/{id}/geographies/{geography_id}` | — | 204 · 404 |

## Review queue
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/org-units/unmatched` | — | `{items: UnmatchedValue[], total}`, by count desc, then value |
| POST | `/org-units/unmatched/resolve` | `{value, org_unit_id}` or `{value, create:{name, description?, parent_id}}` | 200 `{org_unit, updated_count}` · 404 org unit · 422 both or neither given · 409/422 create errors |

## Geographies
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/geographies` | — | `{items: Geography[], total}` (about 255 rows) |
| POST | `/geographies` | GeographyCreate | 201 · 409 duplicate code or sibling · 422 depth or bad code |
| PATCH | `/geographies/{id}` | GeographyUpdate | Geography |
| DELETE | `/geographies/{id}` | — | 204 · 409 has children (links cascade; a primary geography pointing at it is cleared) |
| GET | `/geographies/{id}/org-units` | — | `OrgUnit[]` linked to it |

## Applications (changed)
`POST /api/v1/applications` and `PATCH /api/v1/applications/{id}` accept `owning_org_unit_id` (null clears it). An unknown id gives **422** `"Org unit '<id>' not found"`. `GET` returns the field.
