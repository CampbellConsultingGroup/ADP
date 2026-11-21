# 947 Tasks

- [x] T001 Migration 058: legal_entities, legal_entity_org_units, application_legal_entities, three geo link tables; org_unit_geographies -> operates_in; downgrade.
- [x] T002 Store tables; org unit list/detail, geography org_unit_count, reverse lookup, 940 link/unlink and deletes on operates_in links active today (FR-009, R4).
- [x] T003 941 snapshot reads operates_in active today (Q1b).
- [x] T004 `geo_links`: relation matrix, pure `check_link`, CRUD over the three subjects (FR-003..FR-006).
- [x] T005 `legal_entities`: CRUD, parent tree without cycles, LEI check, org unit and application links (FR-001, FR-002).
- [x] T006 `links_router` (business + applications routers, registered in app.py), errors mapped.
- [x] T007 Search ENTITY_LEGAL_ENTITY + backfill (FR-010); export (FR-011); seed wipe list.
- [x] T008 Tests: test_geo_links.py (unit), test_legal_entities_api.py (contract), export, backfill, test_migration_058.py (integration, CI).
- [x] T009 Web: hooks, GeoLinksEditor, LegalEntities tab, org unit panel, application Geography tab, tests.
- [x] T010 Live check: migration 058 up/down/up on local Postgres (16 links kept), API rules, browser walkthrough; test data removed, DB back at 057.
