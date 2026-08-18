# Implementation Plan: Compliance Framework & Control Registry (COMPLY-01)

**Branch**: `921-compliance-framework-registry` | **Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/921-compliance-framework-registry/spec.md`

## Summary

Stand up the reference-data foundation for ADP's Compliance domain: a `RegulatoryFramework` registry
(NIST, GDPR, SOC 2, …) and a self-referencing `Control` hierarchy beneath each framework, with
framework-scoped code uniqueness and unbounded nesting depth (a framework can go family → control →
sub-control, and depth genuinely varies clause-by-clause within one framework — GDPR Art. 5 vs. Art. 33).
This is COMPLY-01 only, of a five-spec bundle (`docs/speckit-compliance-bundle_1.md`); COMPLY-02
(mappings), COMPLY-03 (derived status), COMPLY-04 (rollups), and COMPLY-05 (Strategy linkage) all build on
the stable IDs this registry creates, but none of that work happens here. New dedicated
`ActionType.WRITE_COMPLIANCE` gates all writes (Clarification Session 2026-08-17); reads stay ungated,
matching every other registry domain. New sibling package `adp.compliance`, not folded into `adp.business`
(research.md D1 — `adp.business`'s core files already exceed the historical split threshold). No new
runtime packages either side.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2, React 18, TanStack Query v5 — all existing stack; zero new packages
**Storage**: PostgreSQL 16 — two new tables (`regulatory_frameworks`, `controls`) via migration `032` (down_revision `031`, confirmed against the real on-disk chain — research.md D7); self-referencing FK with `ON DELETE CASCADE` (D2); composite `UNIQUE(framework_id, code)` (D6)
**Testing**: pytest (unit — no DB; contract — schema/authz; integration — testcontainers PostgreSQL for cascade/hierarchy behavior); Vitest (frontend unit/component)
**Target Platform**: Linux server (API) + browser (existing web canvas)
**Project Type**: Web application (existing `src/adp` backend + `web/` frontend)
**Performance Goals**: standard interactive-CRUD latency; framework detail fetch (full control tree) in a single query pass, no N+1 per control
**Constraints**: ART-XIII typed contracts (Pydantic `extra="forbid"` on every boundary model); migration owns FK/PK/UNIQUE constraints, store-layer `Table()` is DML-only (existing convention); no cycle/cross-framework validation possible at the DB layer — application-layer only (D5)
**Scale/Scope**: dozens of frameworks; up to a few hundred controls per framework (SC-005's 50+-control browsing scenario); unbounded hierarchy depth in the schema, though real frameworks are not expected to exceed a handful of levels in practice

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-I (SDD mandatory)**: ✅ this plan follows an approved spec that already passed `/speckit.clarify`.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ new Pydantic v2 models, `extra="forbid"`; OpenAPI contract generated, not hand-maintained. Note: unlike `adp.models`'s `ArchitectureDescription`, this registry is *not* part of the `adp-generate`/JSON-Schema pipeline (Article II's literal scope) — it's a standalone typed registry, the same architectural category as Business Capabilities and Applications, governed primarily by ART-XIII rather than ART-II's generator pipeline.
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; migration up/down verified; store-layer cycle/uniqueness validation (D5/D6) gets dedicated unit tests before wiring into the router, per the project's own validate-before-implement convention.
- **ART-V (Security by Design)**: ✅ threat model already in spec.md; new `WRITE_COMPLIANCE` permission + route-prefix rule + `PERMISSIONS_VERSION` bump (D4); `tests/authz/test_enforcement.py`'s completeness check extended to cover the new prefix.
- **ART-VI (Observability)**: N/A beyond the baseline — no AI/LLM step in this feature (pure CRUD), so the mandatory AI-span requirement (QG-11) doesn't apply; standard structured request logging already covers every route via the existing FastAPI middleware.
- **ART-VII (Grounded AI)**: N/A — no AI generation involved in COMPLY-01.
- **ART-VIII (Human-in-the-loop)**: N/A — no AI-proposes/human-confirms flow here; every write is already a direct, attributable human action gated by `WRITE_COMPLIANCE`.
- **ART-IX (Provenance/Audit)**: `created_at`/`updated_at` recorded on both entities; append-only `audit_entries` writes are **not** added, matching the confirmed precedent that direct human CRUD on Business Capabilities does *not* write to `audit_entries` either (that mechanism is reserved for design mutations and AI-suggestion applies) — verified by reading `adp.business.store`/`router.py` directly rather than assumed.
- **ART-XI (Traceability)**: this registry creates the stable IDs COMPLY-02's mapping links will target (spec.md's own ART-XI note); no orphan-detection concern at this layer — QG-16's orphan rule scopes to `ArchitectureDescription` elements, not this registry.
- **ART-XV (Governed schema evolution)**: ✅ additive-only migration `032`; `PERMISSIONS_VERSION` bump documented in `permissions.py`'s changelog, mirroring every prior bump's format.

**Result**: PASS — no violations; Complexity Tracking not required. Every design choice follows an existing, directly-confirmed precedent (Application registry's dedicated `ActionType`, Business Capability's tree-assembly shape, `create_capability`'s app-layer hierarchy validation) rather than inventing a new pattern.

## Project Structure

### Documentation (this feature)

```text
specs/921-compliance-framework-registry/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (package placement, delete semantics, authz, validation)
├── data-model.md         # Phase 1 — DDL + Pydantic models
├── contracts/
│   └── compliance-api.md # Phase 1 — REST contract
├── quickstart.md         # Phase 1 — integration scenarios
├── checklists/
│   └── requirements.md   # Spec quality checklist (passed, no iteration needed)
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/compliance/            # NEW package (research.md D1)
├── __init__.py
├── models.py                  # RegulatoryFramework(+Create/Update/ListResponse/Detail),
│                               # Control(+Create/Update/Node); typed exceptions
├── store.py                   # SQLAlchemy Core CRUD; cycle/cross-framework validation (D5);
│                               # tree assembly for RegulatoryFrameworkDetail.controls
└── router.py                  # /api/v1/compliance/frameworks[...], /controls[...] endpoints

