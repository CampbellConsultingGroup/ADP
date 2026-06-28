# Contract: DesignStore Python Interface

**Module**: `adp.store`  
**Primary class**: `DesignStore`  
**Date**: 2026-06-27

This is an internal Python library interface — not a web API endpoint. All parameters and return types are typed Pydantic/dataclass models. No raw dicts or JSON strings cross the store boundary (ART-XIII).

---

## Constructor

```python
class DesignStore:
    def __init__(self, database_url: str) -> None:
        """
        Initialise the store with a PostgreSQL connection URL.
        URL is sourced from environment variable ADP_DATABASE_URL.
        Must NOT be logged or stored in artifacts.
        """
```

---

## `save(description, actor, expected_version?) → DesignRecord`

Persist a new version of an `ArchitectureDescription` with an atomic audit entry.

**Pre-conditions**:
- `description` must validate against the published schema (FR-006); raises `SchemaValidationError` if not
- `description` must pass referential integrity checks (inherited from ADP-SPEC-001 model validator)
- If `expected_version` is provided and does not match `designs.current_version`, raises `ConcurrencyConflictError`

**Post-conditions**:
- A new row is inserted into `design_versions`; `designs.current_version` is incremented atomically
- An `AuditEntry` from `description.audit_log` is written to `audit_entries` in the same transaction
- If any step fails, the entire transaction rolls back (FR-003)

**Raises**:
- `SchemaValidationError` — artifact did not validate against the published schema
- `ConcurrencyConflictError` — `expected_version` did not match the current version
- `StoreError` — unexpected persistence failure

---

## `get(design_id, version?) → ArchitectureDescription`

Retrieve a stored design. If `version` is omitted, returns the latest version.

**Pre-conditions**: `design_id` must exist in `designs`; raises `DesignNotFoundError` if not. If `version` is specified, it must exist in `design_versions`.

**Post-conditions**: The returned `ArchitectureDescription` is identical to what was saved; it validates against the schema version recorded at write time.

**Raises**:
- `DesignNotFoundError` — design ID or version does not exist
- `StoreError` — unexpected persistence failure

---

## `list_versions(design_id) → list[DesignVersion]`

Return metadata for all versions of a design, ordered by `version_num` ascending. Does not return content.

**Raises**: `DesignNotFoundError` if `design_id` does not exist.

---

## `query_satisfies(design_id, requirement_id) → list[Element]`

Return all elements in the latest version of `design_id` whose `satisfies` list contains `requirement_id`.

**Returns**: Empty list (not an error) if no elements satisfy the requirement.

**Raises**: `DesignNotFoundError` if `design_id` does not exist.

---

## `query_orphan_requirements(design_id) → list[Requirement]`

Return all requirements in the latest design version that appear in no element's and no option's `satisfies` list.

**Returns**: Empty list if all requirements are satisfied.

---

## `query_verdict_chain(design_id, option_id) → VerdictChain`

Return the full traceability chain for one `SolutionOption`: the option itself, the requirements it satisfies, the elements that also satisfy those requirements, and the verdict recorded against it (if any).

**Raises**: `DesignNotFoundError` if `design_id` does not exist; `EntityNotFoundError` if `option_id` does not appear in the latest version.

---

## Error Hierarchy

```python
class StoreError(Exception): ...
class DesignNotFoundError(StoreError): ...
class EntityNotFoundError(StoreError): ...
class SchemaValidationError(StoreError): ...
class ConcurrencyConflictError(StoreError): ...
```

All exceptions carry the relevant `design_id` and a human-readable message. Exception text is safe to log (no design content, no credentials).

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ADP_DATABASE_URL` | PostgreSQL connection URL (`postgresql+asyncpg://...`) | Yes |

The database URL MUST be externalized via environment variable and MUST NOT appear in source, fixtures, or generated files (ART-V / QG-08).

---

## Logging Contract (ART-VI / QG-10)

Each store method emits a structured log entry at INFO level on success and ERROR level on failure:

```json
{
  "operation": "save | get | list_versions | query_satisfies | ...",
  "design_id": "DESIGN-001",
  "version_num": 3,
  "actor": "jmuir",
  "duration_ms": 42,
  "error": null
}
```

Fields `content` and `database_url` are NEVER logged.
