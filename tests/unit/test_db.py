"""ADP-blp.14 / ADP-blp.15: one shared engine for every store, and one DesignStore."""

from __future__ import annotations

import asyncio
import importlib

import pytest

from adp import db

STORE_MODULES = [
    "adp.application.store",
    "adp.business.store",
    "adp.strategy.store",
    "adp.compliance.store",
    "adp.organization.store",
    "adp.agentic.store",
    "adp.patterns.store",
    "adp.chat.store",
    "adp.diagrams.store",
    "adp.admin.service",
    "adp.admin.rubric_service",
    "adp.admin.prompt_registry",
    "adp.admin.rubric_registry",
]


@pytest.fixture()
def sqlite_url(tmp_path, monkeypatch):
    url = f"sqlite+aiosqlite:///{tmp_path}/shared.db"
    monkeypatch.setenv("ADP_DATABASE_URL", url)
    return url


async def test_every_store_shares_one_factory(sqlite_url, monkeypatch):
    shared = db.get_session_factory()
    assert db.get_session_factory() is shared
    for name in STORE_MODULES:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "_session_factory", None)
        assert module._get_session_factory() is shared, name

    from adp.api import deps

    monkeypatch.setattr(deps, "_kb_session_factory", None)
    assert deps._get_kb_session_factory() is shared
    await db.dispose()


async def test_module_override_still_wins(sqlite_url, monkeypatch):
    """Tests point one store at their own database by setting its _session_factory."""
    import adp.business.store as bstore

    sentinel = object()
    monkeypatch.setattr(bstore, "_session_factory", sentinel)
    assert bstore._get_session_factory() is sentinel
    await db.dispose()


def _run_in_new_loop(coro):
    """Run on a private loop. asyncio.run() would also clear the thread's current event loop,
    which older tests in this suite still fetch with asyncio.get_event_loop()."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_engine_is_per_loop_and_per_url(tmp_path, monkeypatch):
    async def factory():
        return db.get_session_factory()

    monkeypatch.setenv("ADP_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/a.db")
    first = _run_in_new_loop(factory())
    assert _run_in_new_loop(factory()) is not first  # a new loop gets its own engine

    async def two_urls():
        one = db.get_session_factory()
        monkeypatch.setenv("ADP_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/b.db")
        two = db.get_session_factory()
        await db.dispose()
        return one, two

    one, two = _run_in_new_loop(two_urls())
    assert one is not two


def test_postgres_pool_is_sized_explicitly(monkeypatch):
    monkeypatch.setenv("ADP_DB_POOL_SIZE", "7")
    monkeypatch.setenv("ADP_DB_MAX_OVERFLOW", "nonsense")
    kwargs = db._engine_kwargs("postgresql+asyncpg://u:p@h/d")
    assert kwargs["pool_size"] == 7
    assert kwargs["max_overflow"] == 10  # bad value falls back to the default
    assert kwargs["pool_pre_ping"] is True
    assert "pool_size" not in db._engine_kwargs("sqlite+aiosqlite:///x.db")


async def test_design_store_is_reused_across_requests(sqlite_url, monkeypatch):
    from adp.api import deps

    monkeypatch.setattr(deps, "_design_store", None)
    first = await deps.get_design_store()
    assert await deps.get_design_store() is first
    assert first.session_factory is db.get_session_factory()
    await first.dispose()  # must not close the shared engine
    async with db.get_session_factory()() as session:
        assert session is not None
    await db.dispose()


def test_is_unique_violation_recognises_each_driver():
    """ADP-blp.27: one check for what used to be seventeen copies of a text test."""

    class _PgError(Exception):
        sqlstate = "23505"

    class _Wrapped(Exception):
        def __init__(self, orig):
            super().__init__("(wrapped) something went wrong")
            self.orig = orig

    assert db.is_unique_violation(_Wrapped(_PgError("duplicate key")))
    assert db.is_unique_violation(_PgError("x"))
    assert db.is_unique_violation(Exception("UNIQUE constraint failed: themes.name"))
    assert db.is_unique_violation(Exception("duplicate key value violates unique constraint"))
    assert not db.is_unique_violation(Exception("FOREIGN KEY constraint failed"))

    class _FkError(Exception):
        sqlstate = "23503"

    assert not db.is_unique_violation(_Wrapped(_FkError("fk")))