src/adp/authz/
├── roles.py                   # + ActionType.WRITE_COMPLIANCE
├── permissions.py             # + grant to Solution/Technical Architect; PERMISSIONS_VERSION 1.8.0 → 1.9.0
└── enforcement.py             # + ("/api/v1/compliance/", ActionType.WRITE_COMPLIANCE) prefix rule

src/adp/api/app.py              # + app.include_router(compliance.router)

src/adp/store/migrations/versions/
└── 032_compliance_framework_registry.py   # regulatory_frameworks, controls (D2/D6/D7)

web/src/api/
└── compliance.ts               # TanStack Query hooks (mirrors web/src/api/business.ts's shape)

web/src/compliance/             # NEW — mirrors web/src/business/'s shape
├── CompliancePage.tsx          # framework list + create
├── FrameworkDetail.tsx         # framework fields + nested control tree
└── ControlTree.tsx             # tree render + add/edit/delete, mirrors CapabilityTree.tsx's shape

web/src/shell/                  # + new top-level nav entry (sibling to Business/Governance)

tests/
├── contract/
│   └── test_compliance_registry_api.py   # schema, authz-shape
├── unit/
│   └── compliance/
│       ├── test_models.py                # Pydantic validation (blank fields, extra="forbid")
│       └── test_store.py                 # cycle/cross-framework/uniqueness validation (D5/D6)
├── integration/
│   └── test_compliance_api.py            # testcontainers PostgreSQL: cascade delete, tree fetch
└── authz/
    └── test_enforcement.py               # extended: new prefix rule completeness

