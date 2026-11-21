"""Integration test: migration 059 (948 GEO-03) up, cascade and down.

Uses its own database (it downgrades below head), like test_migration_058.py.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
import sqlalchemy as sa


def _docker_available() -> bool:
    import shutil

    return shutil.which("docker") is not None


if not _docker_available():
    collect_ignore_glob = ["test_migration_059.py"]


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
    """Override conftest.py's autouse table truncation: this file uses its own database."""
    yield


async def _scalar(conn, sql: str):
    return (await conn.execute(sa.text(sql))).scalar_one()


async def test_migration_059_jurisdiction_tables(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "059")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO regulatory_frameworks (id, name, jurisdiction, authority, version,"
                    " status, created_at, updated_at) VALUES ('fw', 'GDPR', 'EU', 'EU', '1',"
                    " 'in_force', now(), now())"
                )
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO framework_jurisdiction_geographies VALUES ('fw', 'geo-DE', now())"
                )
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO framework_jurisdiction_triggers VALUES"
                    " ('fw', 'application', 'processes_personal_data_of', now())"
                )
            )
        with pytest.raises(sa.exc.IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text(
                        "INSERT INTO framework_jurisdiction_triggers VALUES"
                        " ('fw', 'org_unit', 'operates_in', now())"
                    )
                )
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM regulatory_frameworks WHERE id = 'fw'"))
            assert await _scalar(conn, "SELECT count(*) FROM framework_jurisdiction_triggers") == 0
            assert (
                await _scalar(conn, "SELECT count(*) FROM framework_jurisdiction_geographies") == 0
            )
        await engine.dispose()
        _run_alembic(migration_db_url, "downgrade", "058")
        _run_alembic(migration_db_url, "upgrade", "059")
    finally:
        await engine.dispose()
