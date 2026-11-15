# Implementation Plan: EA Pattern Adoptions, Conformance & Discovery

**Branch**: `936-pattern-conformance` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/936-pattern-conformance/spec.md` (bead ADP-mmm.3, epic ADP-mmm). Sources: `docs/PATTERN-03`, the conformance/transition parts of `docs/PATTERN-04`, and the `docs/PATTERN-00` addendum.

## Summary

This feature adds pattern **adoptions** (a pattern applied to a domain, an application set or the whole portfolio, with authoritative role pins), a per-caller read-only **portfolio snapshot** built from the real registries, and a **pure engine**. The engine binds roles, evaluates implicit cardinality/evidence constraints and the declared CEL constraints, and **derives** the conformance status and transition plateau on every read; nothing is stored.

It also adds:
- anti-pattern **discovery** across the portfolio;
- conformance and transition **views** (935 dialect, goldens);
- the Adoptions UI with "Save as diagram";
- a dry-run **evaluate**;
- demo data: the `seed_retail.py` health bug is fixed, an event hub and hub-routed integrations are added, and the demo adoptions are seeded.

Migration `045`. No new permission and no new package.

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**:
- the existing stack;
- 934's `cel-expr-python` through the `CelEngine` adapter;
- 935's render, registry and FlowchartView;
- diagram-core `parseFlowchart` / `autoLayout` for Save as diagram.

**Zero new packages.**
**Storage**: PostgreSQL 16, migration `045` (3 tables). The snapshot and reports are ephemeral.
**Testing**:
- a pure engine suite over in-memory snapshots (written first);
- SQLite store suites;
- contract and authz tests;
- render goldens plus vitest parsing;
- Docker-gated migration test;
- component tests.

**Performance Goals**: a report in under 1 s at demo scale (SC-005). The snapshot uses about 13 queries regardless of estate size.
**Constraints**:
- `engine.py`, `snapshot.py`, the render additions and the status/plateau functions are pure;
- no status column (guard test);
- the per-caller snapshot never leaks gated attributes;
- literal routes come before `/{key}`.

**Scale/Scope**: about 6 backend modules (~1,800 lines), 1 migration, seed changes, about 6 frontend components, and roughly 150 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md, plus bead ADP-mmm.3 |
| ART-II Single source of truth | ✔ | Snapshot = read projection; derived status, never stored (guard test) |
| ART-III Machine-readable | ✔ | JSON reports, flowchart views, YAML dry-run |
| ART-IV TDD / QG-04 | ✔ | Engine fixtures and tests come before any DB or API work (tasks order); ≥ 85% on `adp.patterns` |
| ART-V Security | ✔ | Per-caller gated omission → `field_unavailable`; evaluation caps; pin validation; WRITE_PATTERN on writes |
| ART-VI Observability | ✔ | Adoption write log lines |
| ART-IX Provenance | ✔ | Reports carry version and digest; view header provenance |
| ART-X Deterministic | ✔ | Ordered bindings and findings; shuffle test |
| ART-XI Traceability | ✔ | Findings name the registry elements |
| ART-XII Visual language | ✔ | 935 palette extended from c4-theme colours; meaning also in labels |
| ART-XIII Typed contracts | ✔ | Closed enums, frozen models |
| ART-XV Schema evolution | ✔ | Reversible 045, Docker-gated up/down test |

No violations.

## Project Structure

```text
specs/936-pattern-conformance/  plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/patterns/
├── conformance_models.py   # NEW enums, report/finding/adoption models, exceptions
├── snapshot.py             # NEW PortfolioSnapshot, Scope, in_scope, GATED_FIELDS (pure)
├── engine.py               # NEW bindings, implicit+declared constraints, status, plateau, discover (pure)
├── snapshot_store.py       # NEW build_snapshot (mirrors + list_all_costs)
├── adoptions.py            # NEW adoption tables + CRUD + pin validation + version resolution
├── render.py               # + render_conformance, render_transition
└── router.py               # + adoption/conformance/discovery/evaluate routes (before /{key})
src/adp/store/migrations/versions/045_ea_pattern_adoption.py   # NEW
src/adp/authz/enforcement.py   # + ("POST", "/api/v1/patterns/evaluate") explicit rule
scripts/seed_retail.py          # fix health_score; + Enterprise Event Hub + hub integrations
scripts/seed_patterns.py        # + demo adoptions (idempotent)

tests/unit/patterns/  snapshots.py (builder) test_engine_bindings.py test_engine_constraints.py
                      test_engine_status.py test_engine_fixtures.py test_snapshot_store.py
                      test_adoptions_store.py test_render.py(+) goldens/(+) test_no_status_column.py
tests/contract/test_pattern_adoptions_api.py
tests/integration/test_migration_045.py
web/src/api/patterns.ts (+hooks)
web/src/patterns/ AdoptionsList.tsx AdoptionForm.tsx AdoptionPage.tsx PinsEditor.tsx FindingsTable.tsx
                  DiscoveryTab.tsx EvaluatePanel.tsx saveAsDiagram.ts adoptions.test.tsx
web/src/App.tsx (pass onGenerateDiagram to PatternsPage)
```

**Structure Decision**: extend `adp.patterns`. The engine and snapshot model are pure and separate from the DB loaders, so the engine is testable on in-memory fixtures (ART-IV gate).

## Complexity Tracking

None.
