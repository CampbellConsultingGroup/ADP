# Implementation Plan: EA Pattern Registry, Lifecycle & Patterns Screen

**Branch**: `935-pattern-registry` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/935-pattern-registry/spec.md` (bead ADP-mmm.2, epic ADP-mmm). Sources: `docs/PATTERN-02`, the structure/catalog/traceability parts of `docs/PATTERN-04`, and the `docs/PATTERN-00` addendum.

## Summary

This feature persists 934's `PatternDefinition` as governed, versioned artifacts. It adds:
- **Registry:** families and versions with a 5-state lifecycle, immutable after `draft`, and one `current` version enforced by a partial unique index.
- **YAML in and out:** idempotent YAML import, and byte-identical YAML download and export.
- **Reference resolution:** warnings in drafts, blocking at promotion.
- **Governance:** reason + confirmation on every transition, with a persisted lifecycle history.
- **Knowledge projection:** each family's current version is written into `knowledge_items` as one managed row. The indexer is exempted, the knowledge routes are guarded, and the compliance mapping is widened to `reference_architecture`.
- **Views:** pure, deterministic structure, catalog and traceability views in the in-app flowchart dialect, with goldens parsed in vitest.
- **Export:** a 5th export task.
- **UI:** a new Patterns screen.

Migration `044`. `PERMISSIONS_VERSION` 1.11.0.

## Technical Context

**Language/Version**: Python 3.12 (3.11+ compatible) and TypeScript 5.x + React 18. Both are existing stacks.
**Primary Dependencies**:
- backend: FastAPI, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, pgvector, plus 934's `adp.patterns` (with `cel-expr-python`);
- frontend: TanStack Query v5 and the vendored diagram-core (`parse`, `autoLayout`, `renderToSvg`).

**Zero new packages.**
**Storage**:
- PostgreSQL 16, migration `044`: 4 new tables (research D2).
- Writes to the existing `knowledge_items` table (no schema change).
- Filesystem export under the existing opt-in export root.

**Testing**:
- pytest unit tests: pure functions + a SQLite store;
- contract tests: full app on SQLite;
- authz tests;
- export unit tests;
- Docker-gated integration tests: migration, real concurrency, pgvector;
- Vitest: components + golden parsing.

**Target Platform**: Linux server and browser (existing).
**Project Type**: web service + SPA (existing `src/adp` + `web/`).
**Performance Goals**: catalog list and version detail feel instant at demo scale (tens of patterns). Rendering any view takes under 50 ms. Promotion latency is dominated by one embedding call (under 1 s warm).
**Constraints**:
- The 934 library modules stay unchanged.
- `lifecycle.py`, `render.py`, `resolve.py` and the projection text builder are pure.
- No `postgresql.insert().on_conflict` in paths exercised by SQLite tests (research D6).
- Every non-GET route maps to an action.
- Rendered views parse in diagram-core with zero errors.

**Scale/Scope**: about 8 backend modules (~1,600 lines), 1 migration, 1 export module, about 9 frontend components, and about 120 new backend + 30 frontend tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| ART-I Spec-driven / QG-01 | ✔ | spec.md, plus bead ADP-mmm.2 |
| ART-II Single source of truth | ✔ | The definition JSONB is canonical. The knowledge row is derived and write-protected (FR-015). Relation rows are rebuilt from the definition |
| ART-III Machine-readable | ✔ | YAML in and out, JSON views, export tree |
| ART-IV TDD / QG-04 | ✔ | Matrix, idempotency and golden tests come first (tasks order). Coverage target ≥ 85% on `adp.patterns` |
| ART-V Security / QG-06, QG-07 | ✔ | Threat model in spec. 256 KB body cap before parsing; 934 hardened parser; filename grammar for export; label sanitisation; role gating server-side |
| ART-VI Observability | ✔ | Structured log lines per write (contract) |
| ART-VII Grounded AI | ✔ | Only `current` (confirmed) content reaches the knowledge base that agents cite |
| ART-VIII Human confirmation | ✔ | `GOVERN_PATTERN` ∈ `REQUIRES_CONFIRMATION`; `confirmation_id` required and persisted (research D5) |
| ART-IX Provenance | ✔ | Lifecycle history table + log lines. View provenance header carries key, version and digest |
| ART-X Deterministic gating | ✔ | Pure lifecycle, resolution and rendering; shuffle-determinism test |
| ART-XI Traceability | ✔ | Traceability view; relations; projection makes patterns mappable to controls |
| ART-XII Fixed visual language | ✔ | Palette drawn only from `c4-theme.json` hexes (research D10) |
| ART-XIII Typed contracts | ✔ | Closed enums for lifecycle, import status and view kind; frozen `extra="forbid"` models |
| ART-XIV Drift-free builds | ✔ | No new dependency. `adp-generate --check` is unaffected (no schema-generated model changes; 934's schema unchanged) |
| ART-XV Schema evolution | ✔ | Reversible migration `044` with named constraints, plus integration up/down test |
| ART-XVI Docs as code | ✔ | quickstart, contracts, CLAUDE.md entry |

There are no violations. Re-checked after design: unchanged. Both deviations from the source bundle (no target FK, no principle/control link tables) are documented in research D2 and simplify rather than add.

## Project Structure

### Documentation (this feature)

```text
specs/935-pattern-registry/
├── plan.md
├── research.md          # D1–D16
├── data-model.md        # 4 tables, state machine, API models, issue codes, projection
├── quickstart.md
├── contracts/rest-api.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
src/adp/patterns/
├── registry_models.py   # NEW  PatternLifecycle, ImportStatus, PatternViewKind, summaries/detail, requests, exceptions
├── lifecycle.py         # NEW  allowed_transitions() (pure)
├── resolve.py           # NEW  reference resolution → R1–R4 issues (pure over lookup sets)
├── projection.py        # NEW  build_projection(defn) → ProjectedItem (pure)
├── render.py            # NEW  sanitize_label, render_structure/catalog/traceability (pure)
├── store.py             # NEW  Core tables + mirrors; import/update/delete/transition/list/get/relations
├── router.py            # NEW  /api/v1/patterns
└── __init__.py          # + registry public names (render, lifecycle, models)
src/adp/store/migrations/versions/044_ea_pattern_registry.py   # NEW
src/adp/authz/roles.py        # + WRITE_PATTERN, GOVERN_PATTERN
src/adp/authz/permissions.py  # 1.11.0 changelog, REQUIRES_CONFIRMATION += GOVERN_PATTERN
src/adp/authz/enforcement.py  # prefix rule + explicit lifecycle/validate/render rules
src/adp/knowledge/embedder.py # + embed_or_zero()
src/adp/knowledge/index.py    # get_active_ids(exclude_source_prefixes=...)
src/adp/knowledge/indexer.py  # pass ("adp-pattern:",)
src/adp/api/routers/knowledge.py  # use embed_or_zero; managed-item guard (409/422)
src/adp/compliance/store.py   # accept reference_architecture
src/adp/export/patterns.py    # NEW  run_reconciliation_cycle + start/stop
src/adp/api/app.py            # include patterns router; 5th export task
scripts/seed_patterns.py      # NEW
scripts/seed_data/patterns/*.yaml  # NEW (4)

tests/unit/patterns/  test_lifecycle.py test_resolve.py test_projection.py test_render.py
                      test_sanitize.py test_store.py conftest.py(+--update-goldens) goldens/*.mmd
tests/contract/test_patterns_api.py                       # NEW
tests/contract/test_knowledge_api.py, test_compliance_mappings_api.py   # extended
tests/knowledge/test_indexer.py                            # extended
tests/authz/test_permissions.py, test_enforcement.py       # extended
tests/unit/export/test_patterns_export.py                  # NEW
tests/integration/test_migration_044.py, test_pattern_registry.py      # NEW (Docker-gated)

web/src/api/patterns.ts                  # NEW
web/src/patterns/  PatternsPage.tsx PatternFamily.tsx PatternVersion.tsx ImportPanel.tsx
                   LifecycleDialog.tsx YamlEditor.tsx FlowchartView.tsx IssueList.tsx
                   permissions.ts index.ts  *.test.tsx goldens.test.ts      # NEW
web/src/shell/index.ts, web/src/ui/AppShell.tsx, web/src/App.tsx   # nav wiring
web/src/knowledge/KnowledgeItemRow.tsx   # managed badge, hide edit/delete
```

**Structure Decision**: extend the existing `adp.patterns` package (research D1), with cross-domain reads through mirror tables. The frontend gets a sibling feature folder, like `web/src/agentic/`.

## Key design points

1. **Import pipeline**, in one transaction:
   1. size cap;
   2. `parse_pattern_yaml(text, default_engine())`, with any error rejected;
   3. batch reference lookups → R-warnings;
   4. idempotency check against `(key, version)` and the family kind;
   5. insert family (if new) + version + relation rows.
2. **Promotion**:
   1. compute the projection and embedding **outside** the transaction (`asyncio.to_thread`);
   2. in the transaction: re-parse the stored definition, resolve at error level, demote the old current version (event `caused_by`), update the version, insert the event, upsert the knowledge row;
   3. `IntegrityError` on the partial index → 409.
3. **Leaving `current`**: when no current version remains, the knowledge row gets `active=false`. Rollback re-activates it with fresh content.
4. **Views** are rendered server-side (pure Python, goldens). The client only parses, lays out and renders SVG, so 936 can reuse the same renderer for its conformance views.
5. **UI gating** is cosmetic (`canManagePatterns`). The server's prefix and explicit rules are authoritative.

## Complexity Tracking

None.
