# Implementation Plan: Application Portfolio Management

**Branch**: `038-application-portfolio-management` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/038-application-portfolio-management/spec.md`

## Summary

Expand the application registry (ADP-SPEC-036) into a full APM capability across eight data categories, prioritized so the **business-value × technical-health (TIME) rationalization view** lands first. The primary requirement is FR-002: a read-only rationalization projection computed from `business_value` × `health_score`; the enabling addition is FR-001 (two 1–5 scores on `applications`). The rest of the epic adds identity, risk/compliance, cost (TCO), technical-fit, roadmap, governance, and quality attributes as independently-shippable slices. All monetary values are `Decimal`/NUMERIC; every write audits (ART-IX); sensitive categories gate on new action-based permissions (ADP-SPEC-004). No new runtime packages.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Pydantic v2, Alembic, TanStack Query v5 — all existing stack
**Storage**: PostgreSQL 16 — column additions on `applications`; new child tables (`application_cost`, `application_risk`, `application_contracts`, `application_quality_metrics`); `transformation_initiatives` + `application_initiative_links`. Money as `NUMERIC(14,2)`.
**Testing**: pytest (contract + unit, no DB via SQLite/mocks; integration via testcontainers), Vitest/Playwright (web)
**Target Platform**: Linux server (API) + browser (web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: registry/rollup queries use indexed columns; rationalization projection computed over the estate in a single query pass (no per-app N+1)
**Constraints**: money never float; sensitive fields never leak to unauthorized reads or aggregates; zero schema-drift-check failures
**Scale/Scope**: hundreds–low-thousands of applications; 8 user stories; ~4 new tables + 2 join/initiative tables + column additions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-II (Model is source of truth)**: ✅ APM attributes extend the canonical `applications` registry; technology stack stays in `element_technology_tags`, dependencies in `application_integrations` — referenced, not duplicated (FR-018).
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ new Pydantic v2 models (`extra="forbid"`); new enums emit to JSON Schema via `adp-generate`; `Decimal` for money.
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; migrations verified up/down.
- **ART-V (Security by Design)**: ✅ threat model in spec; new permission actions for cost/risk/governance; no-sensitive-data test extended.
- **ART-IX (Audit)**: ✅ every APM write emits an `AuditEntry`.
- **ART-XV (Governed schema evolution)**: ✅ contiguous reviewed migrations with down-revisions; numbering coordinated with feeders (see Phase 0).

**Result**: PASS — no violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/038-application-portfolio-management/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (money, scales, migration order, authz)
├── data-model.md        # Phase 1 — DDL + Pydantic models
├── checklists/
│   └── requirements.md  # Spec quality checklist (clarifications resolved)
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/application/
├── models.py        # + business_value/criticality, identity, hosting/arch/tech-debt on Application;
│                    #   new ApplicationCost, ApplicationRisk, ApplicationContract,
│                    #   ApplicationQualityMetric, TransformationInitiative models + enums
├── store.py         # + CRUD for the new child records + rationalization projection query
├── router.py        # + endpoints per story (scores, identity, risk, cost, technical, roadmap,
│                    #   governance, quality) + GET rationalization projection
└── rationalization.py  # NEW — TIME-quadrant projection (business_value × health_score)

src/adp/authz/
├── permissions.py   # + READ/WRITE actions for cost, risk, governance; PERMISSIONS_VERSION bump
└── roles.py         # grant the new actions to appropriate roles

src/adp/store/migrations/versions/
└── 012..019_*.py    # one migration per slice (see Phase 0 numbering)

generated/            # regenerated JSON Schema (adp-generate)

web/src/application/   # UI panels per category + a rationalization (TIME quadrant) view

tests/
├── contract/         # per-endpoint contract tests (authz, validation, audit)
├── unit/             # rationalization projection, TCO arithmetic, out-of-support flagging
└── integration/      # migration up/down, rollups, cascade-delete
```

**Structure Decision**: Extends the existing `src/adp/application` package and `web/src/application` — no new top-level modules except `rationalization.py`. Follows ADP-SPEC-036's established layout (models/store/router split).

## Phase 0 — Research & Decisions

Captured in [research.md](./research.md). Key decisions:

