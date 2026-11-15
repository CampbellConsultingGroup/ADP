# Tasks: EA Pattern Registry, Lifecycle & Patterns Screen

**Input**: Design documents from `/specs/935-pattern-registry/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓ (D1–D16), data-model.md ✓, contracts/rest-api.md ✓, quickstart.md ✓

**Tests**: Mandatory (ART-IV). In every phase, test tasks come before their implementation and must be seen to fail first.

**Organization** (spec user stories):
- **US1**: import + catalog (P1, MVP)
- **US2**: lifecycle governance (P1)
- **US3**: knowledge projection (P2)
- **US4**: views (P2)
- **US5**: draft editing in the UI (P3)
- **US6**: export (P3)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6

---

## Phase 1: Setup

- [x] T001 Create the module skeletons `src/adp/patterns/{registry_models,lifecycle,resolve,projection,render,store,router}.py` (docstrings only) and `web/src/patterns/index.ts`. Add `--update-goldens` (a pytest `addoption`, default off) and a `golden(path, text)` helper to `tests/unit/patterns/conftest.py`.

## Phase 2: Foundational (blocks all stories)

- [x] T002 [P] Extend `tests/authz/test_permissions.py`. Expect: `PERMISSIONS_VERSION == "1.11.0"`; `WRITE_PATTERN`/`GOVERN_PATTERN` granted to EA and Platform Admin only; `GOVERN_PATTERN ∈ REQUIRES_CONFIRMATION`; the completeness checks updated.
- [x] T003 Add `ActionType.WRITE_PATTERN`/`GOVERN_PATTERN` (`src/adp/authz/roles.py`). In `src/adp/authz/permissions.py`: the 1.11.0 changelog line, the version bump and `REQUIRES_CONFIRMATION`. Make T002 pass.
- [x] T004 [P] Write `tests/unit/patterns/test_lifecycle.py`: the full 5×5 parametrized matrix of `allowed_transitions()` against data-model.md; `decommissioned` → ∅.
- [x] T005 Implement `PatternLifecycle`, `ImportStatus` and `PatternViewKind` in `src/adp/patterns/registry_models.py`, and `allowed_transitions()` in `src/adp/patterns/lifecycle.py`. Make T004 pass.
- [x] T006 Write migration `src/adp/store/migrations/versions/044_ea_pattern_registry.py` (`down_revision="043"`): the 4 tables, named CHECKs, the partial unique index and indexes (data-model.md); downgrade drops them in reverse order. Write `tests/integration/test_migration_044.py` (Docker-gated): up/down, CHECK names present, the partial index rejects a second `current`.
- [x] T007 Define the Core tables and mirrors (`applications` id/name; `controls` id; full-column `knowledge_items` with a `Vector(384)`/JSON-for-SQLite embedding variant) in `src/adp/patterns/store.py`. Include the partial unique `Index` with `postgresql_where`/`sqlite_where` (research D2), plus `_get_session_factory()` mirroring `adp.agentic.store`.
- [x] T008 Complete the remaining API models and exceptions in `src/adp/patterns/registry_models.py` (data-model.md, plus `PatternUpdateResult`).

## Phase 3: User Story 1 — Import and browse (P1) 🎯 MVP

**Goal**: an EA imports YAML; anyone lists, filters, opens and downloads.
**Independent test**: quickstart §1, plus the catalog UI showing an imported fixture.

- [x] T009 [P] [US1] Write `tests/unit/patterns/test_resolve.py`. With lookup sets given, check R1–R4 at the right paths, warning vs error severity by mode, and no issue when everything resolves.
- [x] T010 [US1] Implement `resolve_references(defn, lookups, *, blocking)` in `src/adp/patterns/resolve.py`, plus `store.load_lookups(defn, session)` (one batched query per reference type; principles must be active and of kind `principle`). Make T009 pass.
- [x] T011 [P] [US1] Write the import, read and filter tests in `tests/unit/patterns/test_store.py` (SQLite):
  - every row of the idempotency table (created, unchanged, I1, I2, I3);
  - an invalid YAML leaves 0 rows (atomic);
  - relation rows match the definition;
  - list filters by kind, lifecycle, tag and `q`;
  - family versions ordered current-first, then semver descending, so `1.10.0` sorts above `1.9.0`.
- [x] T012 [US1] Implement `import_pattern`, `list_versions`, `get_family`, `get_version_detail` and `get_yaml` in `src/adp/patterns/store.py`. Make T011 pass.
- [x] T013 [P] [US1] Write `tests/contract/test_patterns_api.py` (SQLite full app, `adp.agentic` fixture style, fake embedder):
  - `POST /import`: 201/200/422, 413 above 256 KB, 403 for Reviewer/SA/TA;
  - `GET` list/family/detail/yaml: media type and `Content-Disposition`;
  - 404s.
- [x] T014 [US1] Implement those routes in `src/adp/patterns/router.py`: literal routes before `/{key}`, a body cap, actor-attributed log lines. Register the router in `src/adp/api/app.py`. Add the `("/api/v1/patterns/", WRITE_PATTERN)` prefix rule (`src/adp/authz/enforcement.py`). Make T013 pass, and confirm `tests/authz/test_enforcement.py` completeness still passes.
- [x] T015 [P] [US1] Write `web/src/patterns/PatternsPage.test.tsx` and `IssueList.test.tsx`: filters drive the query; the issue list shows code + path; the import panel is hidden for a Reviewer.
- [x] T016 [US1] Implement:
  - `web/src/api/patterns.ts` (read hooks + `useImportPattern`);
  - `web/src/patterns/{PatternsPage,PatternFamily,PatternVersion (Overview + YAML tabs),ImportPanel,IssueList,permissions}.tsx|ts`;
  - nav wiring in `web/src/shell/index.ts`, `web/src/ui/AppShell.tsx` (Oversight, before Knowledge, with a `TITLES` entry) and `web/src/App.tsx`.

  Make T015 pass.

## Phase 4: User Story 2 — Lifecycle governance (P1)

**Goal**: reason + confirmation transitions, one current version, history.
**Independent test**: quickstart §2 and §4.

- [x] T017 [P] [US2] Extend `tests/unit/patterns/test_store.py`:
  - legal and illegal transitions (illegal → `IllegalTransitionError`);
  - propose freezes the version (update/delete → `NotDraftError`);
  - promotion swap: old version → deprecated, plus a demotion event with `caused_by_event_id`;
  - rollback;
  - a promotion blocked by an R-issue → `PromotionBlockedError`, with nothing changed;
  - a forced second current version → `ConcurrentPromotionError`;
  - history rows carry reason, confirmation and actor.
- [x] T018 [US2] Implement `transition()` and `get_history()` in `src/adp/patterns/store.py` (research D4; the projection hook is a no-op until US3). Make T017 pass.
- [x] T019 [P] [US2] Extend `tests/contract/test_patterns_api.py` for `POST .../lifecycle`: 200, 409 (illegal/concurrent), 422 (no reason, no confirmation, blocked with issues), and 403 for SA/TA/Reviewer. The detail response includes `allowed_transitions` and `history`.
- [x] T020 [US2] Implement the lifecycle route and add the explicit `GOVERN_PATTERN` rule in `_EXPLICIT_ROUTE_ACTIONS` (`src/adp/authz/enforcement.py`). Add an enforcement test asserting the lifecycle route maps to `GOVERN_PATTERN`. Make T019 pass.
- [x] T021 [P] [US2] Write `web/src/patterns/LifecycleDialog.test.tsx`: it offers only `allowed_transitions`; Submit stays disabled until reason + confirm are given; it sends `confirmation_id`; it is hidden for non-EA users.
- [x] T022 [US2] Implement `web/src/patterns/LifecycleDialog.tsx`, the History tab in `PatternVersion.tsx`, and `useTransition` (which invalidates `["patterns"]` and `["knowledge"]`). Make T021 pass.
- [x] T023 [US2] Write `tests/integration/test_pattern_registry.py` (Docker-gated): real concurrent promotions → exactly one current version, the other gets 409.

## Phase 5: User Story 3 — Knowledge projection (P2)

**Goal**: one managed knowledge row per family with a current version; it survives the indexer and is guarded.
**Independent test**: quickstart §3 and §5.

- [x] T024 [P] [US3] Write `tests/unit/patterns/test_projection.py`: kind mapping (reference-architecture → `reference_architecture`, others → `pattern`); `full_text` sections with empty parts omitted; metadata; id/source_ref `adp-pattern:<key>`.
- [x] T025 [US3] Implement `build_projection()` in `src/adp/patterns/projection.py`. Make T024 pass.
- [x] T026 [P] [US3] Extend `tests/unit/patterns/test_store.py`:
  - the first promotion creates an active row;
  - a second promotion updates the same id, and an existing `control_pattern_mapping` row survives;
  - deprecating the only current version → inactive;
  - rollback → active again;
  - drafts never project;
  - the embed callable is invoked outside the transaction (a fake records it).
- [x] T027 [US3] Add `embed_or_zero()` to `src/adp/knowledge/embedder.py` and switch `src/adp/api/routers/knowledge.py` to use it. Wire the projection upsert and deactivation (select-then-update/insert) into `store.transition()`. The router passes `asyncio.to_thread`-wrapped `embed_or_zero`. Make T026 pass.
- [x] T028 [P] [US3] Extend `tests/knowledge/test_indexer.py`: an active `adp-pattern:` item absent from every connector is NOT deactivated, and other items still are.
- [x] T029 [US3] Add `exclude_source_prefixes` to `get_active_ids` in `src/adp/knowledge/index.py` and pass it from `src/adp/knowledge/indexer.py`. Make T028 pass.
- [x] T030 [P] [US3] Extend `tests/contract/test_knowledge_api.py`: PUT/DELETE on a managed item → 409 with the registry message; POST with an `adp-pattern:` id → 422; other items are unaffected.
- [x] T031 [US3] Implement the managed-item guard in `src/adp/api/routers/knowledge.py`. Make T030 pass.
- [x] T032 [P] [US3] Extend `tests/contract/test_compliance_mappings_api.py`, plus the store unit test if present: mapping to a `reference_architecture` item → 200; to a `standard` item → 422. Update the existing rejection test to use `standard`.
- [x] T033 [US3] Widen the kind check and error message in `src/adp/compliance/store.py` (`upsert_pattern_mapping`). Make T032 pass.
- [x] T034 [P] [US3] Write `web/src/knowledge/KnowledgeItemRow.test.tsx` (new or extended): a managed item shows the "Managed by Patterns" link and no Edit/Delete.
- [x] T035 [US3] Implement the badge and hidden actions in `web/src/knowledge/KnowledgeItemRow.tsx`. Make T034 pass.

## Phase 6: User Story 4 — Views (P2)

**Goal**: deterministic structure, catalog and traceability flowcharts that parse in diagram-core.
**Independent test**: goldens match, and the vitest golden parse has zero errors.

- [x] T036 [P] [US4] Write `tests/unit/patterns/test_sanitize.py`: quotes, brackets, braces, pipes, `<script>`, `-->`/`==`/`-.` runs, `#`/`;`, emoji, 200 characters → `…` at 60, empty → `?`.
- [x] T037 [P] [US4] Write `tests/unit/patterns/test_render.py`:
  - goldens `goldens/{structure,catalog,traceability}__<fixture>.mmd` for each valid 934 fixture;
  - header provenance (digest prefix);
  - via → two edges;
  - prohibited/required hint edge syntax;
  - catalog depth 1/2/3 and the 40-node cap → `truncated`;
  - deprecated suffix;
  - unresolved → `unknown` class;
  - id collision-freedom;
  - a 50× shuffle determinism check.
