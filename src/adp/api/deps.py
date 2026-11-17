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


_design_store: Any = None


async def get_design_store():  # type: ignore[return]
    """FastAPI dependency: returns a configured DesignStore.

    Raises 503 if ADP_DATABASE_URL is not set.
    Override in tests via app.dependency_overrides.
    """
    from adp.db import get_session_factory
    from adp.store.store import DesignStore  # type: ignore[attr-defined]

    _get_database_url()  # 503 when ADP_DATABASE_URL is unset
    # ADP-blp.14: this used to build a DesignStore -- and with it a whole new connection pool
    # that was never closed -- on every request. One store is now kept per shared session
    # factory (adp.db keeps one factory per event loop and database URL).
    global _design_store
    factory = get_session_factory()
    if _design_store is None or _design_store.session_factory is not factory:
        _design_store = DesignStore.from_session_factory(factory)
    return _design_store


# ── Shared knowledge-base session factory ─────────────────────────────────────
# Single engine + session factory for all knowledge-base access from within
# the FastAPI application context (ADP-SPEC-023 Move A).

_kb_engine: Any = None
_kb_session_factory: Any = None


def _get_kb_session_factory() -> Any:
    """adp.db's shared session factory (ADP-blp.15); a test may set _kb_session_factory."""
    if _kb_session_factory is not None:
        return _kb_session_factory
    from adp.db import get_session_factory

    return get_session_factory()


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


_intake_capture_singleton: Any = None
_recommendation_capture_singleton: Any = None
_validation_capture_singleton: Any = None


async def get_intake_capture_store() -> Any:
    """FastAPI dependency: returns the singleton IntakeCaptureStore.

    Uses the shared KB session factory so no additional DB connections are created.
    Override in tests via app.dependency_overrides.
    """
    global _intake_capture_singleton
    if _intake_capture_singleton is None:
        from adp.store.ai_capture import IntakeCaptureStore
        _intake_capture_singleton = IntakeCaptureStore(_get_kb_session_factory())
    return _intake_capture_singleton


async def get_recommendation_capture_store() -> Any:
    """FastAPI dependency: returns the singleton RecommendationCaptureStore."""
    global _recommendation_capture_singleton
    if _recommendation_capture_singleton is None:
        from adp.store.ai_capture import RecommendationCaptureStore
        _recommendation_capture_singleton = RecommendationCaptureStore(_get_kb_session_factory())
    return _recommendation_capture_singleton


async def get_validation_capture_store() -> Any:
    """FastAPI dependency: returns the singleton ValidationCaptureStore."""
    global _validation_capture_singleton
    if _validation_capture_singleton is None:
        from adp.store.ai_capture import ValidationCaptureStore
        _validation_capture_singleton = ValidationCaptureStore(_get_kb_session_factory())
    return _validation_capture_singleton


async def get_kb_session() -> AsyncGenerator[Any, None]:
    """FastAPI dependency: yields a SQLAlchemy AsyncSession for knowledge-base access.

    Uses the shared engine created once per process (ADP-SPEC-023).
    Override in tests via app.dependency_overrides.
    """
    factory = _get_kb_session_factory()
    async with factory() as session:
        yield session
