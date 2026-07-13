"""Shared FastAPI dependency functions for database access.

All routers that need a DesignStore or a KB session import from here so the
database URL resolution and engine lifecycle happen in one place.
The URL is read from ADP_DATABASE_URL; if absent a clear 503 is returned.
"""

from __future__ import annotations

import os
from typing import Any, AsyncGenerator

from fastapi import HTTPException, status


def _get_database_url() -> str:
    url = os.environ.get("ADP_DATABASE_URL", "")
    if not url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ADP_DATABASE_URL is not configured. "
                "Set this environment variable to the PostgreSQL connection string."
            ),
        )
    return url


async def get_design_store():  # type: ignore[return]
    """FastAPI dependency: returns a configured DesignStore.

    Raises 503 if ADP_DATABASE_URL is not set.
    Override in tests via app.dependency_overrides.
    """
    from adp.store.store import DesignStore  # type: ignore[attr-defined]

    return DesignStore(_get_database_url())


# ── Shared knowledge-base session factory ─────────────────────────────────────
# Single engine + session factory for all knowledge-base access from within
# the FastAPI application context (ADP-SPEC-023 Move A).

_kb_engine: Any = None
_kb_session_factory: Any = None


def _get_kb_session_factory() -> Any:
    global _kb_engine, _kb_session_factory
    if _kb_session_factory is None:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        db_url = os.environ.get(
            "ADP_DATABASE_URL",
            "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp",
        )
        _kb_engine = create_async_engine(db_url, echo=False)
        _kb_session_factory = async_sessionmaker(_kb_engine, expire_on_commit=False)
    return _kb_session_factory


_op_store_singleton: Any = None


async def get_operation_store() -> Any:
    """FastAPI dependency: returns the singleton OperationStore.

    Uses the shared KB session factory (ADP-SPEC-023 single pool).
    Override in tests via app.dependency_overrides.
    """
    global _op_store_singleton
    if _op_store_singleton is None:
        from adp.store.operations import OperationStore
        _op_store_singleton = OperationStore(_get_kb_session_factory())
    return _op_store_singleton


_reasoning_store_singleton: Any = None


async def get_reasoning_store() -> Any:
    """FastAPI dependency: returns the singleton ReasoningStore (ADP-SPEC-027).

    Uses the shared KB session factory so no additional DB connections are created.
    Override in tests via app.dependency_overrides.
    """
    global _reasoning_store_singleton
    if _reasoning_store_singleton is None:
        from adp.store.reasoning import ReasoningStore
        _reasoning_store_singleton = ReasoningStore(_get_kb_session_factory())
    return _reasoning_store_singleton


async def get_kb_session() -> AsyncGenerator[Any, None]:
    """FastAPI dependency: yields a SQLAlchemy AsyncSession for knowledge-base access.

    Uses the shared engine created once per process (ADP-SPEC-023).
    Override in tests via app.dependency_overrides.
    """
    factory = _get_kb_session_factory()
    async with factory() as session:
        yield session
