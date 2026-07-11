"""Pytest fixtures for integration tests using a real PostgreSQL container.

Requires Docker. Tests are skipped automatically when Docker is unavailable.
Transaction isolation: each test runs inside a BEGIN/ROLLBACK block so
committed rows from one test never leak into the next (ART-IV: deterministic).
"""

from __future__ import annotations

import os

import pytest


def _docker_available() -> bool:
    import shutil
    return shutil.which("docker") is not None


# Skip the entire integration module if Docker is unavailable.
if not _docker_available():
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the test session."""
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require Docker")

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg15") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_url(postgres_container) -> str:  # type: ignore[type-arg]
    """Return an asyncpg-compatible database URL."""
    raw = postgres_container.get_connection_url()
    # testcontainers returns psycopg2 URL; convert for asyncpg
    return raw.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session")
async def db_engine(db_url: str):  # type: ignore[type-arg]
    """Create engine and run migrations once per test session."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(db_url, echo=False)

    # Run Alembic migrations via the synchronous migration path
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "ADP_DATABASE_URL": db_url},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stderr}")

    yield engine
    await engine.dispose()


@pytest.fixture()
async def db_session(db_engine):  # type: ignore[type-arg]
    """Function-scoped session wrapped in a rolled-back transaction for test isolation."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(db_engine) as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture()
async def store(db_url: str):  # type: ignore[type-arg]
    """Function-scoped DesignStore wired to the test database."""
    from adp.store import DesignStore

    s = DesignStore(db_url)
    yield s
    await s.dispose()
