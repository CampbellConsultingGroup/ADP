# Implementation Plan: Capability ↔ Org Unit Mappings

**Branch**: `941-capability-org-mappings` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)
**Input**: `/specs/941-capability-org-mappings/spec.md` (bead ADP-55k.2, spec 2 of 4 in epic ADP-55k; clarified 2026-11-16).

## Summary

This feature connects 940's org units to the business capability model with one mapping table, `capability_org_mappings` (migration `049`). Each mapping has one of three roles:
- **owner**: L1/L2, at most one per capability;
- **performer**: L3, with an optional geography;
- **contributor**: L3.

Everything else is derived on read by a pure engine over a 4-query snapshot, never stored:
- effective owner (inherited);
- the outside-geography note;
- four finding lists (no owner, shared-service candidates counted by independent org-tree branch, unmapped L3s, owned with no performer);
- each org unit's footprint, including its descendant units.

UI:
- owner and performer chips plus an Organization expander on each Capabilities row;
- a Findings sub-tab on Business → Organization, which opens capabilities through the existing focus path;
- a footprint section in the org-unit panel.

No new permission and no new package (extends `adp.organization`).

## Technical Context

**Language/Version**: Python 3.12 (3.11+) and TypeScript 5.x + React 18 (existing).
**Primary Dependencies**: FastAPI, SQLAlchemy 2 async Core, Alembic, Pydantic v2, TanStack Query v5. **Zero new packages.**
**Storage**: PostgreSQL 16. Migration `049` (`down_revision="048"`) adds one table, 3 FKs (CASCADE / CASCADE / SET NULL), 2 CHECKs, a partial unique index (one owner) and an expression unique index (`COALESCE(geography_id,'')`).
**Testing**:
- pure engine tests (no DB) for effective owner, branch folding, geography containment, footprint grouping;
- SQLite store tests (level rules, duplicates, owner replace, delete cleanup incl. the geography merge);
- contract tests via `create_app()` (reviewer 403, 404/409/422 bodies);
- a not-stored guard test;
- export and seed checks;
- Docker-gated `test_migration_049.py` (indexes, CHECKs, cascades, down/up);
- vitest component tests under CI's coverage ratchet.

**Performance Goals**: every read is one snapshot (4 queries) plus in-memory work, linear in mappings × tree depth (≤ 3). It's well under 2 s at 300 capabilities / thousands of mappings (SC-005).
**Constraints**: findings, effective owner and footprint are never persisted (guard test); "one owner" is enforced in the DB as well as by the replace-only API; level rules are enforced in the store with messages naming the rule.
**Scale/Scope**:
- backend: `cap_mappings.py` ~250 lines, `cap_org_analysis.py` ~250, models +~120, router +~110, store +~40 (table, mirror, delete cleanup);
- export and seed edits;
- frontend: 3 new components plus 4 touched;
- about 70 backend and 25 frontend tests.

## Constitution Check

| Gate | Status | Notes |
|---|---|---|
| ART-I / QG-01 | ✔ | spec.md (clarified), bead ADP-55k.2 |
| ART-II | ✔ | Capability and org models untouched; the mapping is the only record of the relationship; findings/footprint derived |
| ART-IV | ✔ | Engine and store tests before code, contract tests before routes, component tests before UI |
| ART-V | ✔ | `WRITE_BUSINESS_ARCH` prefix rule; non-sensitive data; no bulk write |
| ART-IX | ✔ | Actor-attributed log line on every set/clear/add/remove |
| ART-XIII | ✔ | `Literal` role, `extra="forbid"`, DB CHECKs, rule-named 422s |
| ART-XV | ✔ | Reversible 049 with a Docker-gated test |

No violations. Post-design re-check: unchanged.

## Project Structure

```text
specs/941-capability-org-mappings/  spec.md plan.md research.md data-model.md quickstart.md contracts/rest-api.md checklists/ tasks.md

src/adp/store/migrations/versions/049_capability_org_mappings.py   NEW
src/adp/organization/store.py            + capability_org_mappings table, business_capabilities mirror,
                                           mapping cleanup in delete_org_unit / delete_geography (R3)
src/adp/organization/cap_mappings.py     NEW writes (set_owner, add, remove), build_snapshot, read assemblers
src/adp/organization/cap_org_analysis.py NEW pure: effective owner, geography note, findings, footprint
src/adp/organization/models.py           + mapping, findings, footprint models
src/adp/organization/router.py           + /capability-org-mappings routes, /org-units/{id}/footprint
src/adp/export/business_arch.py          + "organization" block on capability files
scripts/seed_retail.py                   + phase C4 mappings; WIPE_TABLES + capability_org_mappings

tests/unit/organization/test_cap_org_analysis.py   NEW (pure)
tests/unit/organization/test_cap_mappings_store.py NEW (SQLite)
tests/unit/organization/test_cap_org_analysis_not_stored.py NEW (guard)
tests/contract/test_capability_org_mappings_api.py NEW
tests/unit/export/test_business_arch_serialize.py  extended
tests/integration/test_migration_049.py            NEW (Docker-gated)
existing fixtures creating both bstore and ostore metadata: exclude the business_capabilities mirror

web/src/api/organization.ts              + mapping/findings/footprint types and hooks
web/src/business/CapabilityOrgPanel.tsx  NEW (owner chip + Organization expander editor)
web/src/business/OrgFindings.tsx         NEW (Findings sub-tab)
web/src/business/OrgUnitFootprint.tsx    NEW (footprint section)
web/src/business/CapabilityNode.tsx      + chips and expander
web/src/business/OrganizationTab.tsx     + Findings sub-tab, footprint in detail panel, onOpenCapability
web/src/business/BusinessPage.tsx        pass onOpenCapability (switch to Capabilities + focus)
```

**Structure Decision**: extend `adp.organization` (R1), with the 937/938 split: tables in store, logic module, pure engine.

## Delivery order (for /speckit.tasks)
1. Migration 049 and the Docker test; the table, mirror and fixture updates.
2. Pure engine, test-first (effective owner → geography note → findings → footprint), plus the guard test.
3. Store writes and snapshot, test-first on SQLite (level rules, duplicates, owner replace, delete cleanup).
4. Models, routes and contract tests.
5. Export and seed.
6. Frontend: hooks → capability row chips and expander (US1/US2) → Findings sub-tab (US3) → footprint (US4).
7. Gates, live quickstart with Playwright, CLAUDE.md, GitNexus.

## Complexity Tracking

| Deviation | Why | Simpler alternative rejected |
|---|---|---|
| Level rules in the store, not the DB | An FK can't check the far row's `level` (937 precedent) | A trigger: not used anywhere else in ADP, and harder to test on SQLite |
| Store-side merge before geography delete | The unique index includes `COALESCE(geography_id,'')`, so SET NULL alone could collide | Dropping the geography from the unique index: would allow exact duplicate "everywhere" performers |