- [x] T038 [US4] Implement `sanitize_label`, `render_structure`, `render_catalog`, `render_traceability` and the palette (research D10) in `src/adp/patterns/render.py`. Generate the goldens with `--update-goldens`, then review them by hand. Make T036–T037 pass.
- [x] T039 [P] [US4] Write `web/src/patterns/goldens.test.ts`: read every `tests/unit/patterns/goldens/*.mmd` via `fs` and assert the flowchart family parse has zero errors.
- [x] T040 [US4] Extend `tests/contract/test_patterns_api.py` for `GET .../views/{view}` (200; 422 for bad view or depth) and `POST /render` (structure only, nothing stored). Implement both routes, plus `GET /relations`, in `src/adp/patterns/router.py`, with the explicit `/render` and `/validate` rules in `enforcement.py`.
- [x] T041 [P] [US4] Write `web/src/patterns/FlowchartView.test.tsx`: it renders an SVG for a golden; a `<script>` label appears as text and is never executed; the source panel can be copied.
- [x] T042 [US4] Implement `web/src/patterns/FlowchartView.tsx` (parse → `autoLayout` → `renderToSvg`, research D11) and the Views tab (structure/catalog with depth/traceability) in `PatternVersion.tsx`. Make T041 pass.

## Phase 7: User Story 5 — Draft editing in the UI (P3)

