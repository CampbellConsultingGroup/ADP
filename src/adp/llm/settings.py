"""Which model each AI step uses, stored where every worker can see it (ADP-blp.13).

The settings screen used to change a dict in the memory of whichever worker process handled the
save. The container runs more than one worker, so about half of later requests kept the old
model, and the choice was lost whenever the app restarted (it scales to zero when idle).

The three model choices now live in the ``llm_settings`` table. A worker reads them at the
start of every request that calls a model (:func:`refresh`, wired as an app-level dependency),
so a change applies everywhere at once and survives a restart. A setting with no row falls back
to its environment variable, then to the built-in default.

The API key is deliberately NOT here. It is a secret with one home: the ``ADP_LLM_API_KEY``
environment variable (Key Vault on Azure, ``.env`` locally). It can no longer be set through the
API, which kept an unrecorded copy in one worker's memory.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"

#: setting name -> the environment variable that supplies its deploy-time default.
MODEL_SETTINGS: dict[str, str] = {
    "extraction_model": "ADP_LLM_MODEL",
    "recommendation_model": "ADP_LLM_RECOMMENDATION_MODEL",
    "validation_model": "ADP_LLM_VALIDATION_MODEL",
}

_metadata = sa.MetaData()

_llm_settings = sa.Table(
    "llm_settings",
    _metadata,
    sa.Column("name", sa.Text(), primary_key=True),
    sa.Column("value", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", sa.Text(), nullable=False),
)

# ── Session factory ───────────────────────────────────────────────────────────

_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    """The shared engine (adp.db), or this module's own factory when a test set one."""
    if _session_factory is not None:
        return _session_factory
    from adp.db import get_session_factory

    return get_session_factory()


# ── Values ────────────────────────────────────────────────────────────────────


def defaults() -> dict[str, str]:
    """The deploy-time values: each setting's environment variable, else the built-in default."""
    return {name: os.environ.get(env) or DEFAULT_MODEL for name, env in MODEL_SETTINGS.items()}


def endpoint() -> str:
    return os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")


def api_key() -> str:
    """The provider key, from the environment only. NEVER log the return value."""
    return os.environ.get("ADP_LLM_API_KEY", "")


# What this worker last read from the table. Synchronous callers (the code that builds an LLM
# client) read this; refresh() keeps it current.
_stored: dict[str, str] = {}
_retry_after = 0.0
_FAILURE_PAUSE_SECONDS = 30.0


def current() -> dict[str, str]:
    return {**defaults(), **_stored}


def model_for(setting: str) -> str:
    return current()[setting]


async def load(session: AsyncSession) -> dict[str, str]:
    """The stored choices over the defaults, read from the database."""
    rows = (await session.execute(sa.select(_llm_settings.c.name, _llm_settings.c.value))).all()
    stored = {name: value for name, value in rows if name in MODEL_SETTINGS}
    _remember(stored)
    return {**defaults(), **stored}


def _remember(stored: dict[str, str]) -> None:
    _stored.clear()
    _stored.update(stored)


async def refresh() -> None:
    """Bring this worker's copy up to date. Never raises: a database that cannot be read (or has
    no such table yet) leaves the last known values in place, and is not asked again for a while."""
    global _retry_after
    if time.monotonic() < _retry_after:
        return
    try:
        async with _get_session_factory()() as session:
            await load(session)
    except Exception as exc:  # noqa: BLE001 - settings must never fail an AI request
        _retry_after = time.monotonic() + _FAILURE_PAUSE_SECONDS
        _logger.warning("llm settings could not be read (%s); using the last known values", exc)


async def save(session: AsyncSession, changes: dict[str, str], actor: str) -> dict[str, str]:
    """Store the given model choices. The caller commits."""
    now = datetime.now(timezone.utc)
    for name, value in changes.items():
        if name not in MODEL_SETTINGS:
            raise KeyError(name)
        # Select-then-branch: portable across PostgreSQL and the SQLite used in tests.
        found = await session.execute(
            sa.select(_llm_settings.c.name).where(_llm_settings.c.name == name)
        )
        exists = found.first()
        values = {"value": value, "updated_at": now, "updated_by": actor}
        if exists:
            await session.execute(
                sa.update(_llm_settings).where(_llm_settings.c.name == name).values(**values)
            )
        else:
            await session.execute(sa.insert(_llm_settings).values(name=name, **values))
    return await load(session)


def reset_for_tests() -> None:
    global _retry_after
    _stored.clear()
    _retry_after = 0.0
