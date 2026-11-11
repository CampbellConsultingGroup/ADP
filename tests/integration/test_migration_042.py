"""Integration test: migration 042 (value chains, ADP-nag) applies and reverts cleanly, and the
database itself enforces what the store relies on -- the category CHECK constraint and the
ON DELETE CASCADE on both legs (chain -> activities -> capability links, and a deleted business
capability dropping its activity links).

Uses its own dedicated container rather than the shared session-scoped `db_engine` fixture, since
this test deliberately downgrades below head (same reasoning as test_migration_023.py).
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
    collect_ignore_glob = ["test_migration_042.py"]


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


_TABLES = {"value_chains", "value_chain_activities", "value_chain_activity_capabilities"}


async def _seed(conn) -> None:
    await conn.execute(sa.text(
        "INSERT INTO business_capabilities (id, name, level, position, created_at, updated_at)"
        " VALUES ('cap-1', 'Inventory Management', 1, 0, now(), now())"
    ))
    await conn.execute(sa.text(
        "INSERT INTO value_chains (id, name, created_at, updated_at)"
        " VALUES ('vc-1', 'Retail', now(), now())"
    ))
    await conn.execute(sa.text(
        "INSERT INTO value_chain_activities (id, value_chain_id, name, category, position)"
        " VALUES ('act-1', 'vc-1', 'Operations', 'primary', 0)"
    ))
    await conn.execute(sa.text(
        "INSERT INTO value_chain_activity_capabilities (activity_id, capability_id)"
        " VALUES ('act-1', 'cap-1')"
    ))


async def _count(conn, table: str) -> int:
    return (await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608


async def test_migration_042_upgrade_downgrade_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "041")
    _run_alembic(migration_db_url, "upgrade", "042")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert _TABLES <= tables
            margin = await conn.execute(sa.text(
                "SELECT column_default FROM information_schema.columns"
                " WHERE table_name = 'value_chains' AND column_name = 'margin_label'"
            ))
            assert "Margin" in margin.scalar_one()

        # The category CHECK constraint rejects anything but primary/support.
        async with engine.begin() as conn:
            await _seed(conn)
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(sa.text(
                    "INSERT INTO value_chain_activities (id, value_chain_id, name, category)"
                    " VALUES ('bad', 'vc-1', 'x', 'core')"
                ))

        # A deleted capability drops its activity links but not the activity.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM business_capabilities WHERE id = 'cap-1'"))
            assert await _count(conn, "value_chain_activity_capabilities") == 0
            assert await _count(conn, "value_chain_activities") == 1

        # A deleted chain cascades to its activities (and their links).
        async with engine.begin() as conn:
            await conn.execute(sa.text(
                "INSERT INTO business_capabilities (id, name, level, position, created_at,"
                " updated_at) VALUES ('cap-2', 'Warehouse Management', 1, 0, now(), now())"
            ))
            await conn.execute(sa.text(
                "INSERT INTO value_chain_activity_capabilities (activity_id, capability_id)"
                " VALUES ('act-1', 'cap-2')"
            ))
            await conn.execute(sa.text("DELETE FROM value_chains WHERE id = 'vc-1'"))
            assert await _count(conn, "value_chain_activities") == 0
            assert await _count(conn, "value_chain_activity_capabilities") == 0
            assert await _count(conn, "business_capabilities") == 1
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "downgrade", "041")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert not (_TABLES & tables)
            assert "business_capabilities" in tables
    finally:
        await engine.dispose()