**Goal**: validate, preview, save and delete drafts, and start a new version from any version.
**Independent test**: spec US5 acceptance scenarios.

- [x] T043 [P] [US5] Extend `tests/unit/patterns/test_store.py` and `tests/contract/test_patterns_api.py`:
  - PUT on a draft replaces definition/digest/name/summary and relations;
  - PUT with a key, version or kind change → 422 `U1`;
  - PUT on non-draft → 409;
  - `POST /validate` stores nothing;
  - DELETE on a draft → 204, and on the family's last version the family is gone; DELETE on non-draft → 409.
- [x] T044 [US5] Implement `update_draft`, `delete_draft` and `validate_only` in `store.py`, and PUT/DELETE/`POST /validate` in `router.py`. Make T043 pass.
- [x] T045 [P] [US5] Write `web/src/patterns/YamlEditor.test.tsx`: Validate shows issues and Save is blocked while errors exist; Preview renders the structure view; "New version" prefills ImportPanel.
- [x] T046 [US5] Implement `web/src/patterns/YamlEditor.tsx`, the draft-only Edit/Delete actions, "New version", and the corresponding hooks. Make T045 pass.

## Phase 8: User Story 6 — Export (P3)

**Goal**: current versions are written to `patterns/<key>@<version>.yaml`, byte-identical to the download.
**Independent test**: quickstart §6.

