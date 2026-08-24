"""Pytest fixtures for integration tests using a real PostgreSQL container.

Requires Docker. Tests are skipped automatically when Docker is unavailable.

Transaction isolation (ADP-isj): the db_session fixture wraps writes made
directly through it in a BEGIN/ROLLBACK block, but most integration tests
instead write through a DesignStore/business-store/FastAPI-app fixture that
opens its own real engine — those commits were never wrapped by anything,
so on a full-suite run they permanently pollute the single, session-scoped
container for the rest of the run, in file/test order (confirmed root
cause: every such fixture's own async_sessionmaker has no savepoint/rollback
wired at all). _clean_tables below truncates every table before each test
runs, independent of and in addition to db_session's own rollback, so no
individual fixture needs to get its own isolation right for the suite as a
whole to be order-independent.
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


@pytest.fixture(autouse=True)
async def _clean_tables(db_engine):  # type: ignore[type-arg]
    """Truncate every table before each test (ADP-isj).

    Depends on db_engine directly (not conditionally via
    request.getfixturevalue) for two reasons, both confirmed by direct
    experiment against this project's actual pytest-asyncio config
    (asyncio_mode=auto, session-scoped fixture/test loops): (1) resolving an
    async fixture's value via request.getfixturevalue() from inside another
    already-running async fixture raises "Runner.run() cannot be called from
    a running event loop"; (2) it guarantees db_engine's migrations have
    already run before this truncates, which isn't otherwise guaranteed for
    two function-scoped sibling fixtures with no dependency between them.

    Test files with no DB dependency at all, or that deliberately use their
    own dedicated non-shared container (test_migration_022/023.py), override
    this fixture locally with a no-op -- both to avoid forcing Docker/the
    shared container on tests that don't need it, and because an *async*
    autouse fixture applied file-wide would otherwise break any plain `def
    test_...` (sync) test in the same file (confirmed by direct experiment:
    pytest-asyncio raises PytestRemovedIn9Warning/error for a sync test
    depending on an async autouse fixture, regardless of what runs inside
    its body).

    Runs *before*, not after, so a test that crashes mid-body (skipping its
    own cleanup, if any) doesn't leave the next test polluted either — the
    tradeoff is that the *last* test's data lingers until the next session
    starts, which is a feature for post-failure debugging, not a bug.
    TRUNCATE bypasses row-level triggers (unlike DELETE), so this doesn't
    trip audit_entries' append-only guard (deny_audit_mutation(), migration
    001) even though that trigger blocks ordinary DELETE. Table names are
    discovered dynamically rather than hardcoded so a future migration
    adding a table doesn't silently reopen this bug for it.
    """
    from sqlalchemy import text

    async with db_engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
                )
            )
        ).scalars().all()
        if tables:
            names = ", ".join(f'"{t}"' for t in tables)
            await conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    yield


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
