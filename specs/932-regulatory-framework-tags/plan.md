# Implementation Plan: Regulatory Framework Tags for Application Risk & Compliance

**Branch**: `932-regulatory-framework-tags` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/932-regulatory-framework-tags/spec.md`

## Summary

`ApplicationRisk.regulatory_tags` is today an unvalidated `list[str]` of free text (e.g. `"SOX"`,
`"GDPR"`) with no relationship to the real `RegulatoryFramework` registry COMPLY-01 later built.
This feature replaces it with a governed many-to-many link (`ApplicationFrameworkTag`) between an
`Application` and a `RegulatoryFramework`, keeping the wire shape (`regulatory_tags: list[str]`,
now framework ids) and the existing `GET`/`PUT /applications/{app_id}/risk` endpoints and
permissions unchanged. Only frameworks whose `status` is `in_force`/`amended` can be newly tagged;
an existing tag survives its framework later changing status; deleting a framework cascades to
remove the tag. Pre-existing free-text values are discarded outright by construction — the new
join table starts empty for every application, because the old column is dropped rather than
migrated (research.md D6). The link table lives in `adp.application` (not `adp.compliance`),
mirroring `theme_framework_links`' (927) precedent for an unassessed, non-Compliance-owned tag.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing
stacks, no new language/version surface.
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic
v2, React 18, TanStack Query v5 — all existing project dependencies; zero new packages either side.
**Storage**: PostgreSQL 16 — one new migration (`041`, `down_revision="040"`): new table
`application_framework_tags` (composite PK, both legs `ON DELETE CASCADE`), and drops
`application_risk.regulatory_tags` (the now-superseded JSON column; research.md D6).
**Testing**: pytest (unit + contract, SQLite fixture mirroring every sibling COMPLY-0x/927 suite's
own pattern) + Docker-gated `testcontainers` integration suite (same environment constraint every
prior COMPLY-0x spec this project has hit — written, runs in CI); Vitest (frontend component
tests for the picker); Playwright (manual/E2E per quickstart.md Scenario 8).
**Target Platform**: Linux server (existing deployment target) + browser (existing web canvas).
**Project Type**: Web application (existing `src/` backend + `web/` frontend monorepo structure).
**Performance Goals**: N/A beyond existing — the Compliance framework registry is small
(single-digit to low-dozens of rows in practice); no new performance surface.
**Constraints**: No new permission, no new `ActionType`, no `PERMISSIONS_VERSION` bump (research.md
D1/D4) — existing `READ_APPLICATION_RISK`/`WRITE_APPLICATION_RISK` gates carry over unchanged.
**Scale/Scope**: One new table, one new migration, one modified store module
(`adp.application.store`), one modified model file, one modified frontend component
(`RiskPanel.tsx`), one modified frontend API type file (`web/src/api/compliance.ts`, add `status`),
one export-module fixture update (`adp.export.application_arch`'s tests, not its code).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (Spec-Driven Development) | Yes | Full `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` cycle completed before any code; this plan traces to spec.md's FR-001..009. |
| ART-II (Model is Single Source of Truth) | Yes | The entire point of the feature — `regulatory_tags` moves from a duplicated, arbitrary string to a reference into the canonical `RegulatoryFramework` registry. |
| ART-III (Machine-Readable) | Yes | `ApplicationFrameworkTag` is a typed SQLAlchemy table + Pydantic-validated API payload, not a free-text artifact. |
| ART-IV (TDD) | Yes | Contract tests (SQLite fixture) + unit tests for the diff/validate logic (research.md D4/D5) written before implementation; Docker-gated integration tests for the real cascade-delete behavior (research.md D6). |
| ART-V (Security by Design) | Yes | Threat model in spec.md; no new permission surface (research.md D1); server-side validation (not client-trust) for both existence and status (research.md D4). |
| ART-VI (Observability) | Partial, by established precedent | `PUT .../risk` already logs `application.risk.update id=%s actor=%s` (existing line, `application/router.py:316`) — unchanged, no new log statement needed since no new endpoint is added. |
| ART-VII (Grounded AI) | N/A | No AI step in this feature. |
| ART-VIII (Human-in-the-Loop) | N/A | Not a consequential/AI-driven mutation — a direct, human-initiated CRUD edit, same class as the rest of `ApplicationRiskUpdate` today. |
| ART-IX (Provenance/Auditability) | Not newly engaged | `ApplicationRisk` writes carry no append-only audit trail today (confirmed by direct code inspection — no `AuditEntry` usage anywhere in `adp.application.router`/`store`) and none of its sibling APM/Compliance link features introduced one either. This feature inherits that existing, pre-established gap rather than introducing a new one; closing it platform-wide is out of scope here. |
| ART-X (Deterministic Validation Gating) | N/A | No LLM-as-Judge involvement. |
| ART-XI (Traceability End to End) | Yes | This feature's entire purpose is repairing a traceability gap — an application's regulatory tag becomes referentially intact against a real framework record (FR-002), and a deleted framework can never leave a dangling reference (FR-005). |
| ART-XII (Fixed Visual Language) | N/A | No diagram/theme surface touched. |
| ART-XIII (Typed Contracts Everywhere) | Yes | `ApplicationRiskUpdate`/`ApplicationRisk` remain `extra="forbid"` Pydantic v2 models; the new mirror table and link table are typed SQLAlchemy Core tables, not dicts. |
| ART-XIV (Reproducible Builds) | Yes | Standard Alembic migration; no generated-artifact drift introduced. |
| ART-XV (Schema Evolution is Governed) | Yes, with a recorded breaking change | Dropping `application_risk.regulatory_tags` is a deliberate breaking change, justified here (research.md D6) and already resolved with the user via `/speckit.clarify` (Option B — discard outright) rather than silently patched over. |
| ART-XVI (Documentation as Code) | Yes | This plan, research.md, data-model.md, and the contract/quickstart docs are the record; spec.md's Clarifications section preserves the resolved decisions. |

**Gate result**: PASS. No unjustified violations; the one deliberate breaking change (ART-XV) is
justified and user-confirmed, not a gap.

## Project Structure

### Documentation (this feature)

```text
specs/932-regulatory-framework-tags/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── application-risk-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks — not created by this command)
```

### Source Code (repository root)

```text
src/adp/
├── application/
│   ├── models.py        # ApplicationRisk/ApplicationRiskUpdate — validation semantics only, wire shape unchanged
│   ├── store.py          # New _application_framework_tags table, new _regulatory_frameworks mirror,
│   │                      #   rewritten _row_to_risk/upsert_application_risk (diff + validate + reconcile)
│   └── router.py         # Unchanged routes; no code change expected beyond what store.py's new
│                          #   exceptions require the existing handler to surface as 422
├── export/
│   └── application_arch.py  # No code change (research.md D8); its own tests/fixtures updated
└── store/migrations/versions/
    └── 041_application_framework_tags.py   # New migration

tests/
├── unit/application/
│   └── test_application_risk_framework_tags.py   # New — diff/validate logic, status-gate edge case
├── contract/
│   └── test_apm_risk_api.py                       # Extended — existing file, new assertions + updated fixtures
└── integration/
    └── test_application_framework_tags.py         # New — Docker-gated, real cascade-delete behavior

web/src/
├── application/
│   └── RiskPanel.tsx     # Free-text input → framework checkbox/multi-select list
└── api/
    └── compliance.ts     # RegulatoryFramework interface gains `status` field
```

**Structure Decision**: Existing monorepo layout (`src/adp/<domain>`, `web/src/<area>`,
`tests/{unit,contract,integration}`) — no new top-level directory. The feature is additive to two
already-existing packages (`adp.application`, its one touched export consumer) plus one new
migration; no new package is created (research.md D1 — the link lives in the existing
`adp.application` package, not a new one).

## Complexity Tracking

*No Constitution Check violations require justification beyond the one recorded, user-approved
breaking schema change already covered under ART-XV above. This section is intentionally empty.*
