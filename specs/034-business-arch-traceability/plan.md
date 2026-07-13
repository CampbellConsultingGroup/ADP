# Implementation Plan: Business Architecture Traceability

**Branch**: `034-business-arch-traceability` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/034-business-arch-traceability/spec.md`

## Summary

Link business capabilities and value streams to solution architecture designs, creating the navigable chain from business intent to technical implementation (ART-XI direct realisation). Two join tables (`capability_design_links`, `value_stream_design_links`) added via migration 008. Seven new API endpoints extend the existing `adp.business` router. Three new frontend components add link management UI to capability nodes, value stream detail, and design intake views. Zero new packages.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend)
**Primary Dependencies**: FastAPI ≥ 0.111, SQLAlchemy 2 async, asyncpg, Pydantic v2, TanStack Query v5 — all existing stack; zero new packages
**Storage**: PostgreSQL 16; two new join tables (`capability_design_links`, `value_stream_design_links`) via Alembic migration 008; composite PK on both; `ON DELETE CASCADE` for both FK legs
**Testing**: pytest (backend unit + integration), Vitest (frontend), testcontainers-python (PostgreSQL container for integration tests)
**Target Platform**: Linux server (FastAPI/uvicorn) + browser SPA (Vite/React)
**Project Type**: web-service + web-app
**Performance Goals**: Link list endpoints respond in < 100ms (pure join query, no vector/LLM); design picker returns first page of designs within the existing portfolio query budget
**Constraints**: Composite PK enforces uniqueness (no duplicates); FK CASCADE enforces referential integrity; no changes to `ArchitectureDescription` JSONB schema
**Scale/Scope**: Expected ≤ 100 designs per capability in v1; ≤ 50 truncation per spec

## Constitution Check

| Article | Status | Notes |
|---------|--------|-------|
| ART-I (Spec-Driven) | ✅ PASS | Spec 034 exists with FRs, acceptance criteria, threat model |
| ART-II (Model is Source of Truth) | ✅ PASS | Links stored in separate join tables; `ArchitectureDescription` JSONB unchanged; links are relational metadata, not model content |
| ART-III (Machine-Readable) | ✅ PASS | All responses have Pydantic schemas; `extra="forbid"` on all models |
| ART-IV (TDD) | ✅ PASS | Tests written before implementation per tasks phase ordering |
| ART-V (Security) | ✅ PASS | Write endpoints gate on authenticated actor; same auth middleware as existing routes; no secrets in links; FK cascade prevents orphan injection |
| ART-VI (Observability) | ✅ PASS | All mutations emit structured `logger.info()` with actor, entity, action |
| ART-VII (Grounded AI) | ✅ N/A | No LLM involvement |
| ART-VIII (Human-in-Loop) | ✅ PASS | Link creation is a human action; no AI writes to model |
| ART-IX (Provenance/Audit) | ⚠️ SHOULD via logging | ART-IX is SHOULD for this feature (per spec). Structured logging satisfies observability. Writing to `audit_entries` requires loading + resaving the full `ArchitectureDescription` (to avoid ID collisions), creating spurious design versions. Decision 3 in research.md records this justification. |
| ART-X (Deterministic Validation) | ✅ N/A | No validation gate; feature is data CRUD only |
| ART-XI (Traceability End to End) | ✅ DIRECT REALISATION | This feature IS the business-tier traceability link |
| ART-XII (Fixed Visual Language) | ✅ N/A | No diagram changes |
| ART-XIII (Typed Contracts) | ✅ PASS | `DesignLinkCreate`, `DesignRef`, `CapabilityRef`, `ValueStreamRef`, `BusinessContextResponse`, `LinkedDesignsResponse` — all with `extra="forbid"` |
| ART-XIV (Drift-Free Builds) | ✅ PASS | No generated artifacts affected; `adp-generate --check` unaffected |
| ART-XV (Schema Evolution) | ✅ PASS | Migration 008 governed Alembic migration; additive only |
| ART-XVI (Docs as Code) | ✅ SHOULD | This plan + solution-architecture.md update satisfy the SHOULD |

**ART-IX deviation is pre-justified** in `research.md` Decision 3. No MUST violations.

## Project Structure

### Documentation (this feature)

```text
specs/034-business-arch-traceability/
├── plan.md              # This file
├── research.md          # Phase 0 — 8 decisions resolved
├── data-model.md        # Phase 1 — tables, models, TypeScript interfaces
├── contracts/
│   └── api-business-traceability.md  # 7 new endpoints
├── quickstart.md        # 8 integration scenarios
└── tasks.md             # Phase 2 output (from /speckit-tasks 034)
```

### Source Code Changes

```text
src/adp/
├── business/
│   ├── models.py       # ADD: DesignLinkCreate, DesignRef, CapabilityRef,
│   │                   #      ValueStreamRef, LinkedDesignsResponse,
│   │                   #      BusinessContextResponse
│   ├── store.py        # ADD: DuplicateLinkError, LinkNotFoundError,
│   │                   #      list_capability_designs, link_design_to_capability,
│   │                   #      unlink_design_from_capability,
│   │                   #      list_value_stream_designs, link_design_to_value_stream,
│   │                   #      unlink_design_from_value_stream,
│   │                   #      get_design_business_context
│   └── router.py       # ADD: 7 new endpoints (3 cap-design, 3 vs-design, 1 context)
└── store/
    └── migrations/
        └── versions/
            └── 008_business_traceability.py  # NEW: 2 join tables + indexes