- [x] T047 [P] [US6] Write `tests/unit/export/test_patterns_export.py` (SQLite):
  - the file equals `get_yaml` byte-for-byte;
  - an unchanged cycle doesn't rewrite (mtime unchanged);
  - a version that stops being current → its file is removed;
  - filename validation rejects `..`, `/` and bad semver;
  - the cycle swallows errors with a warning.
- [x] T048 [US6] Implement `src/adp/export/patterns.py` (research D13) and the 5th lifespan task in `src/adp/api/app.py`. Make T047 pass.

## Phase 9: Seed & Polish

- [x] T049 Write the four `scripts/seed_data/patterns/*.yaml` files, citing `PRIN-*` principles (research D15), and `scripts/seed_patterns.py` (idempotent import + promote). Add a unit test that every seed YAML parses with zero errors and that, with the `PRIN-*` lookup set, R1 resolution is empty.
- [x] T050 [P] Re-export the registry public names from `src/adp/patterns/__init__.py`, without breaking the 934 `__all__` contract.
- [x] T051 Quality gates:
  - `pytest tests/ --ignore=tests/integration -q`;
  - coverage ≥ 85% on `src/adp/patterns`;
  - `ruff check src/`, `mypy src/`, `bandit -r src/adp/patterns src/adp/export/patterns.py`, `adp-generate --check`;
  - `cd web && npx tsc --noEmit && npm run test:run`.
- [x] T052 Live verification on local Postgres: `alembic upgrade head` (044); run quickstart §1–§7 including a Playwright UI walkthrough; downgrade and re-upgrade 044 once; delete scratch drafts. Fix quickstart drift.
- [x] T053 File follow-on beads (filed: ADP-4zn indexer sweep bug, ADP-ufu adp.search, ADP-wmu SA/TA authoring, ADP-8nq reverse lookups):
  - the knowledge indexer also deactivates API/CALM-created items (research D7 finding);
  - index patterns into `adp.search` for chat and global search;
  - SA/TA draft authoring;
  - reverse lookups (patterns citing a principle or control).

  Update the CLAUDE.md Recent Changes entry from "Planned" to "Implemented".

## Dependencies & Execution Order

- **Phase 2** blocks everything.
- **US1** (Phase 3) blocks US2–US6.
- **US2** blocks US3, because projection happens on transition.
- **US4** depends only on US1. It can run in parallel with US2/US3 once T012 is done.
- **US5** depends on US1. It uses the US4 `/render` route for Preview.
- **US6** depends on US2 (it needs current versions).
- **Phase 9** runs last.

## Parallel Opportunities

- Within each phase, every `[P]` test task can be written concurrently: they touch different files.
- After T014: frontend US1 (T015–T016) can run in parallel with backend US2 (T017–T018), and US4 rendering (T036–T038) can start, since it is pure code with no store dependency.

## Implementation Strategy

- **MVP**: Phases 1–4 (US1 + US2). That gives governed, importable and browsable patterns.
- **Increment 2**: US3 + US4, which connects patterns to the knowledge base and shows them visually.
- **Increment 3**: US5 + US6, then seed and polish.
- **Delivery**: one PR for the whole spec, matching 933/934 practice. Commit per phase.
