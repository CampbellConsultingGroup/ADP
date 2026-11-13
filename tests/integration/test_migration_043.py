"""Integration test: migration 043 (agent registry, ADP-hii / 933) applies and reverts cleanly, and
the database itself enforces what the store relies on -- the widened application_type CHECK, the
agents/solution_agents CHECKs, and ON DELETE CASCADE on both membership legs.

Uses its own dedicated container (same reasoning as test_migration_042.py: it downgrades below
head).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


def _docker_available() -> bool:
    import shutil

    return shutil.which("docker") is not None


if not _docker_available():
    collect_ignore_glob = ["test_migration_043.py"]


def _run_alembic(db_url: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        env={**os.environ, "ADP_DATABASE_URL": db_url},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed:\n{result.stderr}")


@pytest.fixture(autouse=True)
def _clean_tables():
    """Override conftest.py's autouse table truncation: this file uses its own container."""
    yield


@pytest.fixture()
def migration_db_url():
    if not _docker_available():
        pytest.skip("Docker not available — integration tests require Docker")
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("pgvector/pgvector:pg15") as pg:
        raw = pg.get_connection_url()
        yield raw.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )


_APP = (
    "INSERT INTO applications (id, name, application_type, lifecycle_status, created_at,"
    " updated_at) VALUES (:id, :name, :t, 'active', now(), now())"
)
_AGENT = (
    "INSERT INTO agents (id, name, autonomy_level, human_approval, created_at, updated_at)"
    " VALUES (:id, :name, :lvl, :ha, now(), now())"
)
_MEMBER = (
    "INSERT INTO solution_agents (solution_app_id, agent_id, role, position, created_at)"
    " VALUES (:app, :agent, :role, 0, now())"
)


async def _count(conn, table: str) -> int:
    return (await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


async def test_migration_043_upgrade_downgrade_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "042")
    _run_alembic(migration_db_url, "upgrade", "043")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert {"agents", "solution_agents"} <= tables
            await conn.execute(sa.text(_APP), {"id": "app-1", "name": "Claims", "t": "agentic"})
            await conn.execute(sa.text(_APP), {"id": "app-2", "name": "Fraud", "t": "agentic"})
            await conn.execute(
                sa.text(_AGENT), {"id": "ag-1", "name": "Triage", "lvl": 3, "ha": "none"}
            )
            await conn.execute(
                sa.text(_MEMBER), {"app": "app-1", "agent": "ag-1", "role": "worker"}
            )
            await conn.execute(
                sa.text(_MEMBER), {"app": "app-2", "agent": "ag-1", "role": "reviewer"}
            )

        # CHECK constraints reject out-of-set values.
        await _expect_integrity_error(engine, _APP, {"id": "x", "name": "x", "t": "robot"})
        await _expect_integrity_error(
            engine, _AGENT, {"id": "bad1", "name": "x", "lvl": 5, "ha": "none"}
        )
        await _expect_integrity_error(
            engine, _AGENT, {"id": "bad2", "name": "x", "lvl": 1, "ha": "sometimes"}
        )
        await _expect_integrity_error(
            engine, _MEMBER, {"app": "app-2", "agent": "ag-1", "role": "boss"}
        )

        # Deleting a solution removes its membership only; the shared agent survives.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM applications WHERE id = 'app-2'"))
            assert await _count(conn, "solution_agents") == 1
            assert await _count(conn, "agents") == 1

        # Deleting an agent removes all of its memberships.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM agents WHERE id = 'ag-1'"))
            assert await _count(conn, "solution_agents") == 0
            assert await _count(conn, "applications") == 1
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "downgrade", "042")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert not ({"agents", "solution_agents"} & tables)
            nulled = await conn.execute(
                sa.text("SELECT application_type FROM applications WHERE id = 'app-1'")
            )
            assert nulled.scalar_one() is None
    finally:
        await engine.dispose()
