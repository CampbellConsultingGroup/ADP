# Data Model: Capability ↔ Org Unit Mappings (941)

## Stored: `capability_org_mappings` (migration `049`, `down_revision = "048"`)

| Column | Type | Rules |
|---|---|---|
| `id` | String(36) PK | uuid4 |
| `capability_id` | String(36) NOT NULL | FK `business_capabilities.id` ON DELETE CASCADE |
| `org_unit_id` | String(36) NOT NULL | FK `org_units.id` ON DELETE CASCADE |
| `role` | String(16) NOT NULL | CHECK `role IN ('owner','performer','contributor')` (`ck_cap_org_mapping_role`) |
| `geography_id` | String(36) NULL | FK `geographies.id` ON DELETE SET NULL; CHECK `role = 'performer' OR geography_id IS NULL` (`ck_cap_org_mapping_geo_performer_only`) |
| `created_at` | timestamptz NOT NULL | |

Indexes:
- `uq_cap_org_mapping_owner`: UNIQUE on `capability_id` WHERE `role = 'owner'` (at most one owner).
- `uq_cap_org_mapping`: UNIQUE on `(capability_id, org_unit_id, role, COALESCE(geography_id, ''))` (no exact duplicates, NULL geography included).
- `ix_cap_org_mapping_org_unit` on `org_unit_id` (footprint).
- `ix_cap_org_mapping_capability` on `capability_id`.

Store-enforced rules (422, message names the rule):
- owner → capability level 1 or 2 ("Owners are set at L2 or L1, not L3");
- performer / contributor → capability level 3 ("Performers and contributors are mapped at L3");
- geography only with performer (also the CHECK);
- capability, org unit and geography must exist (404 for the capability in the path, 422 for a referenced body id).

Duplicate → 409. Downgrade drops the table.

Mirror on the organization metadata (read-only, never created by the migration): `business_capabilities(id, name, level, parent_id)`. Test fixtures create `bstore` metadata first and the organization metadata excluding `business_capabilities` and `applications`.

## Pydantic models (`adp.organization.models`)

```text
CapabilityOrgRole = Literal["owner", "performer", "contributor"]

CapabilityOrgMapping   id, capability_id, org_unit: Ref, role, geography: Ref | None,
                       outside_operating_geographies: bool   # derived, FR-006; always false unless performer
SetOwner               org_unit_id: str | None               # extra="forbid"
AddMapping             capability_id, org_unit_id, role: Literal["performer","contributor"], geography_id: str | None
                       # validator: geography_id only with performer
CapabilityOrgView      capability_id, level, owner: Ref | None, effective_owner: Ref | None,
                       owner_inherited_from: Ref | None (the ancestor capability), performers[], contributors[]
CapabilityOrgMappingsResponse   items: list[CapabilityOrgView]   # only capabilities with any data or an effective owner
```

Findings (derived):

```text
FindingCapability      id, name, level, path: list[Ref]
SharedServicePerformer org_unit: Ref, org_unit_path: list[Ref], geographies: list[Ref], folded_into: Ref | None
SharedServiceCandidate capability: FindingCapability, branches: int, performers: list[SharedServicePerformer]
CapabilityOrgFindings  no_owner: list[FindingCapability]            # L1/L2, no effective owner
                       shared_service: list[SharedServiceCandidate]  # L3, branches >= 2
                       unmapped: list[FindingCapability]             # L3, no performer, no effective owner
                       owned_no_performer: list[FindingCapability]   # L3, no performer, effective owner present
                       counts: {no_owner, shared_service, unmapped, owned_no_performer, l1_l2_total, l3_total}
```

Footprint (derived, FR-014/015):

```text
FootprintL3     capability: Ref, performed_by: list[{org_unit: Ref, geographies: list[Ref]}]
FootprintL2     capability: Ref, l3_count, l3s: list[FootprintL3]
FootprintL1     capability: Ref, l3_count, l2s: list[FootprintL2]
OrgUnitFootprint org_unit: Ref, includes_descendants: true, performs: list[FootprintL1], l3_total,
                 owns: list[{capability: FindingCapability, org_unit: Ref}],
                 contributes: list[{capability: FindingCapability, org_unit: Ref}]
```

Sorting: by capability `position` then name at each level; org units by name.

## Snapshot (`cap_mappings.build_snapshot`, 4 queries)

A frozen dataclass:
- `capabilities: dict[id, (name, level, parent_id, position)]`
- `org_units: dict[id, (name, level, parent_id)]`
- `geographies: dict[id, (name, parent_id)]`
- `operates_in: dict[org_unit_id, set[geo_id]]`
- `mappings: list[row]` (inner-joined to the capability mirror and org units, so orphans never appear).

## Export (`business-architecture/capabilities/<id>.json`)

```json
"organization": {
  "owner": {"id": "...", "name": "..."} | null,
  "effective_owner": {"id": "...", "name": "...", "inherited_from": "<cap id>" | null} | null,
  "performers": [{"org_unit": {"id","name"}, "geography": {"id","name"} | null}],
  "contributors": [{"org_unit": {"id","name"}}]
}
```
