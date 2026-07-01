# Implementation Plan: Identity, Authorization & Audit Trail

**Branch**: `004-identity-authz` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-identity-authz/spec.md`

## Summary

Define the typed permission table, enforce role-based authorization, and provide the audit-record write helper that the rest of the ADP stack depends on. Implemented as two new Python sub-packages — `adp.authz` (role model + permission grants) and `adp.audit` (typed audit writer) — consumed by ADP-SPEC-003's API layer and any future ADP component that needs to enforce access control or record accountability.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: None new — uses `adp.models.AuditEntry` (ADP-SPEC-001) and `adp.store.DesignStore` (ADP-SPEC-002); no additional runtime packages  
**Storage**: Delegates audit writes to `adp.store.DesignStore` (ADP-SPEC-002); the permission table is an in-process Python constant (no database required)  
**Testing**: pytest ≥ 7, pytest-cov; all tests are pure Python — no database or network required  
**Target Platform**: Python library sub-packages within `src/adp/`; consumed by ADP-SPEC-003 and future ADP components  
**Project Type**: Python library (`adp.authz` and `adp.audit` sub-packages)  
**Performance Goals**: Permission lookups are in-memory dict operations — effectively zero latency; audit writes are synchronous with the mutation transaction (no performance target beyond the store's own guarantees)  
**Constraints**: Permission table MUST be the single source of truth; no permission checks scattered across callers; role MUST be sourced from validated identity token, never caller-supplied (ART-IX)  
**Scale/Scope**: Single-tenant v1; four personas; eight action categories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-004 |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ All logic is pure Python — fully unit-testable without infrastructure |
| QG-05 | ART-IV, ART-XIII | Contract tests pass | ✅ Permission table completeness verified by exhaustive contract test |
| QG-06 | ART-V | SAST clean; no secrets in source | ✅ No credentials in permission or audit modules |
| QG-08 | ART-V | Secret scan clean | ✅ FR-006 is the primary requirement; no secrets anywhere in this spec's code |
| QG-09 | ART-V, ART-VIII | No prohibited-action code paths; consequential actions gated by per-action confirmation | ✅ FR-004 enforces per-action confirmation; `require_action` raises on any unconfirmed consequential path |
| QG-13 | ART-VIII, ART-IX | Model mutations write append-only audit entries with origin and actor | ✅ `write_audit_record` in `adp.audit` is the single write path; all callers must use it |
| QG-14 | ART-VIII | Consequential actions require explicit, attributable human confirmation | ✅ FR-004 and `require_action` enforce this; the permission table includes a `requires_confirmation` flag per action |
| QG-18 | ART-XIV | Pinned deps; reproducible | ✅ No new runtime dependencies; existing pinned versions unchanged |

**Constitution Alignment**: ART-V is the primary article this spec implements. No violations. ART-VI (observability) and ART-VII (AI grounding) are not in scope — this spec produces no AI outputs and no HTTP-layer code paths (those belong to ADP-SPEC-003).

## Project Structure

### Documentation (this feature)

```text
specs/004-identity-authz/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — role, action, and permission entities
├── contracts/
│   └── authz-contract.md   # Phase 1 — Python interface contract
├── quickstart.md        # Phase 1 — checking permissions and writing audit records
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # ADP-SPEC-001 (unchanged)
    ├── models.py                 # ADP-SPEC-001 (unchanged)
    ├── generate.py               # ADP-SPEC-001 (unchanged)
    ├── validate.py               # ADP-SPEC-001 (unchanged)
    ├── store/                    # ADP-SPEC-002 (unchanged)
    ├── api/                      # ADP-SPEC-003 (unchanged; imports from adp.authz)
    ├── authz/
    │   ├── __init__.py           # Exports PersonaRole, ActionType, is_permitted, require_action
    │   ├── roles.py              # PersonaRole(StrEnum) and ActionType(StrEnum) definitions
    │   └── permissions.py        # PERMISSION_GRANTS: dict[PersonaRole, frozenset[ActionType]]
    │                             # + requires_confirmation: frozenset[ActionType]
    │                             # + is_permitted(role, action) -> bool
    │                             # + require_action(role, action) -> None [raises PermissionDeniedError]
    └── audit/
        ├── __init__.py           # Exports write_audit_record, AuditRecord
        └── writer.py             # AuditRecord dataclass + write_audit_record(record, store) -> str

tests/
├── unit/                         # ADP-SPEC-001 (unchanged)
├── contract/                     # ADP-SPEC-001 (unchanged)
├── integration/                  # ADP-SPEC-002 (unchanged)
├── api/                          # ADP-SPEC-003 (unchanged; updated to import from adp.authz)
└── authz/
    ├── __init__.py
    ├── test_permissions.py       # Exhaustive permission table tests (all role × action combinations)
    └── test_audit.py             # AuditRecord construction + write helper (mocked store)
```

**Structure Decision**: Two new sub-packages (`adp.authz`, `adp.audit`) within the existing `src/adp/` package. Keeping them separate from `adp.api` ensures the permission table can be imported by any future ADP component without depending on the HTTP layer. The `adp.authz` package has no runtime dependencies beyond the standard library.
