# Data Model: Identity, Authorization & Audit Trail

**Branch**: `004-identity-authz` | **Date**: 2026-06-29  
**Source**: `src/adp/authz/roles.py`, `src/adp/authz/permissions.py`, `src/adp/audit/writer.py`

---

## `PersonaRole` (StrEnum)

The four recognized organizational personas. Unrecognized role strings receive no permissions — the enum is closed.

| Value | Description |
|---|---|
| `enterprise_architect` | Platform owner; may amend standards and manage roles |
| `solution_architect` | Design author; may create designs and confirm AI recommendations |
| `technical_architect` | Component designer; may create detailed designs; cannot override verdicts or amend standards |
| `reviewer` | Governance participant; read-only on designs; may override verdicts and add findings |

---

## `ActionType` (StrEnum)

The eight protected action categories in v1. Every protected operation in the system maps to one of these values before the permission check runs.

| Value | Requires Confirmation | Description |
|---|---|---|
| `read_design` | No | View any design or design version |
| `write_design` | No | Create or modify a design (write mutations) |
| `submit_ai_operation` | No | Submit a recommendation, validation, intake, or view-generation request |
| `confirm_recommendation` | **Yes** | Accept a completed AI recommendation and commit its result |
| `override_verdict` | **Yes** | Override a validation verdict with a human justification |
| `add_finding` | No | Add a review finding to a design |
| `amend_standard` | **Yes** | Create or modify a platform-level architecture standard |
| `manage_roles` | **Yes** | Assign or revoke a persona role for a principal |

**`requires_confirmation`**: `{confirm_recommendation, override_verdict, amend_standard, manage_roles}`

---

## `PERMISSION_GRANTS` Table

The central, versioned permission table. Version: `1.0.0`.

| Action | enterprise_architect | solution_architect | technical_architect | reviewer |
|---|---|---|---|---|
| `read_design` | ✅ | ✅ | ✅ | ✅ |
| `write_design` | ✅ | ✅ | ✅ | ❌ |
| `submit_ai_operation` | ✅ | ✅ | ✅ | ❌ |
| `confirm_recommendation` | ✅ | ✅ | ✅ | ❌ |
| `override_verdict` | ✅ | ✅ | ❌ | ✅ |
| `add_finding` | ✅ | ✅ | ✅ | ✅ |
| `amend_standard` | ✅ | ❌ | ❌ | ❌ |
| `manage_roles` | ✅ | ❌ | ❌ | ❌ |

Implemented in code as `PERMISSION_GRANTS: dict[PersonaRole, frozenset[ActionType]]`.

---

## `PermissionDeniedError`

Raised by `require_action()` when an action is not permitted. Typed for catch-and-convert by API layers.

| Field | Type | Notes |
|---|---|---|
| `role` | `PersonaRole` | The role that was checked |
| `action` | `ActionType` | The action that was denied |
| `message` | `str` | Human-readable denial reason; safe to include in API error responses |

**Subclass hierarchy**: `PermissionDeniedError(Exception)` — no inheritance from `HTTPException`; decoupled from HTTP.

---

## `AuditRecord`

The write-side record provided by callers when recording a consequential action. Converted to `AuditEntry` (ADP-SPEC-001) by `write_audit_record()`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `actor` | `str` | Yes | Principal ID (`sub` claim) of the human who performed the action |
| `action` | `ActionType` | Yes | The typed action category (maps to `AuditEntry.action`) |
| `affected_entity` | `str` | Yes | Entity ID of the design or entity that was mutated |
| `summary` | `str` | Yes | Human-readable description of what changed (≤ 240 chars) |
| `origin` | `Literal["human", "ai"]` | Yes | Whether the action was human-initiated or AI-derived |
| `confirmation_id` | `str \| None` | No | Operation ID of the confirmation that authorized this action (when `action` requires confirmation) |

**Validation**: `write_audit_record()` raises `ValueError` if `action` is in `requires_confirmation` and `confirmation_id` is `None` — prevents unconfirmed consequential actions from writing audit entries.

---

## State: Permission Check Flow

```
caller provides: (role: PersonaRole, action: ActionType, confirmation_id?: str)
                    │
                    ▼
     is (role, action) in PERMISSION_GRANTS?
                    │
           No ──────┴──────  Yes
           │                  │
   raise PermissionDeniedError  action in requires_confirmation?
                              │
                     No ──────┴───── Yes
                     │               │
              proceed         confirmation_id present?
                                      │
                              No ─────┴───── Yes
                              │               │
                      raise confirmation     proceed
                      required error
```

---

## State: Audit Write Flow (async)

**Note**: `write_audit_record` is an `async` function — callers must `await` it. The async requirement is inherited from `DesignStore.save()` (ADP-SPEC-002).

```
caller provides AuditRecord
        │
        ▼
validate: if action requires_confirmation → confirmation_id must be set
        │
        ▼
convert AuditRecord → AuditEntry (adp.models.AuditEntry)
    id = generate AUD-NNN
    actor = record.actor
    action = record.action.value
    affected_entity = record.affected_entity
    summary = record.summary
    timestamp = utcnow()
    origin = record.origin
        │
        ▼
append AuditEntry to design.audit_log
        │
        ▼
call DesignStore.save(design, actor=record.actor)
        │
        ▼
return audit_entry_id
```