web/src/
├── api/
│   └── business.ts     # ADD: DesignRef, CapabilityRef, ValueStreamRef,
│                       #      LinkedDesignsResponse, BusinessContextResponse,
│                       #      useLinkedCapabilityDesigns, useLinkDesignToCapability,
│                       #      useUnlinkDesignFromCapability,
│                       #      useLinkedValueStreamDesigns, useLinkDesignToValueStream,
│                       #      useUnlinkDesignFromValueStream, useDesignBusinessContext
├── business/
│   ├── DesignLinkEditor.tsx  # NEW: reusable add/remove design links component
│   ├── BusinessContextPanel.tsx  # NEW: design's capabilities + value streams panel
│   ├── CapabilityNode.tsx    # MODIFY: add expandable "Linked Designs" section
│   └── ValueStreamDetail.tsx # MODIFY: add "Supporting Designs" section
└── intake/
    └── IntakePage.tsx   # MODIFY: add <BusinessContextPanel> section

tests/
├── unit/
│   └── business/
│       └── test_models.py    # ADD: DesignLinkCreate, DesignRef validation tests
└── integration/
    └── test_business_api.py  # ADD: all 7 link endpoint scenarios
```

## Complexity Tracking

No constitution MUST violations. No complexity justification required.

---

## Phase 0 Research Summary

8 decisions recorded in `research.md`. All NEEDS CLARIFICATION resolved:

| Decision | Resolution |
|----------|------------|
| Module placement | Extend `adp.business` (not new module) |
| CASCADE strategy | Both FK legs CASCADE on both join tables |
| ART-IX audit | Structured logging (SHOULD); design.audit_log approach creates spurious versions |
| Design list source | Existing `GET /api/v1/designs` endpoint |
| Capability link UI | Inline expanded section in `CapabilityNode` |
| Business Context placement | `IntakePage` sidebar/bottom section |
| Unique constraint | Composite PK on both join tables; 409 on conflict |
| New packages | Zero |

---

## Phase 1 Design Summary

### Data Model

Two new join tables (migration 008):
- `capability_design_links`: composite PK `(capability_id, design_id)`, both legs CASCADE
- `value_stream_design_links`: composite PK `(value_stream_id, design_id)`, both legs CASCADE
- B-tree index on `design_id` column in each table for efficient reverse lookup

### API Contracts

7 new endpoints under `/api/v1/business/`:
- 3 capability–design endpoints (GET list, POST link, DELETE unlink)
- 3 value-stream–design endpoints (GET list, POST link, DELETE unlink)
- 1 reverse-lookup endpoint (`GET /business/designs/{design_id}/context`)

Full contract documentation: `contracts/api-business-traceability.md`

### Quickstart Scenarios

8 scenarios (`quickstart.md`):
1. Link design to capability (201 + items list)
2. Duplicate link returns 409
3. Reverse lookup: design business context
4. Link design to value stream (context shows both)
5. Remove capability link (204 + empty context)
6. Cascade on capability delete (no orphan in context)
7. Browser: Business Context panel in IntakePage
8. Browser: Capability tree inline linked designs
