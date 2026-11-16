# Research: Capability ↔ Org Unit Mappings (941)

No `NEEDS CLARIFICATION` remained after the 2026-11-16 clarify session. These are the design decisions for the plan.

## R1 — Where the mapping lives

- **Decision**: in the existing `adp.organization` package (from 940). The table `capability_org_mappings` is defined in `adp.organization.store`, next to `_org_units` and `_geographies`, because `delete_org_unit` and `delete_geography` must clean it up. The logic goes in a new sibling module `adp.organization.cap_mappings` (writes and reads), and the derivations go in a pure module `adp.organization.cap_org_analysis` (no I/O). `store.py` is already 637 lines; this is the same split 937 made (`app_capabilities.py` next to `store.py`).
- **Business capabilities** are read through a narrow mirror `_business_capabilities` (id, name, level, parent_id) on the organization metadata. This is the precedent 940 set with its `applications` mirror.
- **Alternatives**:
  - `adp.business`: its core files are already past the size threshold (`adp.strategy`'s split precedent), and it would have to import the org store, reversing 940's direction.
  - A new package: no benefit, since every read joins org units.

## R2 — One table with a role, not three tables

- **Decision**: a single `capability_org_mappings` table: `id`, `capability_id`, `org_unit_id`, `role` (owner | performer | contributor, CHECK), `geography_id` (nullable), `created_at`. Rules:
  - **At most one owner per capability**: a partial unique index on `capability_id WHERE role = 'owner'`.
  - **No exact duplicates**: a unique expression index on `(capability_id, org_unit_id, role, COALESCE(geography_id, ''))`. Plain UNIQUE treats NULLs as distinct, so "performs everywhere" could otherwise be added twice.
  - **Geography only on performers**: a CHECK `(role = 'performer' OR geography_id IS NULL)`.
  - **Level rules** (owner at L1/L2, performer and contributor at L3): enforced in the store and refused with a 422 naming the rule, because an FK can't check the far row's level. This is the 937 precedent.
- **Why**: the three roles share the same shape and every read wants all of them together (the capability row, the footprint). One table means one query.
- **Alternatives**: three tables (owner as a column on the capability, plus performer and contributor tables). An owner column would put an org reference on the capability row, which the user's notes rule out: the capability model stays separate and the mapping carries the relationship.

## R3 — Deletes and SQLite parity

- **Capability deleted**: the migration's FK `ON DELETE CASCADE` removes its mappings in Postgres. Reads inner-join the mirror, so any orphan left in SQLite tests never surfaces (937's precedent). The business store is not changed.
- **Org unit deleted**: `delete_org_unit` deletes its mappings explicitly (SQLite parity), with CASCADE as the safety net. Owned capabilities then fall back to their parent's owner automatically, because the effective owner is derived.
- **Geography deleted** (FR-007): before deleting, the store:
  1. deletes performer rows on that geography where the same capability and unit already has a no-geography performer row (they would collide once the geography is cleared);
  2. sets `geography_id = NULL` on the remaining rows on that geography.

  Only one geography is deleted at a time, and 940 refuses to delete one with children. So each capability and unit has at most one row on it, and these two steps can't leave a duplicate.

  The FK is `ON DELETE SET NULL` as a safety net. Postgres would raise on the unique index if the store skipped the merge, which is why the store does it first.

## R4 — Effective owner, findings and footprint: pure functions over a snapshot

- **Decision**: `cap_mappings.build_snapshot(session)` runs a fixed 4 queries: capabilities mirror, org units, geographies with org_unit_geographies, and mappings. It returns a frozen dataclass. `cap_org_analysis` computes everything from it, with no I/O:
  - **Effective owner**: walk `parent_id` up from the capability, taking the first owner found. Depth is at most 3.
  - **No owner** (FR-009): L1/L2 with no effective owner.
  - **Shared-service candidates** (FR-010): for each L3, take its performer org units. Drop every unit that has an ancestor in the set (walking the org-unit parent chain); the survivors are the independent branches. Two or more survivors make a candidate. Every performer is listed with its geography and path, and each folded unit is reported under its branch.
  - **Unmapped / owned with no performer** (FR-011): L3s with no performer, split on whether an effective owner exists.
  - **Geography note** (FR-006): a performer's geography is "outside" when it is neither one of the unit's operating geographies nor a descendant of one (walking the geography parent chain). A unit with no operating geographies at all gets **no** note: there is nothing to compare against, and flagging every performer would be noise.
  - **Footprint** (FR-014/015): the unit plus all its descendants; their performer rows grouped L1 → L2 → L3, with L3 counts at each level; owner rows; contributor rows.
- **Why**: the 938 convention. One snapshot is cheap at this scale (hundreds of capabilities, thousands of mappings: SC-005), and the logic is unit-testable without a database.
- **Guard**: `test_cap_org_analysis_not_stored.py` asserts that no table in any metadata has a column naming a finding or the effective owner, mirroring `test_cap_analysis_not_stored.py`.

## R5 — API shape

All routes are under `/api/v1/business/` and served by the organization router (registered before the business router), so the existing `WRITE_BUSINESS_ARCH` prefix rule covers the writes:
- `GET /capability-org-mappings`: one bulk response for the Capabilities tab. Per capability, it gives its own owner, effective owner (marked inherited), performers (with geography and the outside-geography note) and contributors. The tree makes one request instead of one per row.
- `PUT /capability-org-mappings/{cap_id}/owner` with `{org_unit_id: str | null}`: sets, replaces or clears. Using replace rather than add-and-remove makes "at most one" impossible to break from the UI.
- `POST /capability-org-mappings` with `{capability_id, org_unit_id, role: performer|contributor, geography_id?}`. Owner is refused here, with a pointer to the owner route.
- `DELETE /capability-org-mappings/{mapping_id}`.
- `GET /capability-org-mappings/findings`.
- `GET /org-units/{id}/footprint`.

A distinct `capability-org-mappings` prefix avoids any overlap with the business router's `/capabilities/{cap_id}`.

## R6 — UI placement

- **Capability row** (`CapabilityNode.tsx`):
  - an owner chip on every row: own owner, or the inherited one in muted text with "(inherited)" — SC-002;
  - L3 rows also show performer chips;
  - a new "Organization" expander, next to the existing Links and Compliance expanders, edits the owner (L1/L2) or the performers and contributors (L3).
  - Each row calls the shared `useCapabilityOrgMappings()` hook. TanStack Query dedupes this to one request.
- **Findings**: a fourth sub-tab, "Findings", on Business → Organization, with three lists and counts. Each entry calls `onOpenCapability(id)`. `BusinessPage` switches to Capabilities and focuses the row through the existing `focusCapabilityId` path (from 043).
- **Footprint**: a section in the org-unit detail panel from 940, with the same capability links.

## R7 — Export, audit and seed

- **Export**: `_serialize_capability` gains `organization: {owner, effective_owner, performers[], contributors[]}`. `_fetch_all` reads it through `cap_mappings` (one query plus the snapshot).
- **Audit**: `_log("organization.capability_mapping.<set_owner|clear_owner|add|remove>", ...)`, giving actor, capability, org unit, role and geography (FR-008).
- **Seed**: phase C4, after C3's org tree. Three cases:
  - owners on most L2s, with one deliberately unowned L2 whose L1 is also unowned;
  - Accept Payment performed by Stores (DE, FR) and E-commerce, a shared-service candidate;
  - one L3 left unmapped.

  `capability_org_mappings` goes into `WIPE_TABLES`, before `org_units`.
