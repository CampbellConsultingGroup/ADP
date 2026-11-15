# REST API: Application Capabilities (937)

Base: `/api/v1/application-capabilities`. Writes need `WRITE_APPLICATION` (prefix rule). GETs need platform read access only.
Literal segments (`by-*`) are registered before `/{ac_id}`.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `` (`?warning=missing_technical_capability`) | | 200 `{items: ApplicationCapability[], total}` | |
| POST | `` | `ApplicationCapabilityCreate` | 201 `ApplicationCapability` | 404 parent, 409 sibling name, 422 depth/blank |
| GET | `/{ac_id}` | | 200 `ApplicationCapabilityDetail` | 404 |
| PATCH | `/{ac_id}` | `ApplicationCapabilityUpdate` | 200 `ApplicationCapability` | 404, 409 sibling name, 422 |
| DELETE | `/{ac_id}` | | 204 | 404, 409 has children |
| POST | `/{ac_id}/business-capabilities` | `{business_capability_id}` | 201 `ApplicationCapabilityDetail` | 404, 409 dup, 422 level |
| DELETE | `/{ac_id}/business-capabilities/{cap_id}` | | 204 | 404 |
| POST | `/{ac_id}/technical-capabilities` | `{tech_cap_id}` | 201 `ApplicationCapabilityDetail` | 404, 409, 422 |
| DELETE | `/{ac_id}/technical-capabilities/{tc_id}` | | 204 | 404 |
| POST | `/{ac_id}/applications` | `{app_id}` | 201 `ApplicationCapabilityDetail` | 404, 409, 422 (ac not L3) |
| DELETE | `/{ac_id}/applications/{app_id}` | | 204 | 404 |
| GET | `/by-business-capability/{cap_id}` | | 200 `AppCapSummary[]` (with `realized_by`) | |
| GET | `/by-technical-capability/{tc_id}` | | 200 `AppCapSummary[]` | |
| GET | `/by-application/{app_id}` | | 200 `AppCapSummary[]` | |

Reverse lookups return `[]` for an unknown id rather than 404. That matches the existing reverse-lookup routes, and they are read-only.

422 messages for the level rules:
- `"application capabilities are mapped at L3; L1 and L2 are for grouping"`
- `"business capabilities are mapped at L3"`
- `"map to a technical capability at L2 or L3"`

Log lines (actor-attributed): `app_capability.create|update|delete`, `app_capability.link.create|delete kind=business|technical|application`.
