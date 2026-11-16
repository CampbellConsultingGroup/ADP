---
description: "Task list for 940-org-units-geography"
---

# Tasks: Org Units and Geography

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md in `/specs/940-org-units-geography/`
**Tests**: Mandatory (ART-IV). Test tasks come before their implementation and must fail first.
**Stories**:
- US1: org tree (P1)
- US2: geography (P1)
- US3: operating geographies (P2)
- US4: review queue (P1)
- US5: application picker + Portfolio (P2)

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Record the baseline in tasks.md Notes: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/ tests/`, `mypy src/`, `cd web && npx tsc --noEmit && npx vitest run --coverage` (expect 2406 backend, 728 frontend). Run GitNexus upstream impact on `Application`, `update_application`, `create_application`, `groupByBusinessUnit`, `ApplicationForm`, `BusinessPage` and `_fetch_all` (business export), and record callers and risk.
- [X] T002 Create the package skeleton: src/adp/organization/__init__.py and src/adp/organization/data/. Create tests/unit/organization/__init__.py.

---

## Phase 2: Foundational (blocks every story)

**Purpose**: the geography data file, the migration, and the shared hierarchy machinery.

- [X] T003 [P] Write tests/unit/organization/test_geography_data.py (research R4):
  - the file loads and has `source` and `retrieved` keys;
  - exactly 5 regions, each with an `m49`;
  - every country `iso2` matches `^[A-Z]{2}$` and is unique across regions and `unassigned`;
  - the total country count is between 240 and 260;
  - `TW` and `AQ` are in `unassigned`;
  - known samples: DE in Europe, BR in Americas, JP in Asia, NG in Africa, AU in Oceania.
- [X] T004 Build src/adp/organization/data/geographies.json from the UN Statistics Division M49 overview table (https://unstats.un.org/unsd/methodology/m49/overview/ — fetch the CSV via WebFetch or the web-fetch agent).
  - Fold sub-regions into the 5 regions.
  - Add the ISO 3166-1 codes missing from M49 (at least TW), and AQ, under `unassigned`.
  - Header: `source` URL and `retrieved` date.

  Keep the generator script in the session scratchpad, not the repo. T003 should now pass.
- [X] T005 [P] Write tests/integration/test_migration_048.py (Docker-gated; mirror test_migration_047.py). After upgrading 047→048, check:
  - the geography counts match the data file, with 1 Global and 5 regions;
  - `geo-DE` sits under `geo-m49-150` (Europe);
  - the level CHECK rejects 4;
  - the duplicate sibling name index (case-insensitive, including at the root);
  - the partial unique index on country `code`;
  - `org_unit_geographies` cascades from both ends;
  - `applications.owning_org_unit_id` is SET NULL when its org unit is deleted;
  - `primary_geography_id` is SET NULL when its geography is deleted;
  - downgrade to 047 drops everything; upgrade again works.
- [X] T006 Write src/adp/store/migrations/versions/048_org_units_geography.py (`down_revision="047"`), per data-model.md:
  - the three tables, the CHECKs and the indexes;
  - an `applications.owning_org_unit_id` column, FK and index;
  - upgrade bulk-inserts geographies from `adp/organization/data/geographies.json`, with ids `geo-001`, `geo-m49-NNN` and `geo-XX` (research R4);
  - downgrade drops in reverse order.
- [X] T007 Write src/adp/organization/models.py (data-model.md):
  - `OrgUnitKind` / `GeographyKind` Literals and a `Ref` type;
  - `OrgUnit` / `Create` / `Update`, `Geography` / `Create` / `Update`, `UnmatchedValue`, `UnmatchedListResponse`, `ResolveUnmatched` (with a validator requiring exactly one of `org_unit_id` / `create`), `ResolveResult`;
  - list responses, all with `extra="forbid"`;
  - the error classes: OrgNotFoundError, DepthError, HasChildrenError, DuplicateSiblingError, DuplicateCodeError, DuplicateLinkError, InvalidCodeError.
- [X] T008 Write the tables in src/adp/organization/store.py, on its own `_metadata`:
  - `_org_units`, `_geographies`, `_org_unit_geographies`;
  - a narrow `_applications` mirror (id, name, owning_business_unit, owning_org_unit_id);
  - `_get_session_factory()`, mirroring `adp.patterns.store`.

**Checkpoint**: the data file passes its test, and the migration and models exist.

---

## Phase 3: User Story 1 — Build the organization model (P1) 🎯 MVP

**Goal**: org unit CRUD with the 937 hierarchy rules.
**Independent Test**: build Retail Co → Stores / Corporate → Finance. A 4th level, a duplicate sibling and deleting a parent are all refused. A reviewer gets 403.

- [X] T009 [P] [US1] Write tests/unit/organization/test_org_store.py `TestOrgUnits` (SQLite on `ostore._metadata`; patch `index_entity`/`unindex_entity` to recorders):
  - level derived from the parent;
  - the 4th level refused;
  - a duplicate sibling refused ignoring case, including two roots;
  - parent and level ignored on update;
  - delete refused with children;
  - delete clears `applications.owning_org_unit_id` on the mirror (FR-013);
  - `org_unit_exists`;
  - list counts (application_count) and paths;
  - search hooks fire on create, rename and delete.
- [X] T010 [P] [US1] Write tests/contract/test_organization_api.py `test_org_units_*` (fixture: create `astore._metadata` first, then `ostore._metadata` with `tables=[t for t in ostore._metadata.sorted_tables if t.name != "applications"]` — research R2):
  - CRUD, with the 404/409/422 mapping;
  - a reviewer override gets 403 on POST;
  - GET with no auth requirement.
- [X] T011 [US1] Implement the org unit functions in src/adp/organization/store.py: list, get, create, update, delete, `org_unit_exists`, plus a generic `_create_node` / `_check_sibling` helper reused by geographies (research R3). Call `index_entity(ENTITY_ORG_UNIT, …)` with the name + description + path text. T009 should now pass.
- [X] T012 [US1] Implement src/adp/organization/router.py (`APIRouter(prefix="/api/v1/business")`) with the org unit routes and an `_http` error map. Log `organization.org_unit.<event> id=… actor=…`. Register it in src/adp/api/app.py **before** the business router. Add `ENTITY_ORG_UNIT` to src/adp/search/index.py and src/adp/search/__init__.py. T010 should now pass.
- [X] T013 [P] [US1] Write web/src/business/OrganizationTab.test.tsx and OrgUnitTree tests: the tree renders levels with kinds; add root/child; the "+ child" control is hidden at level 3; delete with confirm; read-only for reviewers (`useCanWriteBusiness`, or the existing business write gate — check `web/src/business` for the gate in use); empty state.
- [X] T014 [US1] Implement web/src/api/organization.ts (types and hooks `useOrgUnits`, `useOrgUnit`, `useCreateOrgUnit`, `useUpdateOrgUnit`, `useDeleteOrgUnit`, invalidating `["organization"]` and `["applications"]`). Implement web/src/business/OrgUnitTree.tsx and web/src/business/OrganizationTab.tsx (sub-tabs Org Units | Geography | Unmatched). Add an "Organization" tab to web/src/business/BusinessPage.tsx. T013 should now pass.

**Checkpoint**: MVP. The org tree is usable end to end.

---

## Phase 4: User Story 2 — Standard geography (P1)

**Goal**: the seeded, editable geography tree.
**Independent Test**: after migrating, DE is under Europe. A duplicate country code gets 409. Deleting a region that has countries gets 409.

- [X] T015 [P] [US2] Extend test_org_store.py `TestGeographies`:
  - the hierarchy rules (shared helper);
  - code validation (`^[A-Z]{2}$` for level 3; regions may have none);
  - duplicate code refused;
  - rename keeps the children;
  - delete refused with children;
  - delete clears `primary_geography_id`.
  - Include a seed helper that loads the data file into SQLite, so the tests use the real data.
- [X] T016 [P] [US2] Extend test_organization_api.py `test_geographies_*`: the list is about 255 when seeded through the helper; POST, PATCH and DELETE, with the error mapping.
- [X] T017 [US2] Implement the geography store functions and routes, plus a shared `load_geography_seed(conn_or_session)` used by both the migration and the tests, so they can't drift. T015–T016 should now pass.
- [X] T018 [P] [US2] Write web/src/business/GeographyTree.test.tsx: regions collapsed by default with their country counts; a country shows its code; filtering by name or code; edit and add controls for writers only.
- [X] T019 [US2] Implement web/src/business/GeographyTree.tsx (collapsible, with a filter box) and the geography hooks in web/src/api/organization.ts. T018 should now pass.

---

## Phase 5: User Story 4 — Resolve free-text business units (P1)

**Goal**: the review queue. It never writes free text and never creates anything implicitly.
**Independent Test**: "Store Systems" ×3 and "Store systems" ×1 are listed separately. Resolving both to Stores links 4 applications, and their text is unchanged.

- [X] T020 [P] [US4] Extend test_org_store.py `TestUnmatched`:
  - distinct exact values ordered by count desc, then value;
  - blank or whitespace-only values excluded;
  - already-linked applications excluded;
  - resolve to an existing unit updates only applications with an exact match and no link, and returns the count;
  - resolve with create builds the unit (hierarchy rules apply) and links in one transaction; a create error leaves nothing changed;
  - **`owning_business_unit` is byte-identical before and after** (SC-004).
- [X] T021 [P] [US4] Extend test_organization_api.py `test_unmatched_*`: GET shape; resolve with org_unit_id → 200 and the count; resolve with create → 200; both or neither given → 422; unknown org unit → 404; a reviewer gets 403; the resolve log line is checked with caplog.
- [X] T022 [US4] Implement `list_unmatched` and `resolve_unmatched` in src/adp/organization/store.py, and the routes (`/org-units/unmatched`, `/org-units/unmatched/resolve`, declared before `/org-units/{id}`) in router.py, with the log line (FR-012). T020–T021 should now pass.
- [X] T023 [P] [US4] Write web/src/business/UnmatchedList.test.tsx:
  - rows show the value and count;
  - "Map to…" picks an org unit and calls resolve;
  - "Create org unit" takes a name and parent and calls resolve with create;
  - the result message shows the updated count;
  - empty state "Every business unit value is matched";
  - writers only.
- [X] T024 [US4] Implement web/src/business/UnmatchedList.tsx, plus `useUnmatched` and `useResolveUnmatched` (invalidating `["organization"]` and `["applications"]`). T023 should now pass.

---

## Phase 6: User Story 3 — Where an org unit operates (P2)

**Goal**: org unit ↔ geography links and a primary geography.
**Independent Test**: link Stores to US, CA and DE. Both sides show the links, and a duplicate gets 409.

- [X] T025 [P] [US3] Extend test_org_store.py `TestLinks`: link, a duplicate refused, unlink, `geography_ids` on the org unit, org units listed per geography, the primary geography need not be linked, and the cascade on delete of either side.
- [X] T026 [P] [US3] Extend test_organization_api.py `test_links_*`: POST and DELETE `/org-units/{id}/geographies`, GET `/geographies/{id}/org-units`, PATCH `primary_geography_id` (including null to clear).
- [X] T027 [US3] Implement the link functions and routes. T025–T026 should now pass.
- [X] T028 [P] [US3] Write tests for an org unit detail panel (web/src/business/OrganizationTab.test.tsx): it lists the operating geographies with an add picker (searchable country select) and remove; it has a primary geography select.
- [X] T029 [US3] Implement the org unit detail panel in OrganizationTab.tsx. T028 should now pass.

---

## Phase 7: User Story 5 — Org unit on applications (P2)

**Goal**: the application form picker and org-unit-aware Portfolio grouping.
**Independent Test**: of three applications sharing free text, two are linked. Portfolio shows the org unit bucket (2) and "<text> (unmatched)" (1).

- [X] T030 [P] [US5] Write backend tests in tests/contract/test_organization_api.py `test_application_owning_org_unit_*`: create and patch with a valid id; an unknown id → 422 `Org unit '<id>' not found`; an explicit null clears it; GET returns it. Extend tests/unit/application/test_models.py for the new field.
- [X] T031 [US5] Add `owning_org_unit_id` to `Application` / `ApplicationCreate` / `ApplicationUpdate` (src/adp/application/models.py), to the `_applications` table and the create/update/row mapping (src/adp/application/store.py, as a plain column — research R2), and to the create/update routes, which validate through `adp.organization.store.org_unit_exists` (src/adp/application/router.py). Use the Edit tool: these files are CRLF. T030 should now pass.
- [X] T031a [US5] Export: `application_arch` serializes `owning_org_unit_id` alongside `owning_business_unit` (extend tests/unit/export/test_application_arch_serialize.py first).
- [X] T032 [P] [US5] Write the frontend tests:
  - web/src/portfolio/groupApplications.test.ts: `groupByBusinessUnit` with a names map — linked → org unit name; unlinked with text → "<text> (unmatched)"; neither → Unclassified; update the existing bucket-name assertions;
  - an ApplicationForm picker test (pick and clear; payload has `owning_org_unit_id`).
- [X] T033 [US5] Implement the `groupByBusinessUnit(apps, orgUnitNames?)` change (web/src/portfolio/groupApplications.ts) and pass the map from `useOrgUnits()` in PortfolioPage.tsx. Add the "Owning org unit" select to web/src/application/ApplicationForm.tsx. Add `owning_org_unit_id` to the Application types in web/src/api/application.ts. Fix any fixtures tsc flags. T032 should now pass.

---

## Phase 8: Polish & Cross-Cutting

- [X] T034 [P] Search backfill: add org units to `reindex_all` (src/adp/search/backfill.py), with a test in tests/unit/search/test_backfill.py.
- [X] T035 [P] Export: add `organization/org-units/<id>.json` (`geography_ids`, `primary_geography_id`, `application_ids`) and `organization/geographies.json` to src/adp/export/business_arch.py, with orphan cleanup for org units. Write tests in tests/unit/export/ first.
- [X] T036 Seed (scripts/seed_retail.py, CRLF, so use Edit), a new phase:
  - the org tree Retail Co → Stores, Digital, Supply Chain, Corporate → Finance, HR;
  - links Stores → geo-US, geo-CA, geo-DE; Digital → geo-US, geo-GB;
  - `owning_business_unit` on about 8 applications, including "Store Systems" ×2 and "Store systems" ×1;
  - add the new tables to `WIPE_TABLES` (org units and links only; **never truncate `geographies`**, which is migration-seeded).
- [X] T037 Run the gates: the full pytest suite, ruff (`src/ tests/`), mypy, `adp-generate --check`, tsc, and `vitest --coverage` (it must stay at or above the ratchet). Record the counts in Notes.
- [X] T038 Verify live:
  - `alembic upgrade head` (048) on 5433, plus a downgrade/upgrade cycle;
  - restart the API;
  - run every quickstart.md step with curl;
  - Playwright through Organization (both trees, links, Unmatched resolve), the application form picker and Portfolio grouping;
  - clean up scratch data. The seed is not run (it wipes data) unless the user asks; set demo `owning_business_unit` values through the API instead and restore them afterwards.
- [X] T039 Add a CLAUDE.md Recent Changes entry. Update the ADP-55k.1 notes. Run `node .gitnexus/run.cjs analyze --index-only` and `detect-changes`.

---

## Dependencies & Execution Order

- Setup → Foundational (T003–T008) → stories.
- **US1** (T009–T014) first: the generic hierarchy helper (T011) is reused by US2.
- **US2** (T015–T019) after T011.
- **US4** (T020–T024) needs US1, because it resolves to org units. It is independent of US2.
- **US3** (T025–T029) needs US1 and US2.
- **US5** (T030–T033) needs US1. T031 touches the application CRLF files.
- Polish after the stories it covers. T036 (seed) can run any time after US3.

Parallel: the test tasks within each phase ([P]); frontend test-writing alongside backend implementation of the same story.

## Implementation Strategy

1. MVP: Foundational + US1 (the org tree), then stop and demo.
2. US2 + US4: geography and the review queue, the other two P1s.
3. US3 + US5 (P2), then Polish.

## Notes

- **Baseline (T001):** 2406 backend, 728 frontend.
- **GitNexus (T001):**
  - `create_application` / `update_application`: CRITICAL, 67 impacted. The change is additive: an optional field, validated only when sent.
  - `groupByBusinessUnit`, `ApplicationForm`, `BusinessPage`: UNKNOWN. Each has a single caller.
- **Data file (T004):** built from the UNSD M49 overview page (the English table, `downloadTableEN`), 5 regions, 247 countries, plus `unassigned` AQ and TW = 249 countries and 255 rows in total. The generator script stayed in the session scratchpad. Declared as package data in pyproject.toml (`adp.organization` → `data/*.json`); Docker's editable install also reads it from `src/`.
- **Deviations, recorded:**
  1. The loader lives in `adp/organization/geodata.py`, which has no dependencies, so the migration doesn't import the store (search and other heavy imports). The tests use the same loader.
  2. Seeded countries with no M49 region (AQ, TW) are level 3 directly under the level-1 Global. That is a seed-only exception to "level = parent + 1" (spec edge case); user-created nodes always follow the rule.
  3. **Portfolio (R6):** instead of threading a names map through grouping, cross-tab and filtering, `withOrgUnitLabels()` relabels each application once before grouping. Without a map it returns the list unchanged, so existing callers and tests are unaffected.
  4. Org-unit export lives in `adp.export.organization`, called last in the business cycle inside its own guard.
- **Found live, not by tests:** the review queue's "Linked N applications" confirmation vanished at once. After a resolve the list refreshes, the value leaves it, and the row and its message unmount. The message now lives on the list, with a regression test.
- **Verification (T037, T038):**
  - 2443 backend tests (+37), 89.77% coverage; 749 frontend (+21); ruff, mypy, tsc and adp-generate are clean; the frontend coverage ratchet held (60.29 / 56.91 / 51.56 / 62.73).
  - Migration 048 went up, down and up again on local Postgres (5433).
  - The quickstart curls all matched: 255 geographies; DE under Europe, TW under Global; 409 on a duplicate sibling; link plus reverse lookup; resolve linked 2 with the free text unchanged; 422 on an unknown org unit.
  - Playwright covered the Organization tab (tree, detail panel, geography filter), Unmatched create-and-map and map, and Portfolio grouping by org unit.
  - All scratch data was removed (0 org units, no business-unit text or links on applications, 255 geographies with no links).
  - The seed was not run (it wipes data); its new phase was checked for syntax and imports only. Ruff's import-order finding in the seed predates this change, and CI doesn't lint `scripts/`.
