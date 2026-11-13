# Tasks: Agent Registry Core (Agentic Solutions P1)

**Input**: Design documents from `/specs/933-agent-registry/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/agentic-api.md ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). Test tasks come before their implementation in every phase and must be seen to fail first.

**Organization**:
- **US1:** record a solution and its agents (P1, the MVP).
- **US2:** estate-wide list and shared agents (P2).
- **US3:** search and export (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3

---

## Phase 1: Setup

- [x] T001 Create the package skeleton `src/adp/agentic/__init__.py` and the test dir `tests/unit/agentic/__init__.py`
- [x] T002 [P] Extract `isHttpUrl` from `web/src/compliance/FrameworkDetail.tsx:30-37` into the shared `web/src/ui/url.ts` (+ `url.test.ts`), and switch FrameworkDetail to import it

## Phase 2: Foundational (blocks all stories)

- [x] T003 Write the migration `src/adp/store/migrations/versions/043_agent_registry.py`:
  - drop and re-create `ck_app_application_type` with 'agentic' added;
  - create `agents` with its CHECKs and 3 indexes;
  - create `solution_agents` (composite PK, CASCADE on both legs, `ix_solution_agents_agent_id`);
  - the downgrade nulls 'agentic' rows before restoring the CHECK (data-model.md).
- [x] T004 [P] Write the Docker-gated test `tests/integration/test_migration_043.py`: upgrade/downgrade, the CHECKs, both cascade directions, and that 'agentic' is accepted and then nulled on downgrade.
- [x] T005 [P] Add 'agentic' to `ApplicationType` in `src/adp/application/models.py:35` (+ a case in `tests/unit/application/test_models.py`).
- [x] T006 [P] Add 'agentic' to the four frontend lists:
  - `web/src/api/application.ts:16`
  - `web/src/application/ApplicationForm.tsx:18-23`
  - `web/src/application/ApplicationDetail.tsx:33-38`
  - `web/src/portfolio/groupApplications.ts:131-137` (Agentic bucket last, + a test in `groupApplications.test.ts`)
- [x] T007 Write `src/adp/agentic/models.py`: Literals, `AutonomyLevel`, the Create/Update/response models, `cost_visible`, the http(s) validator, and the domain errors (data-model.md).
- [x] T008 Write `src/adp/agentic/store.py`: `_metadata`, the `agents` and `solution_agents` tables, the narrow `applications` mirror (id, name, application_type), and the engine/session factory (compliance/store.py shape).
- [x] T009 Write `src/adp/agentic/router.py` (prefix `/api/v1/agentic`, `_get_session`, `_get_actor`), and register it in `src/adp/api/app.py` after the compliance router.
- [x] T010 Add the prefix rule `("/api/v1/agentic/", ActionType.WRITE_APPLICATION)` to `src/adp/authz/enforcement.py`, and extend `tests/authz/test_enforcement.py` (completeness test + reviewer-denied write).

## Phase 3: US1 — record an agentic solution and its agents (P1, MVP)

**Independent test**: create an agentic app, register 4 agents, add them with roles, reorder, reload → everything persists. Invalid values and duplicates are rejected, and reclassification is blocked.

### Tests first

- [x] T011 [P] [US1] `tests/unit/agentic/test_models.py`: autonomy 0–4 bounds, Literal sets, blank name, `javascript:` / `data:` URL rejected and https accepted, negative cost rejected, `extra="forbid"`.
- [x] T012 [P] [US1] `tests/unit/agentic/test_store.py` (SQLite):
  - agent CRUD, PATCH `model_fields_set` semantics and explicit-null clearing;
  - add membership (non-agentic app → `NotAgenticSolutionError`, unknown app/agent → not-found, duplicate → `DuplicateSolutionAgentError`);
  - role change, reorder (mismatch → `OrderMismatchError`), remove with position re-normalisation;
  - agent delete removes memberships and re-normalises.
- [x] T013 [P] [US1] `tests/unit/application/test_agentic_reclassify_guard.py`:
  - agentic → custom with agents raises `AgenticSolutionHasAgentsError`;
  - with no agents it is allowed;
  - a PATCH that leaves the type unchanged is unaffected;
  - app delete removes memberships (explicit delete).
- [x] T014 [P] [US1] `tests/contract/test_agentic_api.py`:
  - every agent and membership route in contracts/agentic-api.md (201/200/204/404/409/422);
  - PATCH `/applications/{id}` → 409 on guarded reclassify;
  - cost gating: role override without `READ_APPLICATION_COST` → `null` + `cost_visible=false`; without `WRITE_APPLICATION_COST` → 403 on setting cost, 200 when the fields are omitted.
  - Fixture: astore `create_all` excluding `solution_agents`, then agstore (research.md D3).

### Implementation

- [x] T015 [US1] Agent CRUD functions in `src/adp/agentic/store.py` (create/get/update/delete, `updated_at`, deletes membership rows explicitly).
- [x] T016 [US1] Membership functions in `src/adp/agentic/store.py`: add (agentic check through the mirror, append position), update role, reorder (exact-match id list, normalise 0..n-1), remove (re-normalise), and list ordered with agent summaries.
- [x] T017 [US1] Guard and mirror in `src/adp/application/store.py`:
  - `_solution_agents` mirror table;
  - reclassify guard in `update_application` after `existing` is loaded;
  - explicit membership delete in `delete_application`;
  - `AgenticSolutionHasAgentsError` in `src/adp/application/models.py`.
- [x] T018 [US1] Map `AgenticSolutionHasAgentsError` → 409 in `src/adp/application/router.py` PATCH `/{app_id}` (:251-264).
- [x] T019 [US1] Agent and membership routes in `src/adp/agentic/router.py`:
  - inline `is_permitted(user.role, READ_APPLICATION_COST)` redaction on every read;
  - inline `WRITE_APPLICATION_COST` check when a body sets cost fields (`model_fields_set`);
  - error mapping;
  - `logger.info("agentic.* ... actor=%s")` on every mutation.
- [x] T020 [P] [US1] `web/src/api/agentic.ts`: types plus React Query hooks for agents and memberships (invalidation of the agent list, agent detail and solution agents).
- [x] T021 [P] [US1] `web/src/agentic/autonomy.ts` (scale names and meanings, FR-005) and `web/src/agentic/AgentForm.tsx` (create/edit; autonomy shown with meaning; prompt_ref labelled "Prompt version reference"; cost inputs hidden when `cost_visible` is false) + `AgentForm.test.tsx`.
- [x] T022 [US1] `web/src/agentic/SolutionAgentsPanel.tsx`: ordered members with role select, up/down reorder, remove, "add existing agent" picker and "register new agent" (AgentForm) + `SolutionAgentsPanel.test.tsx`.
- [x] T023 [US1] Add an "Agents" tab to `web/src/application/ApplicationDetail.tsx`, shown only when `application_type === "agentic"`, rendering `SolutionAgentsPanel`. Surface the 409 reclassify message in `ApplicationForm.tsx`.

## Phase 4: US2 — estate-wide list and shared agents (P2)

**Independent test**: 5 agents across 2 solutions, one shared → the list shows 5, `autonomy_min=3` filters correctly, and the shared agent's detail lists both solutions with their roles.

- [x] T024 [P] [US2] Extend `tests/unit/agentic/test_store.py` and `tests/contract/test_agentic_api.py`:
  - filters (`autonomy_level`, `autonomy_min`, `model_provider`, `owner`, `lifecycle_status`);
  - `solution_count`, including 0 (unassigned);
  - detail `solutions[]` with `app_name` and role;
  - a shared agent survives the deletion of one solution.
- [x] T025 [US2] Add the list query with filters and grouped `solution_count` (one query, no N+1) and the detail join to `src/adp/agentic/store.py`, plus the GET routes in `router.py`.
- [x] T026 [P] [US2] `web/src/agentic/AgentsPage.tsx`: table plus filter controls and an "Unassigned" badge for count 0 + `AgentsPage.test.tsx`.
- [x] T027 [P] [US2] `web/src/agentic/AgentDetail.tsx`: attributes; `a2a_card_url` rendered as a link only via `isHttpUrl`; "not estimated" vs "restricted" cost display; solutions list linking to each application; delete confirmation disclosing the solution count + `AgentDetail.test.tsx`.
- [x] T028 [US2] Add the "Agents" nav view in `web/src/shell/index.ts`, `web/src/ui/AppShell.tsx` (beside Applications, plus the page title) and `web/src/App.tsx` `renderPage()`.

## Phase 5: US3 — search and export (P3)

**Independent test**: register "Claims Triage Agent" → search finds it → the export file exists → delete it → both are gone.

- [x] T029 [P] [US3] Tests:
  - `tests/unit/agentic/test_search_indexing.py` (monkeypatched index/unindex recorder, the 930 precedent);
  - extend `tests/unit/search/test_backfill.py` (agents counted);
  - `tests/unit/export/test_agentic_export.py` (serialise, reconcile, orphan cleanup, SQLite).
- [x] T030 [US3] Add `ENTITY_AGENT` to `src/adp/search/index.py` and `src/adp/search/__init__.py` (import + `__all__`). Add index/unindex hooks to the agentic store's create/update/delete, with text from name, description, model_provider, model_id and framework.
- [x] T031 [US3] Add an agents loop and counts key to `src/adp/search/backfill.py` `reindex_all()`.
- [x] T032 [US3] Write `src/adp/export/agentic.py` (`agentic/agents/<id>.json` with `solutions[]`, cost unredacted per D8, orphan cleanup), and wire `start_agentic_export`/`stop_agentic_export` into the `src/adp/api/app.py` lifespan.

## Phase 6: Polish

- [x] T033 Seed in `scripts/seed_retail.py`: add `agents` and `solution_agents` to `WIPE_TABLES`; seed the ADP agentic application and its 5 agents (research.md D9) through store functions.
- [x] T034 Run the full gates: `pytest tests/ --ignore=tests/integration -q`, `ruff check src/`, `mypy src/`, `adp-generate --check`, `cd web && npm run test:run`, and `npx tsc --noEmit`. Fix any regressions, such as exhaustive switches and fixtures that build `Application` literals.
- [x] T035 Live verification against local Postgres:
  - `alembic upgrade head` (with the user's OK);
  - quickstart.md steps 1–8;
  - a Playwright UI walkthrough (step 9);
  - cleanup back to baseline counts.
- [x] T036 Add a CLAUDE.md "Recent Changes" entry; mark tasks done; update bead ADP-hii.

---

## Dependencies

- **Setup → Foundational:** T001 → T007–T009. T003 is needed before any live verification.
- **Foundational → stories:** Foundational (T003–T010) blocks every story.
- **US1:** T011–T014 (tests) → T015–T019 (backend) → T020–T023 (frontend).
- **US2:** depends on US1's store and router. T024 → T025 → T026–T028.
- **US3:** depends on US1's store. T029 → T030–T032. It can run in parallel with US2.
- **Polish:** after all stories.

## Parallel examples

- **Foundational:** T004, T005 and T006 together, once T003 is drafted.
- **US1 tests:** T011, T012, T013 and T014 together. **US1 frontend:** T020 and T021 together.
- **US2:** T026 and T027 together after T025.
- **US2 and US3:** the two phases can proceed together once US1's backend is complete.

## Implementation strategy

1. **MVP:** Phases 1–3, then a demo: an architect records ADP itself as an agentic solution with its agents.
2. **Next:** US2 (the governance list), then US3 (search and export), then polish and seed.
3. **Commits:** one per phase on `933-agent-registry`. The PR is opened only when the user asks.
