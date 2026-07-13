# Research: Identity, Authorization & Audit Trail

**Branch**: `004-identity-authz` | **Date**: 2026-06-29  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: Permission Table as In-Memory Python Constant

**Decision**: The permission table is a `dict[PersonaRole, frozenset[ActionType]]` constant defined in `permissions.py`. It is not stored in a database and does not require a migration.

**Rationale**: The permission table changes rarely and only through a governed spec amendment process (ART-XV). At v1 scale (four roles, eight actions) it is trivially small. An in-memory constant is instantaneous to look up, has no infrastructure dependencies, and is version-controlled alongside the code that enforces it. The cost of changing it (a spec amendment + code review) is an intentional governance friction, not a bug.

**Alternatives considered**:
- Database-backed permission table — rejected: overkill for four roles; adds infrastructure dependency; permission changes require runtime migration, not just code review; risk of drift between code expectations and DB state
- OIDC-side authorization (fine-grained scopes) — rejected: pushes business logic into the identity provider; makes ADP's permission model opaque and hard to test in isolation

---

## Decision 2: `requires_confirmation` as a Frozenset

**Decision**: A separate `requires_confirmation: frozenset[ActionType]` constant marks which action types require per-action confirmation (ART-VIII / QG-14). The `require_action()` function checks both the role permission AND whether the action requires confirmation (returning a different error code if confirmation is absent).

**Rationale**: Separating "is this role allowed to do X" from "does X require confirmation" keeps the two concerns independently testable and allows the confirmation requirement to be tightened or loosened without touching the role table. The v1 `requires_confirmation` set is: `{confirm_recommendation, override_verdict, amend_standard, manage_roles}`.

---

## Decision 3: `PermissionDeniedError` as a Typed Exception

**Decision**: `require_action()` raises a typed `PermissionDeniedError(role, action, message)` exception. ADP-SPEC-003's API layer catches this and converts it to a 403 `ApiError` response.

**Rationale**: Typed exceptions make authorization failures visible to callers without coupling the permission module to the HTTP layer. ADP-SPEC-003 installs an exception handler that catches `PermissionDeniedError` alongside `HTTPException(403)`. Future non-HTTP consumers (e.g., a CLI) can handle the same exception without modification.

**Alternatives considered**:
- Return `bool` from `require_action` — rejected: callers must explicitly check the return value, which is easy to forget; exception forces handling
- Raise `HTTPException(403)` directly — rejected: couples `adp.authz` to `fastapi`, violating the library/HTTP separation

---

## Decision 4: `AuditRecord` as a Dataclass Distinct from `AuditEntry`

**Decision**: Define `AuditRecord` as a plain Python dataclass in `adp.audit.writer`. The `write_audit_record()` function converts it to an `AuditEntry` (ADP-SPEC-001 model) and calls `DesignStore.save()` with the entry appended to the design's `audit_log`.

**Rationale**: `AuditRecord` is the write-side contract — what callers provide when recording a consequential action. `AuditEntry` is the canonical stored form (ADP-SPEC-001). Keeping them distinct allows the audit writer to validate that all required fields are present before passing to the store, and allows `AuditRecord` to carry audit-layer-specific fields (e.g., `confirmation_id`) that are not in the canonical model.

**Alternatives considered**:
- Callers construct `AuditEntry` directly — rejected: forces all callers to know the ADP-SPEC-001 model structure; no central validation of required fields
- Separate audit microservice — rejected: massively over-engineered for v1; atomic audit write with the mutation is simpler and safer

---

## Decision 5: Authentication Validation Lives in ADP-SPEC-003, Not Here

**Decision**: `adp.authz` does NOT validate JWT tokens. JWT/OIDC validation remains in `adp.api.auth.jwt` (ADP-SPEC-003). `adp.authz` receives an already-validated `PersonaRole` and decides what that role may do.

**Rationale**: Separating authentication (did this token come from the right IdP?) from authorization (what may this role do?) is a standard security pattern. `adp.authz` has no knowledge of tokens, HTTP, or OIDC — it only knows about roles and actions. This makes `adp.authz` independently testable with no mock HTTP context.

---

## Decision 6: Versioning the Permission Matrix

**Decision**: The permission matrix is versioned via a `PERMISSIONS_VERSION = "1.0.0"` constant in `permissions.py`. Any change to the matrix must bump this version, reference the ADP-SPEC-004 amendment, and be reviewed as a spec change (not just a code change).

**Rationale**: The permission matrix is a governance artifact, not just implementation detail. Version-tracking makes permission changes auditable via git history and ensures they go through the same amendment process as any other spec change (ART-XV by analogy).

---

## Decision 7: Action Type Enumeration (v1 Baseline)

**Decision**: Eight action types for v1, mapping directly to the permission matrix in the spec:

| Action Type | Description |
|---|---|
| `read_design` | View any design or design version |
| `write_design` | Create or modify a design |
| `submit_ai_operation` | Submit a recommendation/validation/intake request |
| `confirm_recommendation` | Accept a completed AI recommendation |
| `override_verdict` | Override a validation verdict |
| `add_finding` | Add an audit finding to a design |
| `amend_standard` | Create or modify a platform-level architecture standard |
| `manage_roles` | Assign or revoke persona roles |

**Rationale**: Maps 1:1 to the permission matrix rows in the spec, making tests directly comparable to the spec's permission table. New action types are added via spec amendment and a `PERMISSIONS_VERSION` bump.
