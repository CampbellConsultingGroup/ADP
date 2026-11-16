# Tasks: Capability ↔ Org Unit Mappings

**Input**: design documents in `/specs/941-capability-org-mappings/` (plan.md, spec.md, research.md, data-model.md, contracts/rest-api.md, quickstart.md)
**Tests**: required (constitution ART-IV, TDD). Each test task is written first and must fail before its implementation task.
**Bead**: ADP-55k.2

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup

- [X] T001 Confirm the migration head is `048` (`ls src/adp/store/migrations/versions`, `alembic heads`) and that local Postgres on 5433 is at `048` (`alembic current`).
- [X] T002 Audit every test fixture that creates both the business store and the organization store metadata (`grep -rln "ostore._metadata" tests`): `tests/unit/search/test_backfill.py`, `tests/contract/test_organization_api.py`, `tests/unit/export/test_organization_export.py`, `tests/unit/organization/test_org_store.py`. List which also create `bstore` or `astore` metadata (astore already mirrors `business_capabilities` at `src/adp/application/store.py:165`). T005 will need to exclude the new `business_capabilities` mirror from the ostore `create_all` there.

---

## Phase 2: Foundational (blocks every story)

- [X] T003 Write the Docker-gated `tests/integration/test_migration_049.py`, mirroring `test_migration_048.py`. It covers:
  - upgrade creates `capability_org_mappings` with `ck_cap_org_mapping_role` and `ck_cap_org_mapping_geo_performer_only`;
  - `uq_cap_org_mapping_owner` (second owner fails), `uq_cap_org_mapping` (duplicate with NULL geography fails);
  - CASCADE on capability and org-unit delete, SET NULL on geography delete;
  - downgrade drops the table and upgrade re-applies.
- [X] T004 Create `src/adp/store/migrations/versions/049_capability_org_mappings.py` (`revision="049"`, `down_revision="048"`) per data-model.md: columns, the 3 FKs, the 2 CHECKs, the partial unique index (`postgresql_where=sa.text("role = 'owner'")`), the expression unique index on `(capability_id, org_unit_id, role, COALESCE(geography_id, ''))` and the two plain indexes. Downgrade drops the indexes and table.
- [X] T005 In `src/adp/organization/store.py`:
  - add the narrow mirror `_business_capabilities = sa.Table("business_capabilities", _metadata, id, name, level, parent_id, position)`;
  - add the `_capability_org_mappings` table matching migration 049 (unique indexes as `sa.Index(..., unique=True)`, with the partial one using `sqlite_where` and `postgresql_where`, so SQLite tests enforce one owner too);
  - update the fixtures found in T002 to exclude `business_capabilities` from the ostore `create_all` wherever another metadata already creates it.

  Then run `pytest tests/unit/organization tests/contract/test_organization_api.py tests/unit/search tests/unit/export -q` and confirm it is green.
