# Tasks: EA Pattern Adoptions, Conformance & Discovery

**Input**: `/specs/936-pattern-conformance/`, with plan.md ✓, spec.md ✓, research.md ✓ (D1–D12), data-model.md ✓, contracts/rest-api.md ✓ and quickstart.md ✓.

**Tests**: Mandatory (ART-IV). The pure engine is driven entirely by in-memory snapshot fixtures before any DB or API work. Test tasks precede implementation and must fail first.

**Organization**:
- **US1:** conformance (P1)
- **US2:** adoptions, members, pins (P1)
- **US3:** transition plateau (P2)
- **US4:** discovery (P2)
- **US5:** views and Save as diagram (P3)
- **US6:** dry-run evaluate (P3)

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [x] T001 Create module skeletons: `src/adp/patterns/{conformance_models,snapshot,engine,snapshot_store,adoptions}.py`, plus `tests/unit/patterns/snapshots.py`, an in-memory snapshot builder (`SnapshotBuilder().app(...).integration(...).capability(...).build()`).

## Phase 2: Foundational — the pure engine (blocks every story)

- [x] T002 [P] Write `tests/unit/patterns/test_snapshot_model.py`:
  - `in_scope` for domain, application-set and portfolio scopes across all 7 element types (spec Edge Cases);
  - `cross_domain` true/false/null;
  - gated keys absent when in `unavailable_fields`.
- [x] T003 Implement `conformance_models.py` (data-model.md) and `snapshot.py` (`PortfolioSnapshot`, `Scope`, `in_scope`, `GATED_FIELDS`, evidence indexes). Make T002 pass.
- [x] T004 [P] Write `tests/unit/patterns/test_engine_bindings.py`:
  - a selector filters candidates within scope;
  - pins are authoritative (GT-8): a pin that fails the selector → `B2`; a missing pin → `B3`;
  - selector errors → `S:<role>`;
  - deterministic (name, id) order.
- [x] T005 [P] Write `tests/unit/patterns/test_engine_constraints.py`:
  - `K:<role>` min/max/unbounded and `K:<role>/<per>`;
  - `E:<rel>` with/without integration evidence, direction (publishes vs consumes), `via` first hop, `serves`/`realizes` evidence, `unverifiable` for an unsupported type pair, non-required relationships skipped;
  - the full polarity matrix;
  - non-bool → evaluation_error;
  - a missing gated key → field_unavailable, other missing keys → evaluation_error;
  - `L1` when `max_element_evaluations` is exceeded, with other constraints still evaluated;
  - `element_refs` capped at 100 with `truncated`.
- [x] T006 [P] Write `tests/unit/patterns/test_engine_status.py`: every row of the status table plus precedence, and plateau 0/1/all with `blocking`.
- [x] T007 Implement `engine.py` (`resolve_bindings`, `evaluate`, `compute_conformance_status`, `compute_transition_plateau`, `discover`; research D4/D5). Make T004–T006 pass.
- [x] T008 [P] Write `tests/unit/patterns/test_engine_fixtures.py` using the real 934 fixtures:
  - backbone + a snapshot with one direct cross-domain integration and a pinned hub → `non_conformant`, with `C1` naming that integration;
  - all-routed → no `C1`;
  - mesh discovery → the expected matches;
  - mesh-to-backbone → PL1 reached, PL2 blocked by C2;
  - a 50× shuffle → identical reports (minus the timestamp).

  Make them pass, fixing the engine where needed.

## Phase 3: User Story 2 — Adoptions, members, pins (P1) 🎯 MVP with US1

- [x] T009 Migration `src/adp/store/migrations/versions/045_ea_pattern_adoption.py` (data-model.md). Also `tests/integration/test_migration_045.py` (Docker-gated): constraints, partial uniques, CASCADE from family/domain/application, RESTRICT on the pinned version, up/down.
- [x] T010 [P] [US2] Write `tests/unit/patterns/test_adoptions_store.py` (SQLite):
  - create per scope type;
  - duplicate domain/portfolio/name → `DuplicateAdoptionError`;
  - scope_ref rules;
  - members replace;
  - pin validation (role exists in the resolved version, type matches, element exists per type);
  - a draft pin is refused;
  - version resolution (pinned / current / none → None);
  - delete removes members and pins.
- [x] T011 [US2] Implement `src/adp/patterns/adoptions.py` (tables with `sqlite_where` partial indexes, mirrors, CRUD, polymorphic existence check dispatched by element type). Make T010 pass.

## Phase 4: User Story 1 — Conformance (P1)

- [x] T012 [P] [US1] Write `tests/unit/patterns/test_snapshot_store.py` (SQLite mirrors):
  - the domain parent walk (L3 → L1 domain);
  - multi-domain apps;
  - apps with no links → `[]`;
  - integrations with endpoint domains and `cross_domain`;
  - gated attributes present/absent per permission set (`tco` via a stubbed `list_all_costs`);
  - a bounded query count (an event listener counts statements, independent of row count).
