# REST contract: Capability ↔ Org Unit Mappings (941)

Base: `/api/v1/business`. Reads are open to every authenticated user. Writes need `WRITE_BUSINESS_ARCH` through the existing `/api/v1/business/` prefix rule; a reviewer gets 403. Served by `adp.organization.router`, which is registered before the business router.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/capability-org-mappings` | — | 200 `CapabilityOrgMappingsResponse` | — |
| PUT | `/capability-org-mappings/{cap_id}/owner` | `{"org_unit_id": "<id>" \| null}` | 200 `CapabilityOrgView` | 404 capability; 422 L3 capability ("Owners are set at L2 or L1, not L3"), unknown org unit |
| POST | `/capability-org-mappings` | `{"capability_id", "org_unit_id", "role": "performer"\|"contributor", "geography_id"?}` | 201 `CapabilityOrgMapping` | 404 capability; 422 not L3, owner role ("use PUT .../owner"), geography with contributor, unknown org unit or geography; 409 exact duplicate |
| DELETE | `/capability-org-mappings/{mapping_id}` | — | 204 | 404 |
| GET | `/capability-org-mappings/findings` | — | 200 `CapabilityOrgFindings` | — |
| GET | `/org-units/{ou_id}/footprint` | — | 200 `OrgUnitFootprint` | 404 org unit |

Semantics:
- **PUT owner** replaces any existing owner in one transaction. `null` clears it. Setting the same owner again is a no-op 200.
- **Effective owner**: the capability's own owner, else the nearest ancestor's (`owner_inherited_from` names that ancestor).
- **`outside_operating_geographies`**: true only for a performer whose geography is neither one of the unit's operating geographies nor inside one, and only when the unit has at least one operating geography.
- **Shared-service branches**: performers whose org unit has an ancestor that also performs the same L3 are folded into it (`folded_into`). `branches` is the number of performers left, and a capability is a candidate when `branches >= 2`.
- Findings and footprint are computed per request and never stored.

Log lines (INFO, `adp.organization`):

```text
organization.capability_mapping.set_owner   capability=<id> org_unit=<id> previous=<id|None> actor=<sub>
organization.capability_mapping.clear_owner capability=<id> previous=<id> actor=<sub>
organization.capability_mapping.add         capability=<id> org_unit=<id> role=<r> geography=<id|None> actor=<sub>
organization.capability_mapping.remove      mapping=<id> capability=<id> org_unit=<id> role=<r> geography=<id|None> actor=<sub>
```
