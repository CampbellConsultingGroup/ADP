"""Contract tests for the Business Capabilities portfolio-scope Agent Review
(ADP-SPEC-040) -- reviews the whole capability tree at once, distinct from
the per-capability endpoints covered in test_capability_agent_review_api.py.

Full-stack against the real business store on in-memory SQLite, with a
lightweight in-memory fake OperationStore (same approach as the
per-capability contract tests: pre-populate operation state to test
accept/reject, rather than the actual LLM-generation step, which is covered
by tests/unit/business/test_agent_review_portfolio.py instead). Auth is
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

from adp.business import router as brouter
from adp.business import store as bstore


class _FakeOperationStore:
    """In-memory OperationStore double -- see test_capability_agent_review_api.py
    for why this exists instead of the real Postgres-backed store."""

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

    biz_factory = async_sessionmaker(biz_engine, expire_on_commit=False)
    op_store = _FakeOperationStore()

    from adp.api.app import create_app

    app = create_app()

    async def _override_biz():
        async with biz_factory() as session:
            yield session

    async def _override_op_store():
        return op_store

    app.dependency_overrides[brouter._get_session] = _override_biz
    app.dependency_overrides[brouter._get_op_store] = _override_op_store
    # The background task uses this factory (not the request-scoped session
    # above, which closes before the background task runs).
    app.dependency_overrides[brouter._get_biz_session_factory] = lambda: biz_factory

    client = TestClient(app, raise_server_exceptions=False)
    yield client, biz_factory, op_store
    await biz_engine.dispose()


async def _mk_capability(
    biz_factory, cap_id: str, level: int = 1, name: str = "Cap", parent_id: str | None = None
) -> None:
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._capabilities.insert().values(
                id=cap_id, name=name, description=None, level=level, parent_id=parent_id,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def test_trigger_and_poll_completes_empty_when_no_llm_configured(app_and_stores):
    client, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")

    resp = client.post("/api/v1/business/capabilities/agent-review")
    assert resp.status_code == 202, resp.text
    operation_id = resp.json()["operation_id"]

    poll = client.get(f"/api/v1/business/capabilities/agent-review/{operation_id}")
    assert poll.status_code == 200, poll.text
    body = poll.json()
    assert body["status"] == "completed"
    assert body["suggestions"] == []
    assert body["capability_id"] is None


def test_poll_unknown_operation_returns_404(app_and_stores):
    client, _, _ = app_and_stores
    resp = client.get("/api/v1/business/capabilities/agent-review/nope")
    assert resp.status_code == 404


async def test_llm_call_failure_marks_operation_failed(app_and_stores):
    client, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")

    failing_client = AsyncMock()
    failing_client.chat = AsyncMock(side_effect=RuntimeError("LLM provider timed out"))

    with patch("adp.business.router._make_agent_review_llm_client", return_value=failing_client):
        resp = client.post("/api/v1/business/capabilities/agent-review")
        assert resp.status_code == 202
        operation_id = resp.json()["operation_id"]

    poll = client.get(f"/api/v1/business/capabilities/agent-review/{operation_id}")
    body = poll.json()
    assert body["status"] == "failed"
    assert "LLM provider timed out" in body["error_description"]


def _seed_propose_new_capability_suggestion(
    op_store: _FakeOperationStore, supporting_stage_id: str, proposed_parent_id: str | None = None
) -> tuple[str, str]:
    operation_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "suggestion_id": suggestion_id,
        "type": "propose_new_capability",
        "capability_id": None,
        "rationale": "Returns Processing stage has no capability coverage.",
        "citations": [{"entity_type": "value_stream_stage", "entity_id": supporting_stage_id}],
        "advisory": False,
        "status": "pending",
        "proposed_name": "Returns Management",
        "proposed_description": "Handles product returns.",
        "proposed_level": 1,
        "proposed_parent_id": proposed_parent_id,
    }
    op_store._rows[operation_id] = {
        "id": operation_id,
        "type": "agent_review",
        "design_id": "PORTFOLIO",
        "status": "completed",
        "actor": "architect",
        "error_description": None,
        "suggestions": {suggestion_id: suggestion},
    }
    return operation_id, suggestion_id


def _seed_flag_for_removal_suggestion(
    op_store: _FakeOperationStore, target_capability_id: str
) -> tuple[str, str]:
    operation_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "suggestion_id": suggestion_id,
        "type": "flag_capability_for_removal",
        "capability_id": target_capability_id,
        "rationale": "Placeholder name, no description.",
        "citations": [{"entity_type": "business_capability", "entity_id": target_capability_id}],
        "advisory": False,
        "status": "pending",
    }
    op_store._rows[operation_id] = {
        "id": operation_id,
        "type": "agent_review",
        "design_id": "PORTFOLIO",
        "status": "completed",
        "actor": "architect",
        "error_description": None,
        "suggestions": {suggestion_id: suggestion},
    }
    return operation_id, suggestion_id


async def test_accept_propose_new_capability_creates_capability(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._value_streams.insert().values(
                id="VS-1", name="VS", description=None, stakeholder=None,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.execute(
            bstore._stages.insert().values(
                id="STAGE-1", value_stream_id="VS-1", name="Returns Processing",
                description=None, position=0,
            )
        )
        await session.commit()
    operation_id, suggestion_id = _seed_propose_new_capability_suggestion(op_store, "STAGE-1")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text

    caps = client.get("/api/v1/business/capabilities").json()["items"]
    created = [c for c in caps if c["name"] == "Returns Management"]
    assert len(created) == 1


async def test_accept_propose_new_capability_blocked_when_stage_deleted(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    # Deliberately never create STAGE-1 -- simulates it having been deleted.
    operation_id, suggestion_id = _seed_propose_new_capability_suggestion(op_store, "STAGE-1")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 409, resp.text


async def test_accept_flag_capability_for_removal_deletes_capability(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_flag_for_removal_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text

    get_resp = client.get("/api/v1/business/capabilities/CAP-1")
    assert get_resp.status_code == 404


async def test_accept_flag_capability_for_removal_blocked_when_has_children(app_and_stores):
    """Reuses the existing delete_capability guard -- cannot remove a
    capability that still has children, exactly like the manual delete
    button."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-PARENT", level=1)
    await _mk_capability(biz_factory, "CAP-CHILD", level=2, parent_id="CAP-PARENT")
    operation_id, suggestion_id = _seed_flag_for_removal_suggestion(op_store, "CAP-PARENT")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 409, resp.text

    get_resp = client.get("/api/v1/business/capabilities/CAP-PARENT")
    assert get_resp.status_code == 200  # unchanged by the blocked accept


async def test_accept_flag_capability_for_removal_target_already_deleted(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    operation_id, suggestion_id = _seed_flag_for_removal_suggestion(op_store, "CAP-GONE")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 404, resp.text


async def test_reject_flag_capability_for_removal_writes_nothing(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_flag_for_removal_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/reject"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    get_resp = client.get("/api/v1/business/capabilities/CAP-1")
    assert get_resp.status_code == 200


async def test_accept_unknown_suggestion_returns_404(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    operation_id, _ = _seed_flag_for_removal_suggestion(op_store, "CAP-1")

    resp = client.post(
        f"/api/v1/business/capabilities/agent-review/{operation_id}"
        f"/suggestions/nope/accept",
        json={"confirmation_id": "CONFIRM-nope"},
    )
    assert resp.status_code == 404