- [x] T013 [US1] Implement `snapshot_store.build_snapshot(session, permissions)` (research D3). Make T012 pass.
- [x] T014 [P] [US1] Write `tests/contract/test_pattern_adoptions_api.py`:
  - adoption CRUD, members, pins: 201/200/204/404/409/422;
  - 403 for Reviewer/SA/TA on writes;
  - reads open;
  - `GET /adoptions` is not captured by `/{key}`;
  - `GET .../conformance` against a seeded SQLite estate → the expected status and findings;
  - per-caller gating: a Reviewer gets `field_unavailable` / `indeterminate` on a `tco` constraint where an EA gets a decision;
  - `with_status=true`.
- [x] T015 [US1] Implement the adoption and conformance routes in `src/adp/patterns/router.py`, declared before `/{key}`, plus log lines. Make T014 pass, and keep `tests/authz/test_enforcement.py` completeness passing.
- [x] T016 [P] [US1] Write `tests/unit/patterns/test_no_status_column.py`: no `ea_pattern*` table on the metadata (or migration 045) has a column named like status, plateau or finding.

## Phase 5: User Story 3 — Transition (P2)

- [x] T017 [US3] Extend the contract tests: a transition adoption's report has `plateau`; non-transition patterns have `plateau: null`. Implement any routing gaps.

## Phase 6: User Story 4 — Discovery (P2)

- [x] T018 [US4] Contract tests plus the route: `GET /{key}/versions/{version}/discover` returns 200 for an anti-pattern and 422 otherwise.

## Phase 7: User Story 5 — Views and Save as diagram (P3)

- [x] T019 [P] [US5] Extend `tests/unit/patterns/test_render.py`:
  - conformance goldens (non-conformant and conformant) and a transition golden;
  - worst-first collapse with "+k more";
  - fail/warn label suffixes;
  - `blocked: C2` edge;
  - shuffle determinism.

  Then implement `render_conformance` / `render_transition`, generate and review the goldens, and confirm the vitest golden parse still passes.
- [x] T020 [US5] Contract tests plus the routes `GET /adoptions/{id}/views/{conformance|transition}` and `GET /adoptions/{id}/candidates/{role_key}`.

## Phase 8: User Story 6 — Dry-run evaluate (P3)

- [x] T021 [US6] Contract tests plus `POST /evaluate` (YAML or stored version, scope, pins; nothing stored; 422 with issues), with an explicit `WRITE_PATTERN` rule in `enforcement.py` and an enforcement test.

## Phase 9: Frontend

- [x] T022 [P] Write `web/src/patterns/adoptions.test.tsx`:
  - Adoptions list with status badges;
  - the form switches scope type (domain picker vs app multi-select);
  - PinsEditor offers only candidates of the role's type and shows 422 reasons;
  - FindingsTable lists codes and elements;
  - AdoptionPage shows the plateau for a transition;
  - the Discovery tab appears only for anti-patterns;
  - EvaluatePanel shows the report;
  - Save as diagram calls `onGenerateDiagram` with a flowchart seed;
  - write controls are hidden for a Reviewer.
- [x] T023 Implement:
  - the hooks in `web/src/api/patterns.ts`;
  - `AdoptionsList`, `AdoptionForm`, `AdoptionPage`, `PinsEditor`, `FindingsTable`, `DiscoveryTab`, `EvaluatePanel` and `saveAsDiagram.ts`;
  - the Patterns | Adoptions toggle in `PatternsPage`;
  - Discovery in `PatternVersion` and Evaluate in `YamlEditor`;
  - `App.tsx` passing `onGenerateDiagram` to `PatternsPage`.

  Make T022 pass, and keep tsc clean.

## Phase 10: Seed & Polish

- [x] T024 Fix `scripts/seed_retail.py`: health is set through `upsert_health_assessment` (GT-9). Add the Enterprise Event Hub, its tech-capability link and hub-routed `event` integrations (research D11).
- [x] T025 Extend `scripts/seed_patterns.py` with the demo adoptions (idempotent by name), and extend `tests/unit/patterns/test_seed_patterns.py` (adoption specs reference roles that exist in the seed patterns).
- [x] T026 Quality gates:
  - full backend suite;
  - coverage ≥ 85% on `src/adp/patterns`;
  - ruff, mypy `src/`, bandit, `adp-generate --check`;
  - web tsc and full vitest.
- [x] T027 Live verification (with the user's go-ahead):
  1. migration 045 up/down/up;
  2. `seed_retail.py --yes` → `seed_knowledge.py` → `seed_patterns.py`;
  3. quickstart §1–§6 via curl;
  4. a Playwright walkthrough including Save as diagram.

  Confirm the demo statuses match FR-024 (adjust the seed integrations if the engine says otherwise), and fix quickstart drift.
- [x] T028 File follow-on beads (Governance rollup, conformance history, version-change warnings) and update the CLAUDE.md Recent Changes entry.

## Dependencies & Execution Order

- **Phase 2 (pure engine)** blocks everything; it has no DB and no API.
- **US2 store (T009–T011)** and **snapshot store (T012–T013)** can run in parallel after Phase 2.
- **US1 API (T014–T015)** needs both.
- **US3/US4/US6** need T015.
- **US5 render (T019)** needs only Phase 2; its routes (T020) need T015.
- **Frontend** follows the API.
- **Seed** last; T027 depends on everything.

## Implementation Strategy

- **MVP**: Phases 1–4 (engine, adoptions, conformance via the API).
- **Then**: transition, discovery, views, dry run, UI, seed.
- **Delivery**: one PR, committing per phase.
