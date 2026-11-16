# REST contract: Regional Assessments (942)

Base: `/api/v1/business`. Reads are open to every authenticated user. Writes need `WRITE_BUSINESS_ARCH` (the existing prefix rule); a reviewer gets 403. Served by `adp.organization.router`.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/regional-assessments?capability_id=` | — | 200 `RegionalAssessmentListResponse` | — |
| PUT | `/regional-assessments/{cap_id}/{geo_id}` | `{"maturity_level": 1-5 \| null, "note": str \| null}` | 200 `RegionalAssessment` | 404 capability or geography; 422 Global ("Global is the capability's baseline maturity"), neither score nor note, score outside 1–5, note > 1000 |
| DELETE | `/regional-assessments/{cap_id}/{geo_id}` | — | 204 | 404 |
| GET | `/regional-heatmap?geography_ids=a,b` | — | 200 `RegionalHeatmap` | 422 Global, unknown id, more than 12 columns |
| GET | `/capability-region-scope/{cap_id}` | — | 200 `RegionScope` | 404 |
| PUT | `/capability-region-scope/{cap_id}` | `{"region_specific": bool, "geography_ids": [..]}` | 200 `RegionScope` | 404 capability; 422 flagged with no geographies, Global, unknown geography |

Semantics:
- **PUT assessment** is an upsert: there is at most one assessment per capability and geography. A blank note is stored as null.
- **The global maturity** (`business_capabilities.maturity_level`) is never written by these routes.
- **Heat map columns**: omitted gives every region (geography level 2) by name; otherwise the given order, duplicates dropped.
- **Cell state**: `not_applicable` when the capability is region-specific and the column is outside its scope by containment; else `assessed` when an exact assessment exists; else `not_assessed`. `delta = maturity_level − baseline` when both exist.

Log lines (INFO, `adp.organization`):

```text
organization.regional_assessment.set    capability=<id> geography=<id> maturity=<n|None> note_chars=<n> created=<bool> actor=<sub>
organization.regional_assessment.remove capability=<id> geography=<id> actor=<sub>
organization.region_scope.set           capability=<id> region_specific=<bool> geographies=<ids> actor=<sub>
```
