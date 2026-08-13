# Implementation Plan: Objective Progress Tracking, Lifecycle Status & Theme Management

**Branch**: `915-objective-progress-tracking` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/915-objective-progress-tracking/spec.md`

## Summary

Adds a dated, editable progress history to `StrategicObjective` (`strategic_objective_progress`, one entry per objective per date), a derived `status` field computed from that history against the objective's existing target/direction (`proposed` / `active` / `at_risk` / `achieved`, plus a manually-set terminal `abandoned` with a required reason), and completes the lifecycle of the *already-existing* `strategic_themes` entity (adds `description`/`owner`/`priority`, adds single-item `GET`, `PATCH`, `DELETE` — only `POST`/list `GET` exist today). All additive to `src/adp/strategy/` (models.py/store.py/router.py) and `web/src/strategy/`/`web/src/api/strategy.ts` — no new package, no changes to any other domain.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core, mirroring `adp.strategy.store`'s existing `sa.Table`/raw-`sa.text()` style — no ORM), Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies. Zero new packages either side.
**Storage**: PostgreSQL 16 — one new table (`strategic_objective_progress`), one new column set on the existing `strategic_themes` table (`description`, `owner`, `priority`), one new column set on the existing `strategic_objectives` table (`status`, `status_reason`). Migration 026 (`down_revision = "025"`).
**Testing**: pytest (backend unit + contract, `AsyncMock`-based per `tests/contract/test_strategy_api_contract.py`'s established pattern for this exact package), Vitest + Testing Library (frontend).
**Target Platform**: Linux server (existing FastAPI/uvicorn deployment); browser (existing React SPA).
**Project Type**: Web application (existing `src/adp/strategy/` backend package + `web/src/strategy/` frontend directory) — additive to both, no new top-level project.
**Performance Goals**: No new performance requirement beyond the platform's existing read/write latency norms; status is computed on read from a small per-objective row set (bounded by the trend window, not the full history), not a heavy aggregate.
**Constraints**: None beyond the existing platform norms (typed boundaries, `extra="forbid"`); auditability for this domain is structured logging, not an append-only `AuditEntry` row (Ground-Truth Correction 4 below).
**Scale/Scope**: Demo-scale (existing seed data has a handful of objectives); no scale concern distinct from the rest of `adp.strategy`.

## Ground-Truth Corrections Carried From Spec *(repeated here because they change this plan's design, not just narrative)*

Direct reads of `src/adp/strategy/{models,store,router}.py` and migration `025_strategic_objectives.py` (not the source doc/bead, which predates this verification) established three facts that reshape the design below:

1. **`strategic_themes` already exists** as a real table (`id`, `name` unique, `created_at`) with `strategic_objectives.theme_id` already a proper FK. This plan's theme work is `ALTER TABLE` + new endpoints, never `CREATE TABLE` + a tag-to-FK backfill migration.
2. **There is no `users` table anywhere in this codebase.** Every existing "who did this" field (`AuditEntry.actor`, `strategic_objectives.owner`, `element_technology_tags.owner_team`) is a plain `TEXT` string, not a `UUID FK`. `strategic_themes.owner` and `strategic_objective_progress.recorded_by` follow that same convention — `TEXT`, populated from the same `_get_actor(request)` helper `adp.strategy.router` already defines (mirrors `adp.business.router`'s own copy of the same helper).
3. **The write-permission gate is `ActionType.WRITE_BUSINESS_ARCH`** via the existing `("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH)` prefix rule in `adp.authz.enforcement` — not a `strategy:write` action (the bead's informal shorthand; no such enum value exists). No new `ActionType`, no new enforcement rule — every new route in this feature already falls under the existing prefix.
4. **There is no audit mechanism this feature can write a real `AuditEntry` row to.** The `audit_entries` table (and the `lifecycle.py` pattern of appending to `design.audit_log`) is tightly coupled to `design_id`/`design_version` — neither exists for a `StrategicObjective`. This isn't unique to strategy: `src/adp/agents/provenance.py`'s own docstring states the established, deliberate precedent directly — "Business capabilities (and applications) have no `design_id`... Consistent with the rest of `adp.business`/`adp.application`, ART-IX is SHOULD there, satisfied by structured logging, not a real `AuditEntry`." `adp.strategy.router`/`store.py` currently have **zero** logging calls at all (confirmed by grep) — this feature is the first to add any, and does so by establishing the same structured-`logger.info(...)` convention `adp.business.router` already uses (e.g. `"business.capability.update id=%s actor=%s"`), not by inventing a new mechanism.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD mandatory) | Yes | This plan follows an approved spec (`spec.md`, checklist 16/16 pass); tasks.md will reference FR-IDs. |
| ART-II (model is source of truth) | Yes | `status` (for its 3 non-terminal values) is *never* written directly — always recomputed from `strategic_objective_progress` + the objective's own target/direction on read. No separate hand-maintained status field to drift. |
| ART-IV (TDD) | Yes | Contract tests for every new/changed endpoint before implementation; a dedicated unit-test file for the pure status-derivation function (no I/O, easy to drive from a table of cases) before it's wired into the router. |
| ART-V (security by design) | Yes | Threat model already in spec.md — reuses the existing `WRITE_BUSINESS_ARCH` gate, no new trust boundary, no secrets, no PII. |
| ART-VII (grounded AI only) | **N/A, explicitly out of scope** | Progress entries are human-entered only in this version (spec.md Assumptions) — no AI generation writes here. |
| ART-VIII (human-in-the-loop) | Yes | Marking an objective `abandoned` is an explicit, attributable human action requiring a stated reason — mirrors `adp.api.routers.lifecycle`'s explicit-transition-plus-reason shape (though not its `AuditEntry`-writing mechanism — see ART-IX row below). |
| ART-IX (provenance/auditability) | Yes (SHOULD-level, per existing domain precedent) | Every progress entry records `recorded_by` + `created_at` in the row itself; abandoning an objective and recording/editing progress each emit a structured `logger.info(...)` line — the established pattern for domains with no `design_id` to hang a real `AuditEntry` on (`adp.agents.provenance`'s own documented precedent for `adp.business`/`adp.application`, extended here to `adp.strategy`, which currently has no logging convention of its own to reuse). |
| ART-XIII (typed contracts) | Yes | All new request/response models are Pydantic v2 with `extra="forbid"`, matching every existing model in `adp.strategy.models`. |

No violations. **Complexity Tracking is not filled in** — nothing here departs from the established package/pattern shape.

## Project Structure

### Documentation (this feature)

```text
specs/915-objective-progress-tracking/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   └── strategy-progress-status-themes-api-contract.md
└── tasks.md              # Phase 2 output (/speckit.tasks — not this command)
```

### Source Code (repository root)

```text
src/adp/strategy/
├── models.py          # EXTEND: StrategicTheme (+description/owner/priority), StrategicThemeUpdate (new),
│                       #   StrategicObjective (+status/status_reason), ObjectiveStatus literal (new),
│                       #   ObjectiveProgressEntry/-Create/-Update (new), AbandonRequest (new)
├── store.py            # EXTEND: theme get/update/delete, progress CRUD, compute_status() pure function
├── router.py            # EXTEND: GET/PATCH/DELETE /themes/{id}, POST/GET/PATCH /objectives/{id}/progress,
│                        #   PATCH /objectives/{id}/abandon
└── __init__.py          # unchanged

src/adp/store/migrations/versions/
└── 026_objective_progress_status.py   # NEW: strategic_objective_progress table,
                                         #   ALTER strategic_themes (description/owner/priority),
                                         #   ALTER strategic_objectives (status/status_reason)

tests/unit/strategy/
├── test_strategy_models.py     # EXTEND: new model validation cases
├── test_strategy_store.py      # EXTEND: theme CRUD, progress CRUD
└── test_objective_status.py    # NEW: pure compute_status() unit tests (table-driven, no I/O)

tests/contract/
└── test_strategy_api_contract.py   # EXTEND: new endpoint contract cases

web/src/api/
└── strategy.ts          # EXTEND: theme update/delete hooks, progress hooks, status/abandon hooks,
                           #   StrategicTheme (+fields), StrategicObjective (+status/status_reason) types

web/src/strategy/
├── ThemeList.tsx              # EXTEND: description/owner/priority fields, edit, delete
├── ObjectiveDetail.tsx        # EXTEND: status badge, progress mini-history, abandon action
├── ObjectiveProgressForm.tsx  # NEW: record/edit a dated progress entry
└── *.test.tsx                 # EXTEND/NEW alongside each component above
```

**Structure Decision**: Everything lives inside the two directories this domain already owns (`src/adp/strategy/`, `web/src/strategy/` + `web/src/api/strategy.ts`) plus one new migration file — no new package, no new frontend directory. This mirrors `ADP-d8u.1`'s and `ADP-SPEC-054`'s own precedent of extending an existing thin package rather than introducing a sibling one for genuinely additive work.

## Complexity Tracking

*No entries — Constitution Check passed with no violations requiring justification.*
