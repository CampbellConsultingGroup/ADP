# Contract: Authorization and Audit Python Interface

**Modules**: `adp.authz`, `adp.audit`  
**Consumers**: `adp.api.auth.rbac` (ADP-SPEC-003), any future ADP component enforcing access control  
**Date**: 2026-06-29

These are internal Python library interfaces. No HTTP or database dependencies in `adp.authz`. `adp.audit` depends on `adp.store.DesignStore` (ADP-SPEC-002).

---

## `adp.authz` Public Interface

### `PERMISSIONS_VERSION: str`

The semantic version of the active permission table. Bump on every permission matrix change.

```python
PERMISSIONS_VERSION = "1.0.0"
```

### `PersonaRole(StrEnum)`

```python
class PersonaRole(StrEnum):
    ENTERPRISE_ARCHITECT = "enterprise_architect"
    SOLUTION_ARCHITECT = "solution_architect"
    TECHNICAL_ARCHITECT = "technical_architect"
    REVIEWER = "reviewer"
```

### `ActionType(StrEnum)`

```python
class ActionType(StrEnum):
    READ_DESIGN = "read_design"
    WRITE_DESIGN = "write_design"
    SUBMIT_AI_OPERATION = "submit_ai_operation"
    CONFIRM_RECOMMENDATION = "confirm_recommendation"
    OVERRIDE_VERDICT = "override_verdict"
    ADD_FINDING = "add_finding"
    AMEND_STANDARD = "amend_standard"
    MANAGE_ROLES = "manage_roles"
```

### `is_permitted(role: PersonaRole, action: ActionType) -> bool`

Returns `True` if `role` is in the permission table for `action`; `False` otherwise. Never raises.

```python
is_permitted(PersonaRole.REVIEWER, ActionType.WRITE_DESIGN)   # → False
is_permitted(PersonaRole.REVIEWER, ActionType.OVERRIDE_VERDICT)  # → True
```

### `requires_confirmation(action: ActionType) -> bool`

Returns `True` if `action` requires a per-action confirmation payload before proceeding.

```python
requires_confirmation(ActionType.READ_DESIGN)          # → False
requires_confirmation(ActionType.CONFIRM_RECOMMENDATION)  # → True
```

### `require_action(role: PersonaRole, action: ActionType) -> None`

Raises `PermissionDeniedError` if `role` is not permitted `action`. Does NOT check confirmation — confirmation is a separate concern handled by the caller or API layer.

**Raises**: `PermissionDeniedError(role, action, message)` if permission is denied.

### `PermissionDeniedError(Exception)`

```python
class PermissionDeniedError(Exception):
    role: PersonaRole
    action: ActionType
    message: str
```

---

## `adp.audit` Public Interface

### `AuditRecord` (dataclass)

```python
@dataclass
class AuditRecord:
    actor: str                    # principal_id from validated JWT
    action: ActionType            # typed action category
    affected_entity: str          # entity ID of the mutated object
    summary: str                  # ≤ 240 chars; human-readable description
    origin: Literal["human", "ai"]
    confirmation_id: str | None = None  # required when action requires confirmation
```

### `write_audit_record(record: AuditRecord, design: ArchitectureDescription, store: DesignStore) -> str`

Appends an `AuditEntry` derived from `record` to `design.audit_log` and calls `store.save()` atomically. Returns the generated `audit_entry_id`.

**Raises**:
- `ValueError` if `action` is in `requires_confirmation` and `confirmation_id` is `None`
- `ValueError` if `summary` exceeds 240 characters
- Propagates any `StoreError` from `DesignStore.save()`

**Guarantees**: The audit entry and the design mutation commit in the same transaction (inherited from ADP-SPEC-002's store). If the store write fails, neither the mutation nor the audit entry persists.

---

## Environment Variables

None. `adp.authz` has no runtime configuration. `adp.audit` inherits `ADP_DATABASE_URL` from `adp.store` — no new env vars introduced.

---

## Usage Pattern (for ADP-SPEC-003 integration)

```python
from adp.authz import ActionType, PersonaRole, require_action, requires_confirmation
from adp.audit import AuditRecord, write_audit_record

# 1. After validating the JWT and extracting the role:
role = PersonaRole(principal.role)  # raises ValueError on unrecognized role

# 2. Check permission (raises PermissionDeniedError → convert to 403 in API):
require_action(role, ActionType.WRITE_DESIGN)

# 3. If confirmation required, check it was provided:
if requires_confirmation(ActionType.CONFIRM_RECOMMENDATION):
    assert confirmation_id is not None, "Confirmation required"

# 4. Perform the mutation, then write audit entry:
record = AuditRecord(
    actor=principal.principal_id,
    action=ActionType.CONFIRM_RECOMMENDATION,
    affected_entity=design_id,
    summary=f"Accepted recommendation for {design_id}",
    origin="human",
    confirmation_id=confirmation_id,
)
audit_entry_id = await write_audit_record(record, design, store)
```
