# Implementation Plan: Strategy Domain Card on the Overview Dashboard

**Branch**: `051-strategy-landing-card` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/051-strategy-landing-card/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

A fifth "Strategy" domain card on `OverviewPage.tsx`, matching the existing four cards' visual/structural shape exactly. Unlike those four — whose mini-stats are all computed client-side from list data the page already fetches for other reasons — Strategy's linkage-health split (FR-004/005) and fiscal-period breakdown (FR-007/008) need per-objective link and date-comparison facts the existing `GET /api/v1/strategy/objectives` list response doesn't carry, and FR-008 requires the fiscal comparison to be anchored to the server's clock, not the browser's. Rather than inventing a new pattern, this plan follows the one dashboard-aggregate precedent that already exists in the codebase: `adp.api.routers.portfolio`'s `GET /api/v1/portfolio/summary` (raw server-side SQL aggregation, purpose-built response model, already consumed by this same Overview page for the design-lifecycle donut chart). `adp.strategy` gets one new store function and one new `GET /api/v1/strategy/summary` endpoint computing all four card facts in a single query pass; the frontend adds one new hook and one new domain-card entry to the existing `DOMAINS` array.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: None new. FastAPI, SQLAlchemy 2 async (Core, raw `sa.text()` for the aggregate query — mirroring `adp.api.routers.portfolio`'s own established pattern for this exact kind of read), Pydantic v2, React 18, TanStack Query v5 — all existing project dependencies.
**Storage**: PostgreSQL 16 — no migration. Reads existing tables only (`strategic_objectives`, `strategic_themes`, `strategic_objective_capabilities`, `strategic_objective_value_streams`), all already present from migration 025 (ADP-d8u.1).
**Testing**: pytest (backend contract test for the new endpoint, unit test for the new store aggregate function, mirroring `adp.portfolio`'s own summary-endpoint test conventions) + Vitest/RTL (frontend, mirroring `OverviewPage.tsx`'s existing hook-mocking convention where a test exists, or the `vi.mock(hooks-module)` convention established across specs 046–050 otherwise).
**Target Platform**: Existing `adp-api` process (Linux server) + browser (existing `web/` SPA) — no new deployable.
**Project Type**: Web application — this feature adds to both sides of the existing FastAPI backend + React frontend split.
**Performance Goals**: None specific beyond "a dashboard load stays fast" — the new aggregate query is a small number of `COUNT`/`GROUP BY` passes over tables at the same modest scale every other ADP business-registry table already assumes (tens to low hundreds of rows); no N+1 risk since this is one query, not one query per objective.
**Constraints**: No new persisted field, no migration (spec FR-011). No progress/completion metric (spec FR-003 — out of scope, no underlying field exists). The card's read surface stays ungated like the rest of the Overview dashboard (spec FR-012, Assumptions) — `enforce_route_permission` is a documented no-op for GET, so no `ActionType` change is needed either.
**Scale/Scope**: 1 new backend read endpoint + 1 new store aggregate function inside the existing `adp.strategy` package (no new package, no new file). 1 modified frontend file (`OverviewPage.tsx`, one new `DOMAINS` entry) + 1 new hook in `web/src/api/strategy.ts`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, zero `NEEDS CLARIFICATION`) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II (Model is Source of Truth) | Yes | Every figure on the card is a live read of already-canonical rows (`strategic_objectives`, `strategic_themes`, their link tables) — nothing new is stored, nothing is derived-and-cached. |
| ART-III (Machine-Readable) | Yes | The concrete instance of the platform's own stated thesis, now applied to the one domain that was exempt from it: a governance signal (unlinked/past-due objectives) rendered from the model instead of requiring a manual audit. |
| ART-IV (TDD) | Yes | tasks.md will sequence a failing backend contract test (new endpoint) and a failing store unit test (new aggregate function) before their implementation tasks, then a failing frontend test for the new card before its implementation. |
| ART-V (Security by Design) | Yes | Threat model in spec.md: read-only aggregate over already-readable data, no new write path, no new authorization mechanism. |
| ART-VI (Observability) | Yes | The new endpoint gets the same structured request logging every other ADP read route already gets — no bespoke logging path. |
| ART-VII, ART-VIII, ART-IX, ART-X, ART-XI | No | No AI-generated content, no AI proposal to confirm, no new audit-trail obligation (nothing is written), no validation gating, no traceability-thread change. |
| ART-XII (Fixed Visual Language) | Yes (loosely) | The new card must match the four existing domain cards' established shape — enforced by construction, since it's added as one more entry to the same `DOMAINS` array/render loop, not a bespoke component. |
| ART-XIII (Typed Contracts) | Yes | The new `GET /api/v1/strategy/summary` response is a Pydantic v2 model with `extra="forbid"`, matching every other ADP boundary — mirrors `PortfolioSummaryResponse`'s own shape. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | N/A | No schema change — no migration, so nothing to keep drift-free or govern. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md + contracts/ are the documentation, each decision grounded in a direct read of the precedent it follows. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — the one real design choice (a new aggregate endpoint) reuses an already-established pattern (`adp.portfolio`'s own summary endpoint) rather than inventing one; every other decision is purely additive to `adp.strategy`, which already exists.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive, precedent-following design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/051-strategy-landing-card/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── strategy-summary-api.md   # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/strategy/store.py                # MODIFIED: + get_summary_stats(session) — one
                                          #   raw-SQL aggregate query pass (mirrors
                                          #   adp.api.routers.portfolio.get_portfolio_summary's
                                          #   sa.text() pattern) returning objective/theme
                                          #   counts, linked/unlinked split, and the
                                          #   current/upcoming/past-due fiscal split —
                                          #   fiscal "now" anchored via the DB server's own
                                          #   NOW(), never Python's local clock.

