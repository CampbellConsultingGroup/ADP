# 949 Tasks

- [x] T001 Vendor the pinned ISO 3166-2 snapshot (`data/iso_3166-2.json.gz`, iso-codes 4.20.1) with `data/README.md`; `data/regulatory_blocs.json` with sources; `geodata.subdivision*` and `blocs_seed`.
- [x] T002 Migration 060: `parent_place_id`, `place_type` CHECK, custom places, Regulatory blocs hierarchy (EU, EEA) with dated memberships.
- [x] T003 `GeoGraph`: structural place-in-place edges (`Entity.parent_place`, `parent_place()`, `hierarchy_of()`); `contains`/`places` follow them.
- [x] T004 Store: `subdivision_catalog`, `add_subdivision`, `seed_blocs`; `Geography.place_type`/`parent_place_id`; subdivision path via its country.
- [x] T005 `adp.organization.geo_views` (pure `placements`, `reached_places`, `footprint`, `matrix` + store wrappers); routes on the organization router (matrix, subdivisions) and the applications router (geo-footprint).
- [x] T006 Export `place_type`/`parent_place_id`; seed wipe keeps the blocs hierarchy.
- [x] T007 Tests: test_geo_places.py (pure, bloc dates), test_geo_places_api.py (contract), test_migration_060.py (integration, CI).
- [x] T008 Web: hooks, `business/GeoPlaces.tsx` (Organization -> Places: matrix, add subdivision), footprint on the application's Geography tab; tests.
- [x] T009 Live check on local Postgres (060 up/down/up), API and browser with scratch data; data removed, DB back at 057.
- [ ] Follow-on: external (CRM) hierarchy import, once the CRM and format are known.
