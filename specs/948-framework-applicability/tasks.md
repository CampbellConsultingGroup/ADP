# 948 Tasks

- [x] T001 Migration 059: framework_jurisdiction_geographies, framework_jurisdiction_triggers (CASCADE from framework and geography; subject type CHECK).
- [x] T002 Pure `adp.compliance.applicability.compute_framework_applicability` (FR-003/FR-004): lifecycle, triggers, overlap via 946 GeoGraph as of the date, evidence with path and via entity.
- [x] T003 `adp.compliance.jurisdiction`: get/set jurisdiction (validated against 947's relation matrix), snapshot, subject and framework applicability.
- [x] T004 `adp.compliance.applicability_router` registered beside the compliance router (not nested).
- [x] T005 Tests: test_applicability.py (pure), test_framework_applicability_api.py (contract), test_applicability_not_stored.py (guard), test_migration_059.py (integration, CI).
- [x] T006 Web: hooks, `compliance/Applicability.tsx` (jurisdiction editor, applies-to list, subject view) on the framework, the application's Regulatory Mappings tab and the legal entity; tests.
- [x] T007 Live check on local Postgres (059 up/down), API and browser with scratch data; data removed, DB back at 057.
