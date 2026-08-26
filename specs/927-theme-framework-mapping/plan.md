# Implementation Plan: Theme–Framework Mapping

**Branch**: `927-theme-framework-mapping` | **Date**: 2026-08-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/927-theme-framework-mapping/spec.md`

## Summary

Add `ThemeFrameworkMapping` — the third, deferred link named in COMPLY-05 (`docs/speckit-compliance-bundle_1.md`),
tracked as bead ADP-1ox. A coarse, many-to-many tag between a `StrategicTheme` and a `RegulatoryFramework`,
with no fields of its own beyond the two references — unlike the two sibling links already built in
`925-strategy-compliance-linkage` (which carry or reference a `compliance_status`), this is a grouping tag,
not an assessed relationship. Resolved during `/speckit.specify` as data-model-and-API-only for this pass;
UI surfacing is filed as a separate follow-on bead (ADP-0md, blocked on this spec).

Package placement and every structural choice below mirror `925-strategy-compliance-linkage`'s own
precedent directly: the link lives in `adp.strategy` (the domain that already reaches into other domains
via read-only mirror tables), with the reverse lookup on `adp.compliance.router` importing
`adp.strategy.store` through the `_get_strategy_session()` dependency 925 already added — reused verbatim,
not re-implemented. `StrategicTheme` gains `framework_ids: list[str]`, mirroring
`StrategicObjective.control_ids` exactly. Zero new `ActionType`, zero `PERMISSIONS_VERSION` bump — writes
reuse the existing `("/api/v1/strategy/", WRITE_BUSINESS_ARCH)` prefix rule. One new migration (`037`, one
table).

## Technical Context

**Language/Version**: Python 3.12 (backend) — no frontend file touched (data-model-and-API-only,
Clarifications 2026-08-26)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async (Core), asyncpg, Alembic, Pydantic v2 — all
existing stack; zero new packages
**Storage**: PostgreSQL 16 — one new table via migration `037` (`down_revision = "036"`):
`theme_framework_links`, composite PK `(theme_id, framework_id)`, `ON DELETE CASCADE` on both FK legs
(data-model.md). No new columns on any existing table.
**Testing**: pytest (unit — no DB, `link_theme_framework`/`unlink_theme_framework` duplicate-link 409 and
missing-target 404 semantics; contract — schema/response-shape against a SQLite fixture wiring
`adp.strategy`+`adp.compliance` tables together, mirroring 925's own two-domain fixture precedent;
integration — testcontainers PostgreSQL for the real cascade-delete behavior in both directions, Docker-
gated like every prior COMPLY-0x spec on this branch)
**Target Platform**: Linux server (API only this pass)
**Project Type**: Web application (existing `src/adp` backend); frontend untouched
**Performance Goals**: standard interactive-CRUD latency; the reverse lookup is a single JOIN scoped by
one `framework_id`, no N+1 (mirrors `list_objectives_for_control`'s own profile)
**Constraints**: ART-XIII typed contracts (`extra="forbid"` on the new `ThemeFrameworkLinkCreate` model);
migration owns FK/PK constraints, store-layer `Table()` objects DML-only (existing convention);
`adp.strategy` continues importing zero other domain packages at the store layer — framework existence
checks go through a same-physical-DB mirror table (research.md D1), not a cross-package store call
**Scale/Scope**: a handful of tags per Theme/Framework in the near term — no pagination added (matches
every prior COMPLY-0x and 925's own registry-scale assumption)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ART-I (SDD mandatory)**: ✅ spec.md's one open question (UI scope) was resolved directly with the
  user during `/speckit.specify` — zero `[NEEDS CLARIFICATION]` markers remained going into this plan.
- **ART-II (Model is the single source of truth)**: ✅ "which regulatory areas does this theme touch"
  becomes a typed, queryable fact (`StrategicTheme.framework_ids`) instead of something inferred from a
  theme's name or tracked in a side document.
- **ART-III / ART-XIII (Machine-readable / Typed contracts)**: ✅ one new Pydantic v2 model
  (`ThemeFrameworkLinkCreate`, `extra="forbid"`); `StrategicTheme` extended, not replaced. OpenAPI
  contract generated, not hand-maintained.
- **ART-IV (TDD)**: ✅ contract + unit tests precede handlers; the duplicate-link 409 and missing-target
  404 rules each get a dedicated unit test before router wiring, matching 925's own precedent for this
  exact class of bare-link feature.
- **ART-V (Security by Design)**: ✅ threat model in spec.md; writes reuse the existing
  `WRITE_BUSINESS_ARCH` permission (no `PERMISSIONS_VERSION` bump — held identically to `WRITE_COMPLIANCE`
  by the same personas, and the `/api/v1/strategy/` prefix rule already covers the new routes). The
  reverse-lookup route is ungated beyond general read access, matching `GET /controls/{id}/objectives`'s
  own precedent — no new authz surface at all this pass (research.md D4).
- **ART-VI (Observability)**: N/A beyond baseline — no AI/LLM step; standard structured request logging
  already covers every route via the existing FastAPI middleware.
- **ART-VII (Grounded AI)**: N/A — no AI generation involved.
- **ART-VIII (Human-in-the-loop)**: N/A — every link write is already a direct, attributable human
  action gated by `WRITE_BUSINESS_ARCH`; no automation trigger is introduced.
- **ART-IX (Provenance/Audit)**: `created_at` recorded on every link row; no `audit_entries` write,
  matching 925/COMPLY-01/02's own confirmed precedent that direct human CRUD on registry/traceability
  links does not write to the append-only audit trail.
- **ART-XI (Traceability)**: ✅ this spec *is* a traceability link — a `StrategicTheme` gaining a
  reusable-tag relationship to a `RegulatoryFramework`. Referential integrity is DB-FK-enforced on both
  legs via the composite PK.
- **ART-XV (Governed schema evolution)**: ✅ additive-only migration `037`; no `PERMISSIONS_VERSION` bump
  (no new `ActionType` — see ART-V above).

**Result**: PASS — no violations; Complexity Tracking not required. Every design choice traces to an
existing, directly-confirmed precedent (925's own package-placement, response-shape, and duplicate-link-
handling decisions applied one level up to a simpler, single-table pair) rather than inventing a new one.

## Project Structure

### Documentation (this feature)

```text
specs/927-theme-framework-mapping/
├── plan.md              # This file
├── research.md          # Phase 0 — D1–D4 decisions (package placement, response shape,
│                         #   duplicate-link handling, permission reuse)
├── data-model.md         # Phase 1 — DDL (1 table) + Pydantic model changes + store function inventory
├── contracts/
│   └── theme-framework-links-api.md  # Phase 1 — REST contract (link + reverse lookup)
├── quickstart.md         # Phase 1 — integration scenarios covering every acceptance scenario + edge case
├── checklists/
│   └── requirements.md   # Spec quality checklist (passed, zero clarification markers remaining)
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code Changes

