"""Shared FastAPI dependency functions for database access.

All routers that need a DesignStore import from here so the database URL
resolution happens in one place. The URL is read from ADP_DATABASE_URL;
if absent, a clear 503 error is returned rather than a cryptic 500.
"""

from __future__ import annotations

import os

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