- [X] T006 [P] Add the models from data-model.md to `src/adp/organization/models.py`, all `extra="forbid"` on write models:
  - `CapabilityOrgRole`, `CapabilityOrgMapping`, `SetOwner`;
  - `AddMapping` (validator: `geography_id` only with `role="performer"`), `CapabilityOrgView`, `CapabilityOrgMappingsResponse`;
  - `FindingCapability`, `SharedServicePerformer`, `SharedServiceCandidate`, `CapabilityOrgFindings`;
  - `FootprintL3`/`L2`/`L1`, `OrgUnitFootprint`;
  - new `LevelRuleError(OrganizationError)` → 422 (level rules) and `UnknownReferenceError(OrganizationError)` → 422 (an org unit or geography id in a request body that doesn't exist).

  Add both errors to the router's `_http` status map.
- [X] T007 Write the guard test `tests/unit/organization/test_cap_org_analysis_not_stored.py`, mirroring `tests/unit/application/test_cap_analysis_not_stored.py`. No table in any ADP metadata (business, application, organization) may have a column named like `effective_owner`, `owner_inherited`, `shared_service`, `unmapped`, `footprint`, `branches` or `outside_operating`.

**Checkpoint**: migration and tables exist; models compile; existing suites still green.

---

## Phase 3: User Story 1 — Name the accountable owner (P1) 🎯 MVP

**Goal**: set, replace and clear one owner on L1/L2; refuse L3; show the effective (inherited) owner.
**Independent test**: quickstart §1.

- [X] T008 [P] [US1] Write the pure tests in `tests/unit/organization/test_cap_org_analysis.py::TestEffectiveOwner` against a hand-built `Snapshot`:
  - own owner wins;
  - an L3 inherits the L2's owner, else the L1's;
  - the nearest owned ancestor wins when both L1 and L2 are owned;
  - no owner anywhere → None;
  - `owner_inherited_from` names the ancestor capability.
- [X] T009 [US1] Create `src/adp/organization/cap_org_analysis.py` with a frozen `Snapshot` dataclass (capabilities, org_units, geographies, operates_in, mappings: see data-model.md) and pure `effective_owner(snapshot, cap_id) -> (owner_ou_id | None, inherited_from_cap_id | None)`. Make T008 pass.
- [X] T010 [P] [US1] Write SQLite store tests in `tests/unit/organization/test_cap_mappings_store.py::TestOwner`:
  - `set_owner` on L2 and L1;
  - replacing the owner leaves exactly one owner row;
  - setting the same owner again is a no-op;
  - `None` clears it;
  - L3 raises `LevelRuleError` with "Owners are set at L2 or L1, not L3";
  - an unknown capability raises `OrgNotFoundError`; an unknown org unit raises `UnknownReferenceError`.
- [X] T011 [US1] Create `src/adp/organization/cap_mappings.py` with:
  - `build_snapshot(session)` (4 queries: capability mirror, org units, geographies + `org_unit_geographies`, mappings inner-joined to the capability mirror and org units);
  - `set_owner(cap_id, org_unit_id | None, session) -> tuple[CapabilityOrgView, previous_owner_id]`: delete the existing owner row, insert the new one in the same transaction;
  - `list_views(session) -> CapabilityOrgMappingsResponse`, using `cap_org_analysis` for the effective owner.

  Make T010 pass.
- [X] T012 [P] [US1] Write contract tests in `tests/contract/test_capability_org_mappings_api.py`. Use a fixture creating the bstore metadata, then the ostore metadata excluding `business_capabilities` and `applications` (astore too if the org fixture already does). Cover:
  - PUT owner 200 / replace / clear;
  - PUT owner on L3 → 422 with the rule text;
  - unknown capability → 404;
  - reviewer → 403;
  - GET `/capability-org-mappings` shows the inherited owner on the L3.
- [X] T013 [US1] Add `GET /capability-org-mappings` and `PUT /capability-org-mappings/{cap_id}/owner` to `src/adp/organization/router.py`, with `_log("organization.capability_mapping.set_owner" | ".clear_owner", capability=..., org_unit=..., previous=..., actor=...)`. Make T012 pass.

**Checkpoint**: owners work end to end through the API.

---

## Phase 4: User Story 2 — Performers and contributors, with geography (P1)

**Goal**: add and remove L3 performers (optional geography) and contributors; refuse other levels and duplicates; derive the outside-geography note; clean up on deletes.
**Independent test**: quickstart §2 and §5.

- [X] T014 [P] [US2] Write pure tests in `test_cap_org_analysis.py::TestGeographyNote`:
  - a geography equal to an operating geography → no note;
  - a descendant of one (Germany under Europe) → no note;
  - outside → note;
  - a unit with no operating geographies → no note;
  - a performer with no geography → no note;
  - contributors never get a note.
- [X] T015 [US2] Add `outside_operating_geographies(snapshot, org_unit_id, geo_id) -> bool` to `cap_org_analysis.py`, walking the geography parent chain. Include it in `list_views`' performer entries. Make T014 pass.
- [X] T016 [P] [US2] Write store tests in `test_cap_mappings_store.py::TestPerformers`:
  - add a performer with and without a geography (both rows exist);
  - an exact duplicate raises `DuplicateLinkError`;
  - a performer or contributor on L1/L2 raises `LevelRuleError` "Performers and contributors are mapped at L3";
  - a contributor with a geography is refused;
  - `remove_mapping` deletes it and returns the row for logging;
  - an unknown mapping id → `OrgNotFoundError`.
- [X] T017 [P] [US2] Write delete-cleanup store tests in `test_cap_mappings_store.py::TestDeletes`:
  - `delete_org_unit` removes that unit's mappings, and an owned L2 then falls back to its L1's owner;
  - `delete_geography` clears the geography from a performer;
  - `delete_geography` where the same capability and unit also has a no-geography performer leaves exactly one no-geography row (R3);
  - mappings whose capability row is gone never appear in `list_views` (inner join).
- [X] T018 [US2] Implement in `cap_mappings.py`:
  - `add_mapping(body: AddMapping, session) -> CapabilityOrgMapping`: check the level and existence, then insert; catch `IntegrityError` or pre-check the duplicate → `DuplicateLinkError`;
  - `remove_mapping(mapping_id, session)`.

  In `store.py`:
  - `delete_org_unit` deletes `_capability_org_mappings` rows for the unit;
  - `delete_geography` first deletes performer rows on that geography whose capability and unit already has a no-geography performer row, then sets `geography_id=NULL` on the rest, before the existing cleanup.

  Make T016 and T017 pass.
- [X] T019 [P] [US2] Extend `tests/contract/test_capability_org_mappings_api.py`:
  - POST performer 201, with a geography;
  - duplicate → 409;
  - L2 target → 422;
  - `role: owner` → 422 pointing at the owner route;
  - contributor with a geography → 422;
  - unknown org unit or geography → 422;
  - DELETE 204, then 404;
  - reviewer → 403 on POST and DELETE;
  - GET shows `outside_operating_geographies`.
- [X] T020 [US2] Add `POST /capability-org-mappings` and `DELETE /capability-org-mappings/{mapping_id}` to `router.py`, with `.add` and `.remove` log lines (capability, org_unit, role, geography, actor). Make T019 pass.

**Checkpoint**: the full mapping write surface works; deletes are clean on SQLite and (via T003) on Postgres.

---

## Phase 5: User Story 3 — Findings (P1)

**Goal**: four derived lists with counts.
**Independent test**: quickstart §3.

- [X] T021 [P] [US3] Write pure tests in `test_cap_org_analysis.py::TestFindings`:
  - no owner: an unowned L2 under an unowned L1 is listed; an L2 under an owned L1 is not; a leaf L2 with no owner is listed;
  - shared service: one unit in DE and FR → not a candidate; Stores + E-commerce → candidate (branches = 2); a division plus its own function → not a candidate (`folded_into` set); two sibling functions → candidate; three units where one folds → branches = 2;
  - unmapped vs owned-no-performer split; a leaf L2 never appears as an unmapped L3;
  - contributors change nothing;
  - counts, including `l1_l2_total` and `l3_total`;
  - list order follows capability position then name.
- [X] T022 [US3] Implement `findings(snapshot) -> CapabilityOrgFindings` in `cap_org_analysis.py`, with capability paths (L1 › L2) and org-unit paths. Make T021 pass.
- [X] T023 [P] [US3] Extend the contract tests: GET `/capability-org-mappings/findings` returns 200 with each list populated by a small fixture model, and the lists change after a mapping is added (nothing cached).
- [X] T024 [US3] Add `GET /capability-org-mappings/findings` to `router.py`, using `build_snapshot` + `findings`. Make T023 pass.

---

## Phase 6: User Story 4 — Org unit footprint (P2)

**Goal**: performs (L1 → L2 → L3 with counts, including descendant units, attributed), owns and contributes.
**Independent test**: quickstart §4.

- [X] T025 [P] [US4] Write pure tests in `test_cap_org_analysis.py::TestFootprint`:
  - three L3s under two L2s in one L1 give correct counts at each level;
  - a division includes its function's L3, attributed to the function, with geographies;
  - owns and contributes lists, attributed;
  - an empty unit gives empty lists and `l3_total=0`;
  - sorting.
- [X] T026 [US4] Implement `footprint(snapshot, org_unit_id) -> OrgUnitFootprint` in `cap_org_analysis.py`. Make T025 pass.
- [X] T027 [P] [US4] Extend the contract tests: GET `/org-units/{id}/footprint` returns 200 with the expected shape; an unknown unit → 404.
- [X] T028 [US4] Add `GET /org-units/{ou_id}/footprint` to `router.py`, placed after the existing `/org-units/unmatched` routes so `unmatched` is never taken as an id. Make T027 pass.

---

## Phase 7: User Story 5 — Export and seed (P3)

- [X] T029 [P] [US5] Extend `tests/unit/export/test_business_arch_serialize.py`: `_serialize_capability` includes `organization` with owner, effective_owner (`inherited_from`), performers (with geography) and contributors, and empty values when the capability has no mappings.
- [X] T030 [US5] In `src/adp/export/business_arch.py`:
  - give `_serialize_capability` an `organization` argument (default empty);
  - in `_fetch_all`, build the snapshot once via `adp.organization.cap_mappings.build_snapshot` and pass each capability its block.

  Guard the org part so an export never fails because of it (log a warning, emit empty blocks). Make T029 pass.
- [X] T031 [US5] In `scripts/seed_retail.py`:
  - add `capability_org_mappings` to `WIPE_TABLES` before `org_units`;
  - add phase C4 after C3, covering:
    - owners on most L2s, leaving one L2 and its L1 unowned;
    - Accept Payment (or the closest existing L3) performed by Stores in DE and FR, and by E-commerce;
    - a contributor;
    - one L3 left with no performer under an unowned L2.

  Import-check only (`python -c "import ast; ast.parse(open('scripts/seed_retail.py').read())"`). Do NOT run the seed (it hard-wipes the local DB).

---

## Phase 8: Frontend (US1–US4 surfaces)

- [X] T032 [P] Add types and hooks to `web/src/api/organization.ts`:
  - `useCapabilityOrgMappings`, `useSetCapabilityOwner`, `useAddCapabilityMapping`, `useRemoveCapabilityMapping`, `useCapabilityOrgFindings`, `useOrgUnitFootprint`;
  - mutations invalidate the `["organization"]` prefix, so mappings, findings and footprint all refresh.
- [X] T033 [P] [US1] [US2] Write `web/src/business/CapabilityOrgPanel.test.tsx`:
  - owner chip, own vs inherited "(inherited)";
  - L1/L2 expander sets and clears the owner;
  - L3 expander adds a performer with a geography, adds a contributor, removes one;
  - the outside-geography note is shown;
  - the API's rule error appears in an alert;
  - readers see chips but no controls.
- [X] T034 [US1] [US2] Create `web/src/business/CapabilityOrgPanel.tsx`, exporting `CapabilityOrgChips` (row chips) and `CapabilityOrgEditor` (expander content). Geography picker: the unit's operating geographies first, then all. Wire both into `web/src/business/CapabilityNode.tsx`: chips in the row, plus an "Organization" toggle next to the existing Links and Compliance toggles. Make T033 pass, and keep the existing `CapabilityNode.test.tsx` and `CapabilityTree.test.tsx` green (mock the new hooks where needed).
- [X] T035 [P] [US3] Write `web/src/business/OrgFindings.test.tsx`:
  - four lists with counts;
  - shared-service entries show the units, geographies and folded units;
  - clicking an entry calls `onOpenCapability(id)`;
  - an empty state per list;
  - the loading and error states.
- [X] T036 [US3] Create `web/src/business/OrgFindings.tsx`. Add a "Findings" sub-tab to `OrganizationTab.tsx`, with an `onOpenCapability` prop. In `BusinessPage.tsx`, pass `onOpenCapability={(id) => { setTab("capabilities"); setFocusCapabilityId(id); }}`. Make T035 pass, and update `OrganizationTab.test.tsx` mocks.
- [X] T037 [P] [US4] Write `web/src/business/OrgUnitFootprint.test.tsx`: grouped L1 → L2 → L3 with counts, attribution to child units, the owns and contributes lists, the empty state, and capability links calling `onOpenCapability`.
- [X] T038 [US4] Create `web/src/business/OrgUnitFootprint.tsx` and render it in the org-unit detail panel in `OrganizationTab.tsx`. Make T037 pass.

---

## Phase 9: Polish & cross-cutting

- [X] T039 Run the gates:
  - `pytest tests/ --ignore=tests/integration -q`;
  - `ruff check src/`, `mypy src/`, `adp-generate --check`;
  - `cd web && npx tsc --noEmit && npm run test:run -- --coverage` (stay above the ratchet).

  Fix anything that fails.
- [X] T040 `alembic upgrade head` (049), `downgrade 048`, `upgrade head` on local Postgres (5433). Restart the backend (task on :8001) and run quickstart §1–§5 with curl on scratch data.
- [X] T041 Playwright walkthrough of quickstart §6 (chips and expander, the Findings sub-tab opening a focused capability, the footprint). Fix any UI bug found, with a regression test. Clean up all scratch data and confirm it is gone.
- [X] T042 Add the 941 Recent Changes entry to `CLAUDE.md` by hand (not the update script); mark tasks `[X]` and add implementation notes here; add a note to bead ADP-55k.2; run `node .gitnexus/run.cjs analyze --index-only` and `detect-changes --scope all`.

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T007)** → the user stories.
- **US1 (T008–T013)** comes first: `cap_mappings.py`, `cap_org_analysis.py` and the snapshot it creates are used by every later story.
- **US2 (T014–T020)** depends on US1's modules.
- **US3 (T021–T024)** and **US4 (T025–T028)** depend only on the snapshot (US1) and can run in either order. Both are only meaningful once US2's performers exist.
- **US5 (T029–T031)** after US1–US4 (it serializes their output).
- **Frontend (T032–T038)** after the matching backend routes: T034 after T013/T020, T036 after T024, T038 after T028.
- **Polish (T039–T042)** last.

