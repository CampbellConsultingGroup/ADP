# Quickstart: Checking Permissions and Writing Audit Records

**Branch**: `004-identity-authz` | **Date**: 2026-06-29  
**Prerequisite**: `adp` package installed; no database or network required for permission checks

This guide covers the primary flows (US1–US4) using the `adp.authz` and `adp.audit` interfaces.

---

## US2: Checking Persona Permissions

```python
from adp.authz import ActionType, PersonaRole, is_permitted, require_action, PermissionDeniedError

# Check without raising
is_permitted(PersonaRole.REVIEWER, ActionType.WRITE_DESIGN)     # → False
is_permitted(PersonaRole.REVIEWER, ActionType.OVERRIDE_VERDICT) # → True
is_permitted(PersonaRole.TECHNICAL_ARCHITECT, ActionType.AMEND_STANDARD)  # → False
is_permitted(PersonaRole.ENTERPRISE_ARCHITECT, ActionType.AMEND_STANDARD) # → True

# Enforce permission (raises on denial)
try:
    require_action(PersonaRole.REVIEWER, ActionType.WRITE_DESIGN)
except PermissionDeniedError as e:
    print(f"Denied: {e.role} cannot {e.action}")
    # → "Denied: reviewer cannot write_design"
```

---

## US2: Rejecting Unrecognized Roles

```python
try:
    role = PersonaRole("super_admin")  # Not a recognized persona
except ValueError:
    # Unrecognized roles get no permissions — fail closed
    pass
```

---

## US3: Checking Whether Confirmation Is Required

```python
from adp.authz import ActionType, requires_confirmation

requires_confirmation(ActionType.READ_DESIGN)          # → False
requires_confirmation(ActionType.CONFIRM_RECOMMENDATION)  # → True
requires_confirmation(ActionType.OVERRIDE_VERDICT)     # → True
requires_confirmation(ActionType.WRITE_DESIGN)         # → False
```

---

## US4: Writing an Audit Record After a Consequential Action

```python
from adp.audit import AuditRecord, write_audit_record
from adp.authz import ActionType

# After a successful design mutation:
record = AuditRecord(
    actor="sub:architect-123",          # principal_id from validated JWT
    action=ActionType.WRITE_DESIGN,
    affected_entity="DESIGN-001",
    summary="Added API Gateway element to Order Processing System.",
    origin="human",
    confirmation_id=None,               # write_design does not require confirmation
)
audit_entry_id = await write_audit_record(record, design, store)
print(audit_entry_id)  # → "AUD-001"
```

---

## US4: Writing an Audit Record for a Confirmed Action

```python
# After a confirmed recommendation acceptance:
record = AuditRecord(
    actor="sub:architect-123",
    action=ActionType.CONFIRM_RECOMMENDATION,
    affected_entity="OPT-001",
    summary="Accepted JWT auth recommendation for Order Service gateway.",
    origin="human",
    confirmation_id="op-uuid-here",     # required — action is in requires_confirmation
)
audit_entry_id = await write_audit_record(record, design, store)
```

---

## What Gets Rejected

| Attempt | Result |
|---|---|
| Reviewer calls `require_action(role, write_design)` | `PermissionDeniedError` |
| Unrecognized role string passed to `PersonaRole(...)` | `ValueError` |
| `write_audit_record` with `confirm_recommendation` but no `confirmation_id` | `ValueError` |
| `write_audit_record` with `summary` > 240 chars | `ValueError` |
| Any attempt to delete or update a committed audit entry | PostgreSQL trigger exception (ADP-SPEC-002) |

---

## Full Permission Table Reference

| Action | enterprise | solution | technical | reviewer |
|---|---|---|---|---|
| `read_design` | ✅ | ✅ | ✅ | ✅ |
| `write_design` | ✅ | ✅ | ✅ | ❌ |
| `submit_ai_operation` | ✅ | ✅ | ✅ | ❌ |
| `confirm_recommendation` | ✅ | ✅ | ✅ | ❌ |
| `override_verdict` | ✅ | ✅ | ❌ | ✅ |
| `add_finding` | ✅ | ✅ | ✅ | ✅ |
| `amend_standard` | ✅ | ❌ | ❌ | ❌ |
| `manage_roles` | ✅ | ❌ | ❌ | ❌ |

Permission table version: `1.0.0` — bump `PERMISSIONS_VERSION` on any change.
