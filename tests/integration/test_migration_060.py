"""Integration test: migration 060 (949 GEO-04) up, constraints, down, up.

Uses its own database (it downgrades below head), like test_migration_059.py.
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
    collect_ignore_glob = ["test_migration_060.py"]


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


_SUBDIVISION = (
    "INSERT INTO geographies (id, name, code, entity, place_type, parent_place_id, created_at,"
    " updated_at) VALUES ('geo-US-CA', 'California', 'US-CA', 'place', 'subdivision', {parent},"
    " now(), now())"
)


async def test_migration_060_places_and_blocs(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "060")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            assert await _scalar(
                conn,
                "SELECT count(*) FROM geo_memberships WHERE hierarchy_id = 'geoh-regulatory-blocs'",
            ) == 59
            assert await _scalar(
                conn,
                "SELECT count(*) FROM geo_memberships WHERE parent_id = 'geo-bloc-eu'"
                " AND (valid_to IS NULL OR valid_to > DATE '2026-11-21')",
            ) == 27
            assert await _scalar(
                conn, "SELECT parent_place_id FROM geographies WHERE id = 'geo-lloyds'"
            ) == "geo-GB"
            assert await _scalar(
                conn, "SELECT count(*) FROM geographies WHERE place_type IS NULL"
                " AND entity = 'place'"
            ) == 0
            await conn.execute(sa.text(_SUBDIVISION.format(parent="'geo-US'")))
        with pytest.raises(sa.exc.IntegrityError):  # a subdivision needs its country
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text(_SUBDIVISION.format(parent="NULL").replace("geo-US-CA", "geo-US-NY"))
                )
        with pytest.raises(sa.exc.IntegrityError):  # unknown place type
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("UPDATE geographies SET place_type = 'city' WHERE id = 'geo-DE'")
                )
        await engine.dispose()
        _run_alembic(migration_db_url, "downgrade", "059")
        async with engine.begin() as conn:
            assert await _scalar(
                conn, "SELECT count(*) FROM geographies WHERE id IN"
                " ('geo-US-CA', 'geo-lloyds', 'geo-bloc-eu')"
            ) == 0
            assert await _scalar(
                conn, "SELECT count(*) FROM geo_hierarchies WHERE id = 'geoh-regulatory-blocs'"
            ) == 0
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "060")
    finally:
        await engine.dispose()
