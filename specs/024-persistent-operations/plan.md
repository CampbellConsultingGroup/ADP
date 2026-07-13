# Implementation Plan: Persistent Operation Store (ADP-SPEC-024)

## Tech Stack
- **New**: `src/adp/store/operations.py` — `OperationStore` class, async SQLAlchemy 2
- **Migration**: New Alembic migration adding `operations` table with JSONB payload + indexes
- **No new packages**: uses existing `asyncpg`, `sqlalchemy[asyncio]`, `pydantic`
- **Depends on**: ADP-SPEC-023 (single DB pool in `adp.api.deps`)

## Architecture

### `operations` Table Schema

```sql
CREATE TABLE operations (
    id          TEXT        PRIMARY KEY,
    type        TEXT        NOT NULL,         -- 'intake' | 'recommend'
    design_id   TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'pending',
    payload     JSONB       NOT NULL DEFAULT '{}',
    actor       TEXT        NOT NULL DEFAULT 'architect',
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL           -- created_at + INTERVAL '24 hours'
);
CREATE INDEX ix_ops_design_type_status ON operations (design_id, type, status);
CREATE INDEX ix_ops_expires_at ON operations (expires_at);
```

### `OperationStore` Interface (`src/adp/store/operations.py`)

```python
class OperationStore:
    async def create(op_id, type, design_id, actor, initial_payload) -> None
    async def get(op_id) -> dict | None
    async def update(op_id, status=None, payload_patch=None, error=None) -> None
    async def update_option_status(op_id, option_id, new_status, requires_pending=True) -> bool
        # Returns False if option was not pending (for 409 handling)
    async def delete_expired() -> int
    async def mark_stale_running_as_failed(message: str) -> int
```

### Payload Shape per Type

**intake payload**:
```json
{
  "requirement_ids": [],
  "proposals": {"PROP-001": {...}},
  "result_summary": null,
  "error_description": null,
  "correlation_id": "..."
}
```

**recommend payload**:
```json
{
  "requirement_ids": ["REQ-001"],
  "options": {"uuid": {...}},
  "result_summary": null,
  "error_description": null,
  "correlation_id": "..."
}
```

### Key Behaviour Changes

- `_intake_store.get(op_id)` → `await op_store.get(op_id)` (async)
- `_intake_store[op_id] = {...}` → `await op_store.create(op_id, "intake", ...)` (async)
- Option accept/reject: `_recommend_store[op_id]["options"][opt_id]["status"] = "accepted"` →
  `await op_store.update_option_status(op_id, opt_id, "accepted")` with optimistic concurrency

### Startup Hook

On FastAPI `lifespan` startup:
1. Call `op_store.mark_stale_running_as_failed("server restarted during processing")`
2. Schedule repeating 10-min cleanup: `op_store.delete_expired()`

## File Changes

| File | Action |
|------|--------|
| `alembic/versions/XXXX_add_operations_table.py` | CREATE — migration |
| `src/adp/store/operations.py` | CREATE — OperationStore class |
| `src/adp/store/__init__.py` | EDIT — export OperationStore |
| `src/adp/api/deps.py` | EDIT — add `get_operation_store()` dependency |
| `src/adp/api/app.py` | EDIT — add lifespan context manager for startup/cleanup |
| `src/adp/api/routers/intake.py` | EDIT — replace `_intake_store` dict with `OperationStore` |
| `src/adp/api/routers/recommend.py` | EDIT — replace `_recommend_store` dict with `OperationStore` |
| `src/adp/intake/orchestrator.py` | EDIT — accept `OperationStore` instead of dict |
| `src/adp/recommendation/orchestrator.py` | EDIT — accept `OperationStore` instead of dict |
| `tests/contract/test_intake_api.py` | EDIT — mock OperationStore instead of dict |
| `tests/contract/test_recommend_api.py` | EDIT — mock OperationStore instead of dict |
| `tests/unit/test_operations_store.py` | CREATE — unit tests for OperationStore |

## Orchestrator Compatibility

Both orchestrators currently accept a `dict` as `operation_store`. After this spec they accept `OperationStore`. To avoid breaking the orchestrator unit tests (which pass plain dicts), introduce a `DictOperationStore(dict)` shim in tests only — not in production code.