```text
src/adp/strategy/                # EXISTING package — extended, not replaced
├── models.py                    # + ThemeFrameworkLinkCreate; StrategicTheme gains framework_ids
├── store.py                     # + _regulatory_frameworks mirror Table(); + _theme_framework_links
│                                 #   Table(); + framework_exists, link_theme_framework,
│                                 #   unlink_theme_framework, list_themes_for_framework (reverse,
│                                 #   called from adp.compliance.router); _row_to_theme/create_theme/
│                                 #   update_theme extended to populate framework_ids
└── router.py                    # + POST/DELETE .../themes/{id}/frameworks[/{framework_id}] (existing
                                  #   WRITE_BUSINESS_ARCH prefix rule, zero enforcement.py change)

src/adp/compliance/router.py     # + GET /frameworks/{framework_id}/themes (imports adp.strategy.store
                                  #   via the existing _get_strategy_session dep, added in 925 — reused
                                  #   verbatim, no new dependency code)

src/adp/store/migrations/versions/
└── 037_theme_framework_links.py   # 1 table, composite PK, ON DELETE CASCADE both legs (data-model.md)

tests/
├── contract/
│   └── test_theme_framework_links_api.py  # schema/response-shape — SQLite fixture wiring
│                                           #   adp.strategy + adp.compliance tables (mirrors 925's own
│                                           #   two-domain fixture)
├── unit/
│   └── strategy/
│       └── test_theme_framework_links.py  # duplicate-link 409, missing-target 404
└── integration/
    └── test_theme_framework_links_api.py  # testcontainers PostgreSQL: real cascade delete, both
                                            #   directions (theme delete, framework delete)
```

No `web/` file is touched this pass (Clarifications, 2026-08-26). No `tests/authz/test_enforcement.py`
change is needed — this feature introduces no new authz surface (research.md D4); existing
`/api/v1/strategy/` prefix-rule coverage already exercises the write gate generically.

**Structure Decision**: Extends the existing `adp.strategy` package (`models.py`/`store.py`/`router.py`)
and `adp.compliance.router` exactly as `925-strategy-compliance-linkage` already did for its own two
links — no new package, no frontend directory touched. One new migration (`037`).

## Complexity Tracking

*No Constitution Check violations — this section is not applicable.*
