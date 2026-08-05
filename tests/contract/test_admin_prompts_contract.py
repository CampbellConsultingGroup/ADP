"""Contract tests for the Admin Agent Prompt Management API (ADP-SPEC-042).

Full-stack against the real service on in-memory SQLite. Role is controlled
via a get_current_user dependency override (mirrors tests/authz/test_enforcement.py),
since ADP_AUTH_ENABLED=false's default caller is ENTERPRISE_ARCHITECT, which
this feature deliberately does NOT grant MANAGE_AGENT_PROMPTS to.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.admin import prompt_registry
from adp.admin import service as admin_service
from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.roles import PersonaRole


def _user(role: PersonaRole) -> AuthenticatedUser:
    return AuthenticatedUser(sub="t", username="t", email="t@localhost", role=role, groups=[])


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    # admin/service.py's own tables (overrides + history, full write-path columns)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/admin.db")
    async with engine.begin() as conn:
        await conn.run_sync(admin_service._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # prompt_registry's own read-path factory (used directly by list_agents(),
    # not via a router-level override) -- point it at the SAME SQLite DB and
    # pin the loop, mirroring tests/unit/admin/test_prompt_registry.py.
    monkeypatch.setattr(prompt_registry, "_session_factory", factory)
    monkeypatch.setattr(prompt_registry, "_engine_loop", asyncio.get_running_loop())

    from adp.api.app import create_app
    from adp.api.routers import admin_prompts_router as admin_router

    app = create_app()

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[admin_router._get_session] = _override
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.PLATFORM_ADMIN)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, app
    await engine.dispose()


async def test_list_returns_all_six_agents_with_defaults(client) -> None:
    c, _app = client
    resp = await c.get("/api/v1/admin/agent-prompts")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"]
    assert len(items) == 6
    ids = {i["agent_id"] for i in items}
    assert ids == {
        "chat_assistant",
        "recommendation_generation",
        "recommendation_generation_no_kb",
        "recommendation_tradeoff",
        "intake_extraction",
        "agent_review_business_capability",
    }
    for item in items:
        assert item["is_override"] is False
        assert item["version"] == 0
        assert item["active_text"].strip() != ""


async def test_list_denied_without_manage_agent_prompts(client) -> None:
    """A caller without MANAGE_AGENT_PROMPTS (e.g. a plain Enterprise Architect,
    per Clarification Session 2026-07-24 Q1) gets 403 with no prompt CONTENT
    in the body -- the 403 detail naming the required action is fine, that's
    not the same as leaking the six agents' actual prompt text (User Story 1
    Scenario 3)."""
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.get("/api/v1/admin/agent-prompts")
    assert resp.status_code == 403
    assert "items" not in resp.json()
    assert "active_text" not in resp.text


# ── User Story 2: edit, confirm, take effect ─────────────────────────────────

async def test_confirm_rejects_empty_text(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "   ", "expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 422


async def test_confirm_rejects_missing_confirmation_id(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "Hello.", "expected_version": 0, "confirmation_id": ""},
    )
    assert resp.status_code == 422


async def test_confirm_success_persists_and_attributes(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        headers={"X-Actor": "alice"},
        json={
            "new_text": "You are a custom chat assistant.",
            "expected_version": 0,
            "confirmation_id": "CONFIRM-chat_assistant-1",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["agent_id"] == "chat_assistant"
    assert body["active_text"] == "You are a custom chat assistant."
    assert body["version"] == 1

    listing = (await c.get("/api/v1/admin/agent-prompts")).json()
    item = next(i for i in listing["items"] if i["agent_id"] == "chat_assistant")
    assert item["is_override"] is True
    assert item["version"] == 1
    assert item["active_text"] == "You are a custom chat assistant."

    history = (await c.get("/api/v1/admin/agent-prompts/chat_assistant/history")).json()
    assert len(history["items"]) == 1
    entry = history["items"][0]
    assert entry["change_type"] == "edit"
    assert entry["new_text"] == "You are a custom chat assistant."
    assert entry["actor"] == "alice"  # from the X-Actor header (auth-disabled convention)


async def test_confirm_version_conflict_returns_current_state(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={
            "new_text": "First edit.", "expected_version": 0,
            "confirmation_id": "CONFIRM-A",
        },
    )
    # Stale expected_version=0 (the agent is now at version=1).
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={
            "new_text": "Second, conflicting edit.", "expected_version": 0,
            "confirmation_id": "CONFIRM-B",
        },
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["current_active_text"] == "First edit."
    assert detail["current_version"] == 1


async def test_confirm_denied_without_manage_agent_prompts(client) -> None:
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "Hi.", "expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 403


# ── User Story 3: history + restore ──────────────────────────────────────────

async def test_history_ordered_newest_first(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "Edit 1.", "expected_version": 0, "confirmation_id": "C-1"},
    )
    await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "Edit 2.", "expected_version": 1, "confirmation_id": "C-2"},
    )
    resp = await c.get("/api/v1/admin/agent-prompts/chat_assistant/history")
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["new_text"] == "Edit 2."
    assert items[1]["new_text"] == "Edit 1."


async def test_restore_requires_confirmation_id(client) -> None:
    """Restore is NOT a lower-friction path than edit (Clarification Session
    2026-07-24) -- missing confirmation_id is rejected the same way."""
    c, _app = client
    confirm = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={"new_text": "Edit 1.", "expected_version": 0, "confirmation_id": "C-1"},
    )
    history_id = (await c.get(
        "/api/v1/admin/agent-prompts/chat_assistant/history"
    )).json()["items"][0]["id"]

    resp = await c.post(
        f"/api/v1/admin/agent-prompts/chat_assistant/restore/{history_id}",
        json={"expected_version": confirm.json()["version"], "confirmation_id": ""},
    )
    assert resp.status_code == 422


async def test_restore_creates_new_history_entry_not_a_rewrite(client) -> None:
    c, _app = client
    await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={
            "new_text": "Original override.", "expected_version": 0,
            "confirmation_id": "C-1",
        },
    )
    await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/confirm",
        json={
            "new_text": "Second, bad edit.", "expected_version": 1,
            "confirmation_id": "C-2",
        },
    )
    history_items = (await c.get(
        "/api/v1/admin/agent-prompts/chat_assistant/history"
    )).json()["items"]
    original_entry_id = next(
        i["id"] for i in history_items if i["new_text"] == "Original override."
    )

    resp = await c.post(
        f"/api/v1/admin/agent-prompts/chat_assistant/restore/{original_entry_id}",
        json={"expected_version": 2, "confirmation_id": "CONFIRM-restore"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active_text"] == "Original override."
    assert body["version"] == 3

    updated_history = (await c.get(
        "/api/v1/admin/agent-prompts/chat_assistant/history"
    )).json()["items"]
    assert len(updated_history) == 3  # two edits + one restore, none rewritten
    assert updated_history[0]["change_type"] == "restore"
    assert updated_history[0]["new_text"] == "Original override."
    # The original two edit entries are untouched.
    assert {i["change_type"] for i in updated_history[1:]} == {"edit"}


async def test_restore_404_for_unknown_history_id(client) -> None:
    c, _app = client
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/restore/999999",
        json={"expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 404


async def test_restore_denied_without_manage_agent_prompts(client) -> None:
    c, app = client
    app.dependency_overrides[get_current_user] = lambda: _user(PersonaRole.ENTERPRISE_ARCHITECT)
    resp = await c.post(
        "/api/v1/admin/agent-prompts/chat_assistant/restore/1",
        json={"expected_version": 0, "confirmation_id": "CONFIRM-1"},
    )
    assert resp.status_code == 403