1. **Migration numbering** (resolves the FR-015 coordination). On-disk head is `011_searchable_items`. The three feeder beads each reserve a migration; APM assigns a **contiguous block**:

   | Migration | Slice | Bead |
   |---|---|---|
   | `012` | US1 — `business_value`, `business_criticality` on `applications` | (this epic) |
   | `013` | US2 — identity: business unit, business/technical owner, `lifecycle_status` | (this epic) |
   | `014` | US3 — `application_risk` (+ regulatory tags, EOL/EOS dates) | (this epic) |
   | `015` | US4 — `application_cost` (8 buckets × one-time+annual, currency, horizon) | **ADP-9x6** |
   | `016` | US5 — hosting model, architecture pattern, tech-debt flags | (this epic) |
   | `017` | US6 — `transformation_initiatives` + `application_initiative_links` | (this epic) |
   | `018` | US7 — `application_contracts` | (this epic) |
   | `019` | US8 — `application_quality_metrics` | (this epic) |
   | `020` | Business-fit feeders — `strategic_relevance` (capabilities) | **ADP-33v** |
   | `021` | Business-fit feeders — `maturity_level` (business capabilities) | **ADP-4ga** |

   Each `down_revision` chains to the previous. Feeders (015/020/021) keep their bead identity but slot into this sequence so numbers never collide.

2. **Money**: `NUMERIC(14,2)` columns, `Decimal` in Pydantic; ISO-4217 currency string; `horizon_years` smallint. Never float. (First monetary data in the codebase — establishes the convention.)

3. **Scales**: `business_value`, `business_criticality` = `SMALLINT NULL CHECK 1..5`, NULL = not assessed (distinct from 1). Consistent with `health_score`/`fit_score`.

4. **Authz**: sensitive categories (cost, risk, governance) get dedicated read + write actions; general application read does not grant them. Aggregates re-check the same permission before returning per-app sensitive values.

## Implementation Phases

> One phase per user story, in priority order. Each phase is independently shippable (migration + models + store + router + authz + tests + UI panel) and re-runs `adp-generate --check` + drift gate.

### Phase 1 — Setup
Migration chaining scaffold (012 base), `rationalization.py` skeleton, new permission actions in `permissions.py`/`roles.py` (+ `PERMISSIONS_VERSION` bump), shared enums.

### Phase 2 — US1 (P1, MVP): Business-value scores + TIME rationalization view
Migration 012; `business_value`/`business_criticality` on `Application` models + CRUD + audit; `rationalization.py` projection (assessed → quadrant from `business_value` × `health_score`; unassessed listed separately); `GET /api/v1/applications/rationalization`; web TIME-quadrant view. **Ships the epic's core value alone.**

### Phase 3 — US2 (P2): Identity & ownership
Migration 013; BU + business/technical owner + `lifecycle_status` (indexed); registry filters by BU and lifecycle; audit; UI.

### Phase 4 — US3 (P3): Risk & compliance register
Migration 014; `application_risk` (data classification, regulatory tags `TEXT[]`, security posture, DR/BC, EOL/EOS dates); out-of-support + expiring-soon queries; **sensitive-read authz path** (first use); no-sensitive-data test extended; UI.

### Phase 5 — US4 (P4): TCO & spend rollups (ADP-9x6)
Migration 015; `application_cost` (8 buckets × one_time+annual NUMERIC, currency, horizon); TCO = Σ(one-time)+Σ(annual)×horizon; per-BU rollup + run-vs-change; sensitive-read authz; Decimal round-trip tests; UI.

### Phase 6 — US5 (P5): Technical fit depth
Migration 016; hosting model, architecture pattern, tech-debt flags on `applications`; filters; surfaces flags in the technical-health view; UI.

### Phase 7 — US6 (P6): Lifecycle & roadmap
Migration 017; `transformation_initiatives` + `application_initiative_links` (planned_disposition); roadmap view (uses `time_classification` + retirement dates); UI.

### Phase 8 — US7 (P7): Ownership & governance
Migration 018; `application_contracts` (terms, renewal_date, SLA, sponsor, IT owner, decision rights); renewals-soon query; sensitive-read authz; UI.

### Phase 9 — US8 (P8): Quality & performance signals
Migration 019; `application_quality_metrics` (manual, advisory); quality panel; does not override `health_score`; UI.

### Phase 10 — Polish
APM data dictionary (ART-XVI), cascade-delete audit coverage, cross-category application detail view, `adp-generate` regen, full drift + no-sensitive-data gates.

> Feeder migrations 020 (ADP-33v) / 021 (ADP-4ga) are tracked by their own beads but numbered into this block; reparent them under the APM epic at `/speckit.taskstoissues`.

## Post-Design Constitution Re-Check

Re-evaluate after data-model.md: confirm (a) no float anywhere in cost paths, (b) every new write path emits an `AuditEntry`, (c) sensitive reads (risk/cost/governance) and their aggregates are gated, (d) all new models/enums appear in `generated/` after `adp-generate`. No anticipated violations.
