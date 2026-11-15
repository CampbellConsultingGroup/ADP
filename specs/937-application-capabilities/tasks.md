# Tasks: Application Capabilities (937)

**Input**: spec.md, plan.md, research.md, data-model.md, contracts/rest-api.md
**Tests**: required (ART-IV). Store tests are written first and seen to fail.

Format: `[ID] [P?] [Story] Description`. `[P]` = can run in parallel (different files).

## Phase 1: Setup

- [x] T001 Migration `src/adp/store/migrations/versions/046_application_capabilities.py` (`down_revision="045"`): four tables, the sibling-name expression index, CHECK level 1–3, cascades per data-model.md. Reversible.
- [x] T002 [P] Docker-gated `tests/integration/test_migration_046.py`: up/down/up; deleting an application, a technical capability, a business capability or an application capability removes only its links.

## Phase 2: Foundational

- [x] T003 Models and errors in `src/adp/application/models.py` (data-model.md "Read models" and "Errors").
- [x] T004 Extend the `_biz_caps` mirror in `src/adp/application/store.py` with nullable `level` and `parent_id`. Check that every fixture creating both business and application metadata still works.
- [x] T005 Tables in a new `src/adp/application/app_capabilities.py`, defined on `store._metadata`.

## Phase 3: US1 Catalog (P1)

- [x] T006 [US1] Store tests `tests/unit/application/test_app_capabilities_store.py`: derived level, depth-3 refusal, sibling-name uniqueness (case-insensitive, NULL-parent roots), delete refused with children, rename/describe. Must fail first.
- [x] T007 [US1] Implement create/get/list/update/delete in `app_capabilities.py`.
- [x] T008 [US1] Router `src/adp/application/app_capabilities_router.py` (CRUD). Register it in `src/adp/api/app.py`. Add the prefix rule in `src/adp/authz/enforcement.py`.
- [x] T009 [P] [US1] Contract tests `tests/contract/test_app_capabilities_api.py` (CRUD, 404/409/422), plus authz entries in `tests/authz/test_enforcement.py` (reviewer 403).

## Phase 4: US2 Links (P1)

- [x] T010 [US2] Store tests: each link type valid at the allowed levels; refused at L1/L2 business, L1/L2 application, L1 technical, with the rule message; duplicates 409; missing ends 404; many-to-many; deleting each end removes only its links; old link tables untouched.
- [x] T011 [US2] Implement link add/remove and level validation. `delete_application_capability`, `astore.delete_application` and `astore.delete_technical_capability` remove the new link rows explicitly.
- [x] T012 [US2] Link routes, with contract tests.

## Phase 5: US3 Warning (P1)

- [x] T013 [US3] Store tests: the warning appears on an L3 with no technical link, never on L1/L2, clears when a link is added, returns when the technical capability is deleted; `?warning=` filter; fixed query count for the list (4 SELECTs); guard test that no column stores the warning.
- [x] T014 [US3] Implement counts and warnings in list/get/detail (grouped COUNTs).

## Phase 6: US4 Traceability (P2)

- [x] T015 [US4] Store and contract tests for the three `by-*` reverse lookups (paths, `realized_by`, empty for unknown ids, literal routes not captured by `/{ac_id}`).
- [x] T016 [US4] Implement the reverse lookups and detail paths.

## Phase 7: US5 Search, export, seed (P2)

- [x] T017 [P] [US5] `ENTITY_APPLICATION_CAPABILITY` in `src/adp/search/index.py`. Write hooks in `app_capabilities.py`. Backfill in `src/adp/search/backfill.py`. Tests extend `tests/unit/search/test_backfill.py`, plus a hook test with recording stubs.
- [x] T018 [P] [US5] Export in `src/adp/export/application_arch.py` (bulk queries, orphan cleanup), with tests.
- [x] T019 [US5] Seed the POS example in `scripts/seed_retail.py` (research D10), reusing existing names, plus "Loyalty Points Accrual" with no technical link.

## Phase 8: Frontend

- [x] T020 Hooks in `web/src/api/appCapabilities.ts` (list, detail, create, update, delete, link add/remove, three reverse lookups; invalidate list and detail on link changes).
- [x] T021 [US1/US3] `AppCapTree.tsx` (alphabetical siblings, add child below L3, warning badge, counts), `AppCapForm.tsx`, `AppCapGaps.tsx`, the guidance note, and the Capabilities tab and focus state in `ApplicationPage.tsx`.
- [x] T022 [US2] `AppCapDetail.tsx`: path, three link editors whose pickers offer only valid levels (business L3, technical L2/L3, any application), delete, hidden for non-writers, 409/422 shown inline.
- [x] T023 [US4] Read-only sections: `CapabilityNode.tsx` (business L3: application capabilities plus realizing apps), `TechCapTree.tsx` ("Used by"), `ApplicationDetail.tsx` ("Realizes"). Each item navigates to Applications → Capabilities with the item focused.
- [x] T024 Component tests `web/src/application/appCapabilities.test.tsx`: tree badge, gaps list, depth control, picker level filtering, reviewer read-only, reverse sections.

## Phase 9: Polish

- [x] T025 ruff, mypy, `adp-generate --check`, the full pytest suite, vitest, tsc.
- [x] T026 Live verification per quickstart.md (migration on local Postgres, reseed, API curls, a Playwright walkthrough), then clean up scratch data.
- [x] T027 Update CLAUDE.md Recent Changes, file follow-on beads (Out of Scope items), refresh GitNexus.

## Dependencies

- T001 → T003–T005 → US1 → US2 → US3. US4 needs US2. US5 needs US1. The frontend needs its matching backend story.
- T002, T009, T017 and T018 can run in parallel within their phases.

## Implementation notes (2026-11-15)

- **Not strictly test-first.** The store module was written in one pass alongside its tests, not after watching them fail. All 23 store tests passed on the first run.
- **T002 not run locally.** Docker is not reachable from WSL here (`test_migration_045.py` fails the same way), so it runs in CI. Migration 046 was applied to the local Postgres instead and round-tripped up/down/up.
- **Tables moved.** The four tables are defined in `adp.application.store`, not `app_capabilities.py` as research D1 said, because `delete_application` / `delete_technical_capability` must remove link rows without a circular import.
- **Models moved.** They live in a new `adp.application.app_capability_models`. `models.py` (CRLF, ~900 lines) is untouched.
- **Reverse lists load on expand.** The read-only lists on the business L3 rows and technical capability rows are expanders that fetch on open, to avoid one request per tree row. They are still within the two clicks of SC-004.
