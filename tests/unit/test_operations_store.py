"""Unit tests for OperationStore (ADP-SPEC-024 T001-T005).

Uses in-memory SQLite via aiosqlite — no PostgreSQL required.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.store.operations import OperationStore


@pytest.fixture()
def store() -> OperationStore:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create the operations table compatible with SQLite
    async def _setup():
        async with engine.begin() as conn:
            await conn.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    design_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    payload TEXT NOT NULL DEFAULT '{}',
                    actor TEXT NOT NULL DEFAULT 'architect',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
            """))

    asyncio.get_event_loop().run_until_complete(_setup())
    return OperationStore(factory)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── T001 ──────────────────────────────────────────────────────────────────────

def test_create_and_get_returns_operation(store):
    run(store.create("OP-001", "intake", "DSN-001", "actor", {"correlation_id": "C-1"}))
    op = run(store.get("OP-001"))
    assert op is not None
    assert op["id"] == "OP-001"
    assert op["type"] == "intake"
    assert op["design_id"] == "DSN-001"
    assert op["status"] == "pending"
    assert op["actor"] == "actor"
    assert op.get("correlation_id") == "C-1"


# ── T002 ──────────────────────────────────────────────────────────────────────

def test_update_changes_status_and_payload(store):
    run(store.create("OP-002", "recommend", "DSN-002", "actor", {}))
    run(store.update("OP-002", status="completed", payload_patch={"result_summary": "done"}))
    op = run(store.get("OP-002"))
    assert op["status"] == "completed"
    assert op.get("result_summary") == "done"


# ── T003 ──────────────────────────────────────────────────────────────────────

def test_get_nonexistent_returns_none(store):
    result = run(store.get("MISSING-OP"))
    assert result is None


# ── T004 ──────────────────────────────────────────────────────────────────────

def test_delete_expired_removes_old_rows(store):
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=25)

    # Create two operations — one expired, one not
    run(store.create("OP-EXPIRED", "intake", "D-001", "actor", {}))
    run(store.create("OP-ACTIVE", "intake", "D-001", "actor", {}))

    # Manually set expires_at for the expired one
    async def _force_expiry():
        async with store._session_factory() as session:
            await session.execute(sa.text(
                "UPDATE operations SET expires_at = :ts WHERE id = 'OP-EXPIRED'"
            ), {"ts": past.isoformat()})
            await session.commit()

    run(_force_expiry())

    deleted = run(store.delete_expired())
    assert deleted >= 1

    assert run(store.get("OP-EXPIRED")) is None
    assert run(store.get("OP-ACTIVE")) is not None


# ── T005 ──────────────────────────────────────────────────────────────────────

def test_mark_stale_running_as_failed(store):
    run(store.create("OP-RUN", "recommend", "D-001", "actor", {}))
    run(store.update("OP-RUN", status="running"))

    count = run(store.mark_stale_running_as_failed("server restarted"))
    assert count >= 1

    op = run(store.get("OP-RUN"))
    assert op["status"] == "failed"
    assert op["error_description"] == "server restarted"


# ── Additional: update_option_status ─────────────────────────────────────────

def test_update_option_status_returns_true_for_pending(store):
    run(store.create("OP-OPT", "recommend", "D-001", "actor", {
        "options": {"OPT-1": {"status": "pending", "title": "Option 1"}}
    }))
    result = run(store.update_option_status("OP-OPT", "OPT-1", "accepted"))
    assert result is True
    op = run(store.get("OP-OPT"))
    assert op["options"]["OPT-1"]["status"] == "accepted"


def test_update_option_status_returns_false_for_non_pending(store):
    run(store.create("OP-OPT2", "recommend", "D-001", "actor", {
        "options": {"OPT-1": {"status": "accepted", "title": "Option 1"}}
    }))
    result = run(store.update_option_status("OP-OPT2", "OPT-1", "rejected"))
    assert result is False
    # Status unchanged
    op = run(store.get("OP-OPT2"))
    assert op["options"]["OPT-1"]["status"] == "accepted"
