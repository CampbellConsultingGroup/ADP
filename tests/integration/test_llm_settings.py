"""ADP-blp.13 on real PostgreSQL: migration 055's table stores the model choices."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from adp.llm import settings as llm_settings


@pytest.fixture()
def factory(db_engine, monkeypatch):
    made = async_sessionmaker(db_engine, expire_on_commit=False)
    monkeypatch.setattr(llm_settings, "_session_factory", made)
    llm_settings.reset_for_tests()
    return made


async def test_save_then_read_from_another_worker(factory, monkeypatch) -> None:
    monkeypatch.delenv("ADP_LLM_MODEL", raising=False)
    async with factory() as session:
        await llm_settings.save(session, {"extraction_model": "claude-opus-4-8"}, "tester")
        await session.commit()
    async with factory() as session:  # the same setting again updates the row in place
        await llm_settings.save(session, {"extraction_model": "claude-fable-5"}, "tester")
        await session.commit()

    llm_settings.reset_for_tests()  # a worker that has read nothing yet
    assert llm_settings.model_for("extraction_model") == llm_settings.DEFAULT_MODEL
    await llm_settings.refresh()
    assert llm_settings.model_for("extraction_model") == "claude-fable-5"
    assert llm_settings.model_for("validation_model") == llm_settings.DEFAULT_MODEL
