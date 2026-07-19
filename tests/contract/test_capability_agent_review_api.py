"""Contract tests for the Business Capabilities Agent Review adapter (ADP-SPEC-039).

Full-stack against the real business/application stores on in-memory SQLite,
with a lightweight in-memory fake OperationStore (mirrors the recommend/intake
contract tests' approach of testing accept/reject against pre-populated
operation state rather than the actual LLM-generation step, which is covered
by tests/unit/business/test_agent_review_duplicates.py instead). Auth is
disabled in tests, so the caller is ENTERPRISE_ARCHITECT (all actions);
authz denial is covered in tests/authz/test_enforcement.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.application import store as astore
from adp.business import router as brouter
from adp.business import store as bstore


class _FakeOperationStore:
    """In-memory OperationStore double: same interface, no DB (JSONB isn't
    portable to SQLite, and the real store is exercised by
    tests/unit/test_operations_store.py already)."""

    def __init__(self) -> None:
        self._rows: dict[str, dict] = {}

    async def create(self, op_id, op_type, design_id, actor, initial_payload) -> None:
        self._rows[op_id] = {
            "id": op_id,
            "type": op_type,
            "design_id": design_id,
            "status": "pending",
            "actor": actor,
            "error_description": None,
            **initial_payload,
        }

    async def get(self, op_id: str) -> dict | None:
        row = self._rows.get(op_id)
        return dict(row) if row is not None else None

    async def update(self, op_id, *, status=None, payload_patch=None, error=None) -> None:
        row = self._rows.get(op_id)
        if row is None:
            return
        if status is not None:
            row["status"] = status
        if payload_patch:
            row.update(payload_patch)
        if error is not None:
            row["error_description"] = error


@pytest.fixture()
async def app_and_stores(tmp_path):
    biz_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/biz.db")
    async with biz_engine.begin() as conn:
        await conn.run_sync(bstore._metadata.create_all)
    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)

    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)
    op_store = _FakeOperationStore()

    from adp.api.app import create_app

    app = create_app()

    async def _override_biz():
        async with biz_factory() as session:
            yield session

    async def _override_app():
        async with app_factory() as session:
            yield session

    async def _override_op_store():
        return op_store

    app.dependency_overrides[brouter._get_session] = _override_biz
    app.dependency_overrides[brouter._get_application_session] = _override_app
    app.dependency_overrides[brouter._get_op_store] = _override_op_store
    # The background task uses these factories (not the request-scoped sessions
    # above, which close before the background task runs) -- must also point
    # at the test's SQLite engines, or it silently targets real Postgres.
    app.dependency_overrides[brouter._get_biz_session_factory] = lambda: biz_factory
    app.dependency_overrides[brouter._get_application_session_factory] = lambda: app_factory

    client = TestClient(app, raise_server_exceptions=False)
    yield client, biz_factory, op_store
    await biz_engine.dispose()
    await app_engine.dispose()


async def _mk_capability(biz_factory, cap_id: str, level: int = 1, name: str = "Cap") -> None:
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._capabilities.insert().values(
                id=cap_id, name=name, description=None, level=level, parent_id=None,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def test_trigger_and_poll_completes_empty_when_no_llm_configured(app_and_stores):
    """No API key configured in the test environment -> the shared stub client
    returns an empty result -> the operation COMPLETES with no suggestions
    (the legitimate no-LLM-configured case, distinct from a failure, FR-021)."""
    client, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")

    resp = client.post("/api/v1/business/capabilities/CAP-1/agent-review")
    assert resp.status_code == 202, resp.text
    operation_id = resp.json()["operation_id"]

    poll = client.get(f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}")
    assert poll.status_code == 200, poll.text
    body = poll.json()
    assert body["status"] == "completed"
    assert body["suggestions"] == []
    assert body["error_description"] is None


def test_trigger_unknown_capability_returns_404(app_and_stores):
    client, _, _ = app_and_stores
    resp = client.post("/api/v1/business/capabilities/NOPE/agent-review")
    assert resp.status_code == 404


def test_poll_unknown_operation_returns_404(app_and_stores):
    client, _, _ = app_and_stores
    resp = client.get("/api/v1/business/capabilities/CAP-1/agent-review/nope")
    assert resp.status_code == 404


async def test_llm_call_failure_marks_operation_failed(app_and_stores):
    """Distinct from the no-API-key case: a configured client whose chat() call
    raises transitions the operation to failed with error_description (FR-021),
    never a silent empty result."""
    client, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")

    failing_client = AsyncMock()
    failing_client.chat = AsyncMock(side_effect=RuntimeError("LLM provider timed out"))

    with patch("adp.business.router._make_agent_review_llm_client", return_value=failing_client):
        resp = client.post("/api/v1/business/capabilities/CAP-1/agent-review")
        assert resp.status_code == 202
        operation_id = resp.json()["operation_id"]

    poll = client.get(f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}")
    body = poll.json()
    assert body["status"] == "failed"
    assert "LLM provider timed out" in body["error_description"]


def _seed_flag_duplicate_suggestion(op_store: _FakeOperationStore, cap_id: str) -> tuple[str, str]:
    operation_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "suggestion_id": suggestion_id,
        "type": "flag_duplicate",
        "capability_id": cap_id,
        "rationale": "Near-identical name and description to CAP-2.",
        "citations": [{"entity_type": "business_capability", "entity_id": "CAP-2"}],
        "advisory": False,
        "status": "pending",
    }
    op_store._rows[operation_id] = {
        "id": operation_id,
        "type": "agent_review",
        "design_id": cap_id,
        "status": "completed",
        "actor": "architect",
        "error_description": None,
        "suggestions": {suggestion_id: suggestion},
    }
    return operation_id, suggestion_id


async def test_accept_flag_duplicate_is_a_no_op_acknowledgment(app_and_stores):
    """US1: flag_duplicate never writes to the database -- accepting it just
    marks it accepted."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_flag_duplicate_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"

    # cannot accept twice
    resp2 = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp2.status_code == 409


async def test_accept_requires_non_empty_confirmation_id(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_flag_duplicate_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": "  "},
    )
    assert resp.status_code == 422


async def test_reject_marks_rejected_and_writes_nothing(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_flag_duplicate_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/reject"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    resp2 = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/reject"
    )
    assert resp2.status_code == 409


async def test_accept_unknown_suggestion_returns_404(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, _ = _seed_flag_duplicate_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/nope/accept",
        json={"confirmation_id": "CONFIRM-nope"},
    )
    assert resp.status_code == 404
