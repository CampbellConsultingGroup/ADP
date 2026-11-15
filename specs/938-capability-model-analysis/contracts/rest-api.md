# REST contract: Capability Model Analysis (938)

All new routes are `GET`, which are open reads (`SAFE_METHODS`). Cost and risk content is gated inline by `READ_APPLICATION_COST` and `READ_APPLICATION_RISK` (research R3). Every response is computed on request.

## Changed: technical capabilities

`GET /api/v1/technical-capabilities` and `GET /api/v1/technical-capabilities/{id}` add two fields to each item:

```json
{ "lifecycle_status": "retiring", "end_of_life_date": "2027-06-30" }
```

`POST /api/v1/technical-capabilities` and `PATCH /api/v1/technical-capabilities/{id}` accept the same two fields. An existing write rule applies (`WRITE_APPLICATION`).
- An invalid status → 422.
- `"lifecycle_status": null` → 422.
- `"end_of_life_date": null` clears the date.

## New: `GET /api/v1/application-capabilities/analysis/business-rollup`

Query parameter: none. `as_of` is the server's current date.

```json
{
  "as_of": "2026-11-15",
  "risk_available": true,
  "cost_available": false,
  "items": [
    {
      "capability_id": "…", "level": 3,
      "contributing_apps": [{"id": "…", "name": "Oracle Retail Xstore POS",
                             "via": [{"id": "…", "name": "Basket Calculation"}]}],
      "excluded_retired_apps": [],
      "health":   {"worst": 2, "spread": {"1":0,"2":1,"3":0,"4":0,"5":0,"unassessed":0,"no_data":0}},
      "risk":     {"worst": "high", "spread": {"high":1,"medium":0,"low":0,"unknown":0,"no_data":0}},
      "cost":     null,
      "exposure": {"worst": "retiring", "spread": {"past_end_of_life":0,"retiring":1,"contained":0,"current":0,"emerging":0,"no_data":0}}
    }
  ]
}
```

- There is one item for every business capability, at every level.
- `risk` and `cost` are `null` on every item when the matching `*_available` flag is false. When the flag is true, `worst: null` means no data.
- `cost.total_tco` is a decimal string, matching how the existing cost endpoints serialise money.

## New: `GET /api/v1/application-capabilities/analysis/technical-capabilities/{tc_id}/impact`

- 404 if the technical capability doesn't exist.
- The body is an `ImpactResult` (data-model.md). Empty lists mean nothing depends on it.
- It contains no cost or risk fields.

## New: `GET /api/v1/application-capabilities/analysis/business-capabilities/{cap_id}/technology`

- 404 if the business capability doesn't exist.
- For an L1 or L2, it returns the union over its L3 descendants, each entry carrying `via_business_capability`.
- The body is `{"items": [TechnologyDependency]}`.

## New: `GET /api/v1/application-capabilities/analysis/findings`

The body is `CapabilityFindings` (data-model.md): `overlaps`, `gaps` (three lists) and `shared`. It contains no cost or risk fields.

## Route order

All four `/analysis/...` routes are registered before `/{ac_id}`. They have two or more segments, so they can't match `/{ac_id}` anyway, but registering them first keeps the 937 convention.
