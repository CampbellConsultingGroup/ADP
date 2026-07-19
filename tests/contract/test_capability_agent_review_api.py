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


def _seed_maturity_suggestion(
    op_store: _FakeOperationStore, cap_id: str, previous_maturity_level: int
) -> tuple[str, str]:
    operation_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "suggestion_id": suggestion_id,
        "type": "set_maturity_level",
        "capability_id": cap_id,
        "rationale": "Documented and standardized org-wide.",
        "citations": [],
        "advisory": False,
        "status": "pending",
        "maturity_level": 3,
        "previous_maturity_level": previous_maturity_level,
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


async def test_accept_set_maturity_level_writes_field_and_snapshot_matches(app_and_stores):
    """US2 happy path: the field snapshotted at generation time still matches
    the current value -> the write proceeds."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    client.put("/api/v1/business/capabilities/CAP-1", json={"maturity_level": 2})
    operation_id, suggestion_id = _seed_maturity_suggestion(
        op_store, "CAP-1", previous_maturity_level=2
    )

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "accepted"

    cap = client.get("/api/v1/business/capabilities/CAP-1")
    assert cap.json()["maturity_level"] == 3


async def test_accept_blocked_when_same_field_changed_since_generation(app_and_stores):
    """FR-015: the SAME field the suggestion targets was edited manually after
    the suggestion was generated -> 409, no write."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    operation_id, suggestion_id = _seed_maturity_suggestion(
        op_store, "CAP-1", previous_maturity_level=2
    )

    # Manually edit maturity_level after the suggestion was generated.
    update_resp = client.put(
        "/api/v1/business/capabilities/CAP-1", json={"maturity_level": 4}
    )
    assert update_resp.status_code == 200, update_resp.text

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 409, resp.text

    cap = client.get("/api/v1/business/capabilities/CAP-1")
    assert cap.json()["maturity_level"] == 4  # unchanged by the blocked accept


async def test_accept_allowed_when_unrelated_field_changed_since_generation(app_and_stores):
    """FR-015: the stale check is field-scoped -- a change to a DIFFERENT field
    (name) since generation does not block accepting a maturity_level
    suggestion."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1")
    client.put("/api/v1/business/capabilities/CAP-1", json={"maturity_level": 2})
    operation_id, suggestion_id = _seed_maturity_suggestion(
        op_store, "CAP-1", previous_maturity_level=2
    )

    update_resp = client.put(
        "/api/v1/business/capabilities/CAP-1", json={"name": "Renamed Capability"}
    )
    assert update_resp.status_code == 200, update_resp.text

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text

    cap = client.get("/api/v1/business/capabilities/CAP-1")
    assert cap.json()["maturity_level"] == 3
    assert cap.json()["name"] == "Renamed Capability"


# ── US3: assign_domain ────────────────────────────────────────────────────────

def _seed_assign_domain_suggestion(
    op_store: _FakeOperationStore, cap_id: str, domain_id: str
) -> tuple[str, str]:
    operation_id = str(uuid.uuid4())
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "suggestion_id": suggestion_id,
        "type": "assign_domain",
        "capability_id": cap_id,
        "rationale": "Scope statement matches this capability's function.",
        "citations": [{"entity_type": "business_domain", "entity_id": domain_id}],
        "advisory": False,
        "status": "pending",
        "domain_id": domain_id,
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


async def _mk_domain(biz_factory, domain_id: str, name: str = "Retail Ops") -> None:
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._domains.insert().values(
                id=domain_id, name=name, scope_statement="Retail operations.",
                classification="strategic", org_unit=None, risk_flags=[],
                created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def _mk_value_stream(biz_factory, vs_id: str, name: str = "Order to Cash") -> None:
    now = datetime.now(timezone.utc)
    async with biz_factory() as session:
        await session.execute(
            bstore._value_streams.insert().values(
                id=vs_id, name=name, description=None, stakeholder=None,
                position=0, created_at=now, updated_at=now,
            )
        )
        await session.commit()


async def _mk_stage(biz_factory, stage_id: str, vs_id: str, name: str = "Stage") -> None:
    async with biz_factory() as session:
        await session.execute(
            bstore._stages.insert().values(
                id=stage_id, value_stream_id=vs_id, name=name, description=None, position=0,
            )
        )
        await session.commit()


async def _link_stage_to_capability(biz_factory, stage_id: str, cap_id: str) -> None:
    async with biz_factory() as session:
        await session.execute(
            bstore._stage_caps.insert().values(stage_id=stage_id, capability_id=cap_id)
        )
        await session.commit()


def _seed_propose_new_capability_suggestion(
    op_store: _FakeOperationStore, cap_id: str, supporting_stage_id: str
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
        "proposed_level": 2,
        "proposed_parent_id": cap_id,
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


async def test_assemble_context_finds_uncovered_sibling_stage(app_and_stores, tmp_path):
    """The supporting-context signal for propose_new_capability (US4): a stage
    in the same value stream as one of the reviewed capability's own stages,
    with zero capability coverage."""
    from adp.business.agent_review import assemble_context

    _, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=2)
    await _mk_value_stream(biz_factory, "VS-1")
    await _mk_stage(biz_factory, "STAGE-COVERED", "VS-1", name="Order Entry")
    await _mk_stage(biz_factory, "STAGE-UNCOVERED", "VS-1", name="Returns Processing")
    await _link_stage_to_capability(biz_factory, "STAGE-COVERED", "CAP-1")

    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app3.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async with biz_factory() as biz_session, app_factory() as app_session:
        context = await assemble_context("CAP-1", biz_session, app_session)
    await app_engine.dispose()

    assert [s.stage_id for s in context.uncovered_stages] == ["STAGE-UNCOVERED"]


async def test_accept_propose_new_capability_creates_capability(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=1)
    await _mk_value_stream(biz_factory, "VS-1")
    await _mk_stage(biz_factory, "STAGE-1", "VS-1")
    operation_id, suggestion_id = _seed_propose_new_capability_suggestion(
        op_store, "CAP-1", "STAGE-1"
    )

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text

    caps = client.get("/api/v1/business/capabilities").json()["items"]
    created = [c for c in caps if c["name"] == "Returns Management"]
    assert len(created) == 1
    assert created[0]["level"] == 2


async def test_accept_propose_new_capability_blocked_when_stage_deleted_since_generation(
    app_and_stores,
):
    """FR-015: the supporting citation (the stage) no longer exists at accept
    time -> 409, no capability created."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=1)
    # Deliberately never create STAGE-1 -- simulates it having been deleted.
    operation_id, suggestion_id = _seed_propose_new_capability_suggestion(
        op_store, "CAP-1", "STAGE-1"
    )

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 409, resp.text

    caps = client.get("/api/v1/business/capabilities").json()["items"]
    assert [c for c in caps if c["name"] == "Returns Management"] == []