src/adp/strategy/models.py               # MODIFIED: + StrategicSummaryResponse
                                          #   (extra="forbid", mirrors PortfolioSummaryResponse's
                                          #   shape: total_objectives, total_themes,
                                          #   linked_count, unlinked_count, current_period_count,
                                          #   upcoming_count, past_due_count)

src/adp/strategy/router.py               # MODIFIED: + GET /api/v1/strategy/summary
                                          #   (reads only, no permission check needed beyond
                                          #   normal auth — enforce_route_permission is a
                                          #   documented no-op for GET)

web/src/api/strategy.ts                  # MODIFIED: + StrategicSummary type + useStrategySummary()
                                          #   hook, mirroring web/src/api/portfolio.ts's
                                          #   usePortfolioSummary() hook shape exactly

web/src/overview/OverviewPage.tsx        # MODIFIED: + useStrategySummary() call, + one new
                                          #   entry in the existing DOMAINS array (mini-stats +
                                          #   tiles), + the linkage-health and fiscal-breakdown
                                          #   warning-state rendering for that entry

tests/unit/strategy/test_strategy_store.py      # MODIFIED: + tests for get_summary_stats
tests/contract/test_strategy_api_contract.py    # MODIFIED: + tests for GET .../summary
web/src/overview/OverviewPage.test.tsx          # NEW (none exists today — confirmed absent
                                                 #   during Phase 0 research) or MODIFIED if
                                                 #   research finds one was added since
```

**Structure Decision**: No new package, no new migration — this feature is purely additive to the already-existing `adp.strategy` package (one new store function, one new response model, one new router endpoint) and to `OverviewPage.tsx` (one new hook call, one new array entry). The one genuinely new pattern — a dedicated dashboard-aggregate endpoint — is not new to the *codebase*, only to `adp.strategy`: it mirrors `adp.portfolio`'s `GET /api/v1/portfolio/summary`, the exact same shape already proven and already consumed by this same `OverviewPage.tsx` for its design-lifecycle donut chart.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
