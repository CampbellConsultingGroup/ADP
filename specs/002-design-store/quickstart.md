# Quickstart: Saving and Querying a Design

**Branch**: `002-design-store` | **Date**: 2026-06-27  
**Prerequisite**: `ADP_DATABASE_URL` environment variable set to a running PostgreSQL instance; `adp` package installed

This guide covers the primary flows (US1–US4) using the `DesignStore` interface.

---

## Initial Setup

```python
import os
from adp.store import DesignStore

store = DesignStore(database_url=os.environ["ADP_DATABASE_URL"])
```

Running migrations before first use:

```bash
ADP_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/adp alembic upgrade head
```

---

## Saving a Design (US1)

```python
from adp.models import ArchitectureDescription, Requirement, Element, ElementKind
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
design = ArchitectureDescription(
    schema_version="1.0.0",
    id="DESIGN-001",
    title="Order Processing System",
    requirements=[
        Requirement(id="REQ-001", title="Stateless handlers", description="...")
    ],
    elements=[
        Element(id="ELM-001", name="API Gateway", kind=ElementKind.CONTAINER,
                satisfies=["REQ-001"])
    ],
    created_at=now,
    updated_at=now,
)

# Save — creates version 1
record = await store.save(design, actor="jmuir")
print(record.current_version)  # 1
```

---

## Retrieving a Design (US1 — round-trip)

```python
# Retrieve latest version
retrieved = await store.get("DESIGN-001")
assert retrieved == design  # identical model

# Retrieve a specific version
v1 = await store.get("DESIGN-001", version=1)
```

---

## Saving a Second Version with Optimistic Concurrency (US3)

```python
# Modify the design
updated_design = design.model_copy(
    update={"title": "Order Processing System v2", "updated_at": datetime.now(timezone.utc)}
)

# Provide current version to prevent overwrites from concurrent actors
record_v2 = await store.save(updated_design, actor="jmuir", expected_version=1)
print(record_v2.current_version)  # 2

# Prior version still accessible
original = await store.get("DESIGN-001", version=1)
assert original.title == "Order Processing System"
```

---

## Handling Concurrent Conflict

```python
from adp.store import ConcurrencyConflictError

try:
    await store.save(stale_design, actor="colleague", expected_version=1)
    # Fails if current version is already 2
except ConcurrencyConflictError:
    # Re-read and retry
    current = await store.get("DESIGN-001")
    # ... apply changes and retry
```

---

## Traceability Queries (US4)

```python
# Which elements satisfy REQ-001?
elements = await store.query_satisfies("DESIGN-001", "REQ-001")
print([e.name for e in elements])  # ["API Gateway"]

# Which requirements have no satisfying element or option?
orphans = await store.query_orphan_requirements("DESIGN-001")
# Returns requirements with nothing in their satisfies chain

# Full verdict chain for an option
chain = await store.query_verdict_chain("DESIGN-001", "OPT-001")
print(chain.option.title)
print([r.id for r in chain.satisfies_requirements])
print(chain.verdict.status if chain.verdict else "no verdict yet")
```

---

## What Gets Rejected

| Attempt | Error |
|---|---|
| Save a design that fails schema validation | `SchemaValidationError` |
| Save with an `expected_version` that doesn't match | `ConcurrencyConflictError` |
| Retrieve a non-existent `design_id` | `DesignNotFoundError` |
| Direct SQL DELETE on `audit_entries` | PostgreSQL trigger exception |
| Retrieve a `version` that does not exist | `DesignNotFoundError` |

---

## Audit Trail (US2)

The audit trail is populated automatically from `description.audit_log` during `save()`. Each `AuditEntry` in the log is written atomically with the new design version:

```python
from adp.models import AuditEntry

design_with_audit = design.model_copy(update={
    "audit_log": [
        AuditEntry(
            id="AUD-001",
            actor="jmuir",
            action="add-element",
            affected_entity="ELM-001",
            summary="Added API Gateway element.",
            timestamp=now,
            origin="human",
        )
    ]
})

await store.save(design_with_audit, actor="jmuir")
# AUD-001 is now in audit_entries, atomically committed with version 1
```