Within a story: the test task, then its implementation; pure engine before store before route.

## Parallel examples

- After T006: T007, T008 and T010 in parallel (different files).
- US2: T014, T016 and T017 together; then T015 and T018.
- US3 and US4 tests (T021, T025) can be written together once T011 lands.
- Frontend: T033, T035 and T037 can be written in parallel after T032.

## Implementation Strategy

- **MVP**: Phases 1–3 (owners with inheritance through the API), then the T034 owner chip. That alone answers "who is accountable".
- **Then**: US2 performers → US3 findings (the headline value) → US4 footprint → US5 export/seed → polish.
- Commit only when the user asks.

---

## Implementation notes (2026-11-16)

- **Results**:
  - backend 2493 tests (+50), 89.98% coverage;
  - frontend 775 tests (+26), coverage 60.75 / 57.56 / 52.24 / 63.14 (up on all four, above the ratchet);
  - ruff, mypy, tsc and `adp-generate --check` clean.
- **Migration 049**: upgrade, downgrade, upgrade on local Postgres (5433). `test_migration_049.py` is Docker-gated and runs in CI.
- **Live checks on real Postgres** (scratch org units on the existing Sales & Customer Transactions › In-Store Transaction Management › Accept Payment chain, all removed afterwards; 0 mappings, 0 org units, 255 geographies):
  - **owners**: replace works, L3 refused with the rule text, inheritance shown;
  - **performers**: duplicate gives 409, an L2 target gives 422, the outside-geography note is false for Germany (unit operates in Europe) and true for Brazil;
  - **findings**: Accept Payment becomes a shared-service candidate with 2 branches once Ecom is added, and stops being one when the parent unit also performs it (folding);
  - **footprint**: includes the sub-units, attributed;
  - **deletes**: deleting a geography merges into an existing "everywhere" row (the `DELETE ... WHERE EXISTS` self-alias works on Postgres), or clears the geography otherwise; deleting an org unit removes its mappings, and its owned L2 falls back.
- **UI bugs found live and fixed, each with a regression test**:
  1. the Organization expander flashed "No org units yet" while org units were loading;
  2. owner and performer chips widened their row, pushing its controls (Delete) off the edge. The name column now has `minWidth: 0`, and the chips are inline-blocks at 100% max width with an ellipsis and the full text in the title;
  3. the footprint said "1 L3 capabilities", and its headings didn't match the panel's style.
- **Deviations from the plan**:
  - `export_block()` lives in the pure engine, so the export reuses the same derivation;
  - `UnknownReferenceError` was added for unknown org unit or geography ids in a body (422), separate from the 404 for the capability in the path;
  - the contract fixture keeps the organization store's narrow `applications` mirror (the org-unit routes need it) and excludes only `business_capabilities`.
- **Seed**: phase C4 (owners, performers, contributors). Every referenced capability and org unit name was checked against the seed's own lists; the seed itself was NOT run (it hard-wipes the local DB). `capability_org_mappings` is in `WIPE_TABLES`.
- **Pre-existing, not changed**: the Capabilities tree is ~24–44px wider than its container at deeper indents, which gives a small horizontal scroll with or without these chips.
- **Follow-on**: ADP-m7x (show these findings on Governance → Architecture Health).
