"""The one database engine every store shares (ADP-blp.15).

Each store module used to call ``create_async_engine`` for itself: about 18 separate
connection pools against the same database, each with SQLAlchemy's default size (5 plus 10
overflow). Under load, with two workers, that allowed several hundred connections against a
Postgres default limit of 100, and a single request could hold connections from several pools.

Now every store's ``_get_session_factory()`` returns the factory from here unless a test has set
that module's own ``_session_factory``. The pool size is explicit and configurable:

    ADP_DB_POOL_SIZE      connections kept open per worker process (default 10)
    ADP_DB_MAX_OVERFLOW   extra connections allowed under load (default 10)
    ADP_DB_POOL_RECYCLE   seconds before a connection is replaced (default 1800)

The engine is kept per event loop and per database URL. asyncpg connections belong to the loop
that opened them, and tests run many loops and point ``ADP_DATABASE_URL`` at different
databases, so a single process-wide engine would hand one loop's connections to another.
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

_logger = logging.getLogger("adp.db")

DEFAULT_DATABASE_URL = "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"

_Entry = tuple[AsyncEngine, async_sessionmaker]

# loop -> {database url -> (engine, session factory)}
_by_loop: weakref.WeakKeyDictionary[Any, dict[str, _Entry]] = weakref.WeakKeyDictionary()
# Used only when there is no running loop (e.g. a factory fetched at import time).
_no_loop: dict[str, _Entry] = {}


def database_url() -> str:
    return os.environ.get("ADP_DATABASE_URL", DEFAULT_DATABASE_URL)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        _logger.warning("%s=%r is not a number; using %d", name, raw, default)
        return default


def _engine_kwargs(url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"echo": False}
    # Pool sizing only applies to a real server; SQLite (tests) uses its own pool classes.
    if url.startswith("postgresql"):
        kwargs.update(
            pool_size=_int_env("ADP_DB_POOL_SIZE", 10),
            max_overflow=_int_env("ADP_DB_MAX_OVERFLOW", 10),
            pool_recycle=_int_env("ADP_DB_POOL_RECYCLE", 1800),
            pool_pre_ping=True,
        )
    return kwargs


def _bucket() -> dict[str, _Entry]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return _no_loop
    return _by_loop.setdefault(loop, {})


def _entry() -> _Entry:
    url = database_url()
    bucket = _bucket()
    entry = bucket.get(url)
    if entry is None:
        engine = create_async_engine(url, **_engine_kwargs(url))
        entry = (engine, async_sessionmaker(engine, expire_on_commit=False))
        bucket[url] = entry
    return entry


def get_engine() -> AsyncEngine:
    return _entry()[0]


def get_session_factory() -> async_sessionmaker:
    """The shared session factory for the current event loop and ADP_DATABASE_URL."""
    return _entry()[1]


async def dispose() -> None:
    """Close the current loop's connections. Called once at application shutdown."""
    try:
        bucket = _by_loop.pop(asyncio.get_running_loop(), {})
    except RuntimeError:
        bucket = {}
    for engine, _factory in bucket.values():
        await engine.dispose()
