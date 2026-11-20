# Implementation Plan: GEO-01 (946)

**Branch**: `946-geo-hierarchies` | **Spec**: [spec.md](spec.md) | **Bead**: ADP-bo1.1

## Summary
`geographies` stays the one addressable table (every id and every foreign key unchanged); each row
is a **place** or a **node** (`entity`). Nodes belong to a `geo_hierarchies` row (kind, shape,
system of record). Parenthood moves from `geographies.parent_id` into dated `geo_memberships`.
One pure resolver (`adp.organization.geo_model.GeoGraph`) answers containment, overlap, places of
a node and the reference parent as of a date, and validates writes. 941/942/943 use it.

## Technical Context
Python 3.12 / TypeScript 5 + React 18; existing stack, zero new packages. PostgreSQL 16;
migration `057` (`down_revision="056"`).

## Constitution Check
ART-I/IV/II/V/IX/XIII/XV as in the spec. No violations.

## Research decisions
- **R1 Keep ids, change meaning.** Places/nodes share `geographies` (supertype). Alternatives
  rejected: separate `geo_place`/`geo_node` tables would need a polymorphic (place_id | node_id)
  pair on six referencing tables and their unique indexes (941's COALESCE index included).
- **R2 Columns.** `geographies`: + `entity` (place|node, CHECK), + `hierarchy_id` (nodes only,
  CHECK), + `place_type` ('country'); − `parent_id`, − `level` (moved to memberships / derived).
  The sibling-name index becomes: nodes unique per (hierarchy, lower(name)). Code index kept.
- **R3 Memberships.** `geo_memberships(id, hierarchy_id, parent_id, child_id, valid_from,
  valid_to, created_at, updated_at)`; parent a node of that hierarchy; child a node of that
  hierarchy or any place. Dates nullable (open), end exclusive. Validation in the pure resolver.
- **R4 Migration data.** Reference hierarchy `geoh-m49` ("UN M49 regions", kind `reference`,
  strict tree, system of record "UN M49"). `geo-001` and `geo-m49-*` → its nodes; level-3 rows →
  places; every old parent link → an undated membership in the parent's hierarchy. Any other
  level-1/2 row (user-added) → node of a "Custom (migrated)" hierarchy (created only when needed,
  kind custom, DAG), its old children become memberships there. Downgrade rebuilds parent/level
  from today's reference memberships (custom nodes come back as regions under Global).
- **R5 Containment (from parked 945, redefined).** places(place) = {place}; places(node) =
  places reachable through active memberships. contains(a, b): a == b; else a must be a node and
  b a descendant of a, or b a node whose places are non-empty and all in places(a). overlaps(a, b):
  either contains the other, or places intersect. Equals the old tree answers for tree data
  (a place never contains a node, so a one-country region is not inside its country).
- **R6 Global.** `GLOBAL_ID = "geo-001"`. Rules that refused level 1 refuse this id. Heat map
  default columns = nodes that are reference-hierarchy children of Global today.
- **R7 Display compatibility.** API `Geography` keeps `level` (1 Global, 2 node, 3 place),
  `parent_id`/`path` (= reference-hierarchy parent/path today) and `kind` (global | region |
  country), and adds `entity`, `hierarchy_id`, `hierarchy_name`, `hierarchy_kind`.
- **R8 Permission by kind.** Prefix rule `/api/v1/business/` already requires
  `write_business_arch`; handlers for regulatory / data_residency / tax hierarchies additionally
  require `write_compliance` via `is_permitted` (919 inline-check precedent).
- **R9 Test fixtures.** `geodata.geography_seed_rows` stays for migration 048. New
  `geodata.seed_geography(conn_or_session, now)` writes the hierarchy, entities and memberships;
  the 26 test call sites switch to it.
- **R10 Routes.** New `/geo-hierarchies` (CRUD, `?as_of=` detail), `/geo-hierarchies/{id}/nodes`,
  `/geo-hierarchies/{id}/memberships` (bulk add), `/geo-memberships/{id}` (PATCH dates, DELETE).
  `POST /geographies` is removed (places read-only); `PATCH`/`DELETE /geographies/{id}` act on
  nodes of writable hierarchies only. `GET /geographies?as_of=`.