async def test_accept_advisory_propose_new_capability_requires_acknowledgment(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=1)
    operation_id, suggestion_id = _seed_propose_new_capability_suggestion(
        op_store, "CAP-1", "STAGE-NEVER-EXISTED"
    )
    op_store._rows[operation_id]["suggestions"][suggestion_id]["advisory"] = True

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 422, resp.text

    resp2 = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}", "advisory_acknowledged": True},
    )
    # STAGE-NEVER-EXISTED still doesn't exist -> FR-015 re-verification 409s
    # even after the advisory override, proving the two checks are independent.
    assert resp2.status_code == 409, resp2.text


async def test_assemble_context_offers_domains_only_for_unassigned_l1(app_and_stores, tmp_path):
    """assemble_context's assignable_domains gating (FR-012), exercised against
    a real DB rather than a constructed CapabilityContext -- covers the new
    list_domains_full store function actually being wired up correctly."""
    from adp.business.agent_review import assemble_context

    _, biz_factory, _ = app_and_stores
    await _mk_capability(biz_factory, "CAP-L1-UNASSIGNED", level=1)
    await _mk_capability(biz_factory, "CAP-L1-ASSIGNED", level=1)
    await _mk_capability(biz_factory, "CAP-L2", level=2)
    await _mk_domain(biz_factory, "DOM-1")

    async with biz_factory() as session:
        await session.execute(
            bstore._capabilities.update()
            .where(bstore._capabilities.c.id == "CAP-L1-ASSIGNED")
            .values(domain_id="DOM-1")
        )
        await session.commit()

    app_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/app2.db")
    async with app_engine.begin() as conn:
        await conn.run_sync(astore._metadata.create_all)
    app_factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async with biz_factory() as biz_session, app_factory() as app_session:
        unassigned_ctx = await assemble_context("CAP-L1-UNASSIGNED", biz_session, app_session)
        assigned_ctx = await assemble_context("CAP-L1-ASSIGNED", biz_session, app_session)
        l2_ctx = await assemble_context("CAP-L2", biz_session, app_session)

    await app_engine.dispose()

    assert [d.id for d in unassigned_ctx.assignable_domains] == ["DOM-1"]
    assert assigned_ctx.assignable_domains == []
    assert l2_ctx.assignable_domains == []


async def test_accept_assign_domain_writes_domain_id(app_and_stores):
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=1)
    await _mk_domain(biz_factory, "DOM-1")
    operation_id, suggestion_id = _seed_assign_domain_suggestion(op_store, "CAP-1", "DOM-1")

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 200, resp.text

    cap = client.get("/api/v1/business/capabilities/CAP-1")
    assert cap.json()["domain_id"] == "DOM-1"


async def test_accept_assign_domain_blocked_when_already_assigned_since_generation(app_and_stores):
    """FR-015's degenerate case (research D8): no previous_* snapshot field --
    the check is simply 'is domain_id still NULL'. Someone else assigned a
    domain between generation and accept -> 409, no overwrite."""
    client, biz_factory, op_store = app_and_stores
    await _mk_capability(biz_factory, "CAP-1", level=1)
    await _mk_domain(biz_factory, "DOM-1")
    await _mk_domain(biz_factory, "DOM-OTHER", name="Other Domain")
    operation_id, suggestion_id = _seed_assign_domain_suggestion(op_store, "CAP-1", "DOM-1")

    # Someone else assigns a (different) domain first.
    assign_resp = client.patch(
        "/api/v1/business/capabilities/CAP-1/domain", json={"domain_id": "DOM-OTHER"}
    )
    assert assign_resp.status_code == 200, assign_resp.text

    resp = client.post(
        f"/api/v1/business/capabilities/CAP-1/agent-review/{operation_id}"
        f"/suggestions/{suggestion_id}/accept",
        json={"confirmation_id": f"CONFIRM-{suggestion_id}"},
    )
    assert resp.status_code == 409, resp.text

    cap = client.get("/api/v1/business/capabilities/CAP-1")
    assert cap.json()["domain_id"] == "DOM-OTHER"  # unchanged by the blocked accept