web/src/compliance/*.test.tsx   # Vitest component tests
```

**Structure Decision**: New top-level `src/adp/compliance` package (models/store/router three-file split,
the same shape `adp.business` started at before it grew) and a matching `web/src/compliance` frontend
directory — not an extension of `adp.business` or `adp.application` (research.md D1). No other existing
module's structure changes except the three `adp.authz` files (additive) and `api/app.py` (one new
`include_router` line).

## Phase 0 — Research & Decisions

Captured in full in [research.md](./research.md). Key decisions:

1. **Package placement** (D1): new sibling package `adp.compliance` — `adp.business`'s core files
   (2,920 lines) already exceed the ~2,800-line threshold that triggered `adp.strategy`'s own historical
   split; `adp.knowledge` is the wrong conceptual fit regardless of size.
2. **Delete semantics** (D2): DB-level `ON DELETE CASCADE` on both `framework_id` and self-referencing
   `parent_id` — a deliberate divergence from Business Capability's app-layer reject-on-children, required
   by spec FR-005/FR-013.
3. **Scope-before-delete** (D3): frontend-only, computed from the already-fetched tree — no new endpoint.
4. **Authorization** (D4): new `ActionType.WRITE_COMPLIANCE`, `PERMISSIONS_VERSION` 1.8.0 → 1.9.0, per
   Clarification Session 2026-08-17.
5. **Hierarchy validation** (D5): app-layer cycle/cross-framework checks, mirroring `create_capability`'s
   existing precedent for the identical class of un-DB-constrainable rule.
6. **Uniqueness** (D6): DB-level composite `UNIQUE(framework_id, code)`, not just an app-layer pre-check.
7. **Migration number** (D7): `032`, confirmed against the real chain head (`031`).
8. **No `level` column** (D8): depth is derived at read time, not stored — unbounded per spec Assumption.

## Implementation Phases

> One phase per user story, in priority order, per the spec's own P1/P2/P3 slicing. Each phase is
> independently shippable and demonstrable.

### Phase 1 — Setup
Migration `032` (both tables, all constraints/indexes); `adp.compliance` package skeleton; `ActionType.WRITE_COMPLIANCE` + `PERMISSIONS_VERSION` bump + enforcement prefix rule; router registered in `api/app.py`.

### Phase 2 — US1 (P1, MVP): Register a regulatory framework
`RegulatoryFramework` model + CRUD (create/list/get/update/delete, no cascade concern yet since no
controls exist); `web/src/compliance/CompliancePage.tsx` (list + create form). **Ships a working
framework catalog alone**, per the spec's own "delivers value on its own" independent-test framing.

### Phase 3 — US2 (P2): Build out a framework's control catalog
`Control` model + CRUD; app-layer cycle/cross-framework validation (D5); DB-level uniqueness (D6); tree
assembly for `RegulatoryFrameworkDetail`; `FrameworkDetail.tsx` + `ControlTree.tsx` (add control,
top-level or nested).

### Phase 4 — US3 (P3): Browse and maintain the control catalog
Full-tree read confirmed end-to-end; edit endpoints for both entities; cascading delete (D2) wired end to
end with the frontend's client-side scope disclosure (D3) before the confirm click.

### Phase 5 — Polish
`adp-generate` regen sanity check (confirm no drift — this registry isn't part of that pipeline, so this
step should be a no-op, worth confirming rather than assuming), full authz completeness gate, quickstart.md
scenarios run end-to-end against a live local stack.

## Post-Design Constitution Re-Check

Re-evaluated after `data-model.md`/`contracts/compliance-api.md`: confirms (a) no DB-unenforceable rule is
silently trusted — D5's cycle/cross-framework check has dedicated unit tests before router wiring, per
ART-IV; (b) `WRITE_COMPLIANCE` is the *only* new permission surface, correctly scoped to writes only,
reads remaining open (D4); (c) the migration is strictly additive (two new tables, no altered existing
table) — no major-version schema bump or ADR needed under ART-XV. No anticipated violations.
