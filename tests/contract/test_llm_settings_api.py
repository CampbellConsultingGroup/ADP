"""ADP-blp.13: model choices are stored in the database; the API key is deploy-time only."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.api.app import create_app
from adp.llm import settings as llm_settings


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/llm.db")
    async with engine.begin() as conn:
        await conn.run_sync(llm_settings._metadata.create_all)
    monkeypatch.setattr(llm_settings, "_session_factory", async_sessionmaker(engine))
    for name in ("ADP_LLM_MODEL", "ADP_LLM_RECOMMENDATION_MODEL", "ADP_LLM_VALIDATION_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("ADP_LLM_API_KEY", raising=False)
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c
    await engine.dispose()


async def test_defaults_come_from_the_environment(client, monkeypatch):
    monkeypatch.setenv("ADP_LLM_RECOMMENDATION_MODEL", "claude-opus-4-8")
    body = (await client.get("/api/v1/config/llm")).json()
    assert body["extraction_model"] == llm_settings.DEFAULT_MODEL
    assert body["recommendation_model"] == "claude-opus-4-8"
    assert body["api_key_configured"] is False
    assert body["provider"] == "not_configured"


async def test_a_change_is_stored_and_seen_by_a_worker_that_did_not_make_it(client):
    resp = await client.put("/api/v1/config/llm", json={"extraction_model": "claude-opus-4-8"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["extraction_model"] == "claude-opus-4-8"
    assert resp.json()["validation_model"] == llm_settings.DEFAULT_MODEL  # untouched

    # Another worker: it has read nothing yet, so it knows only the defaults...
    llm_settings.reset_for_tests()
    assert llm_settings.model_for("extraction_model") == llm_settings.DEFAULT_MODEL
    # ...until it refreshes, which it does before every request that calls a model.
    await llm_settings.refresh()
    assert llm_settings.model_for("extraction_model") == "claude-opus-4-8"


async def test_a_stored_choice_wins_over_the_environment(client, monkeypatch):
    await client.put("/api/v1/config/llm", json={"validation_model": "claude-fable-5"})
    monkeypatch.setenv("ADP_LLM_VALIDATION_MODEL", "claude-haiku-4-5-20251001")
    assert (await client.get("/api/v1/config/llm")).json()["validation_model"] == "claude-fable-5"


async def test_unknown_model_is_refused_and_nothing_is_stored(client):
    resp = await client.put(
        "/api/v1/config/llm",
        json={"extraction_model": "claude-opus-4-8", "recommendation_model": "not-a-model"},
    )
    assert resp.status_code == 422
    llm_settings.reset_for_tests()
    await llm_settings.refresh()
    assert llm_settings.model_for("extraction_model") == llm_settings.DEFAULT_MODEL


async def test_the_api_key_cannot_be_set_through_the_api(client, monkeypatch):
    resp = await client.put("/api/v1/config/llm", json={"api_key": "sk-secret"})
    assert resp.status_code == 422
    assert (await client.get("/api/v1/config/llm")).json()["api_key_configured"] is False

    # It comes from the environment, read when needed (so a rotated key needs no code change).
    monkeypatch.setenv("ADP_LLM_API_KEY", "sk-from-environment")
    body = (await client.get("/api/v1/config/llm")).json()
    assert body["api_key_configured"] is True
    assert body["provider"] == "anthropic"
    assert "sk-from-environment" not in str(body)


async def test_an_unreadable_database_keeps_the_last_known_values(monkeypatch):
    def broken():
        raise RuntimeError("no database")

    monkeypatch.setattr(llm_settings, "_get_session_factory", broken)
    monkeypatch.setenv("ADP_LLM_MODEL", "claude-opus-4-8")
    await llm_settings.refresh()  # must not raise
    assert llm_settings.model_for("extraction_model") == "claude-opus-4-8"
