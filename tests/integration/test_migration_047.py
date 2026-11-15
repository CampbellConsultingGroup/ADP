"""Integration test: migration 047 (technical capability lifecycle, 938 / ADP-6et.2) applies and
reverts cleanly. Existing rows become 'current' with no end-of-life date, the CHECK rejects an
unknown status, and the downgrade removes both columns.

Uses its own dedicated container (it downgrades below head), like test_migration_046.py.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError


def _docker_available() -> bool:
    import shutil

    return shutil.which("docker") is not None


if not _docker_available():
    collect_ignore_glob = ["test_migration_047.py"]


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


_TECH = (
    "INSERT INTO technical_capabilities (id, name, level, parent_id, created_at)"
    " VALUES (:id, :name, 1, NULL, now())"
)


async def _columns(conn) -> set[str]:
    rows = await conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'technical_capabilities'"
        )
    )
    return {r[0] for r in rows}


async def test_migration_047_upgrade_check_and_downgrade(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "046")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(_TECH), {"id": "t1", "name": "Offline Sync"})
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "047")
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    sa.text(
                        "SELECT lifecycle_status, end_of_life_date FROM technical_capabilities"
                        " WHERE id = 't1'"
                    )
                )
            ).one()
            assert row == ("current", None)
            await conn.execute(
                sa.text(
                    "UPDATE technical_capabilities SET lifecycle_status = 'retiring',"
                    " end_of_life_date = DATE '2027-06-30' WHERE id = 't1'"
                )
            )
        with pytest.raises(DBAPIError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("UPDATE technical_capabilities SET lifecycle_status = 'bogus'")
                )
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "046")
        async with engine.begin() as conn:
            cols = await _columns(conn)
            assert "lifecycle_status" not in cols and "end_of_life_date" not in cols
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "047")
        async with engine.begin() as conn:
            assert {"lifecycle_status", "end_of_life_date"} <= await _columns(conn)
    finally:
        await engine.dispose()
