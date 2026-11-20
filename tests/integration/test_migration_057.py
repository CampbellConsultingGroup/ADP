"""Integration test: migration 057 (946 GEO-01) keeps every geography id and link.

Seeds the 940 shape at 056 -- including a user-added region with a country under it and links
from every referencing table -- upgrades, checks places/nodes/memberships and that the links
still resolve, then downgrades and checks the old tree is back.

Uses its own database (it downgrades below head), like test_migration_052.py.
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
    collect_ignore_glob = ["test_migration_057.py"]


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


_SEED_056 = [
    # A region a user added under Global, with a country of its own under it.
    "INSERT INTO geographies (id, name, level, parent_id, created_at, updated_at) VALUES"
    " ('u-emea', 'EMEA', 2, 'geo-001', now(), now())",
    "INSERT INTO geographies (id, name, code, level, parent_id, created_at, updated_at) VALUES"
    " ('u-xk', 'Kosovo', 'XK', 3, 'u-emea', now(), now())",
    "INSERT INTO org_units (id, name, level, primary_geography_id, created_at, updated_at)"
    " VALUES ('ou', 'Retail Co', 1, 'geo-m49-150', now(), now())",
    "INSERT INTO org_unit_geographies (org_unit_id, geography_id, created_at)"
    " VALUES ('ou', 'geo-DE', now()), ('ou', 'u-emea', now())",
]


async def _scalar(conn, sql: str):
    return (await conn.execute(sa.text(sql))).scalar_one()


async def test_migration_057_keeps_ids_and_links(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "056")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for stmt in _SEED_056:
                await conn.execute(sa.text(stmt))
            before = await _scalar(conn, "SELECT count(*) FROM geographies")
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "057")
        async with engine.begin() as conn:
            assert await _scalar(conn, "SELECT count(*) FROM geographies") == before
            assert await _scalar(
                conn, "SELECT count(*) FROM geographies WHERE entity = 'node'"
                " AND hierarchy_id = 'geoh-m49'"
            ) == 6
            assert await _scalar(
                conn, "SELECT hierarchy_id FROM geographies WHERE id = 'u-emea'"
            ) == "geoh-custom-migrated"
            assert await _scalar(
                conn, "SELECT entity FROM geographies WHERE id = 'u-xk'"
            ) == "place"
            # Old parent links became memberships.
            assert await _scalar(
                conn, "SELECT count(*) FROM geo_memberships WHERE parent_id = 'geo-m49-150'"
                " AND child_id = 'geo-DE' AND hierarchy_id = 'geoh-m49'"
            ) == 1
            assert await _scalar(
                conn, "SELECT hierarchy_id FROM geo_memberships WHERE child_id = 'u-xk'"
            ) == "geoh-custom-migrated"
            # The migrated custom region is a root of its hierarchy, not under Global.
            assert await _scalar(
                conn, "SELECT count(*) FROM geo_memberships WHERE child_id = 'u-emea'"
            ) == 0
            # Links untouched.
            assert await _scalar(conn, "SELECT count(*) FROM org_unit_geographies") == 2
            assert await _scalar(
                conn, "SELECT primary_geography_id FROM org_units WHERE id = 'ou'"
            ) == "geo-m49-150"
            # The reference hierarchy is a strict tree: every place has one parent there.
            assert await _scalar(
                conn,
                "SELECT count(*) FROM (SELECT child_id FROM geo_memberships"
                " WHERE hierarchy_id = 'geoh-m49' GROUP BY child_id HAVING count(*) > 1) x",
            ) == 0
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "056")
        async with engine.begin() as conn:
            assert await _scalar(
                conn, "SELECT parent_id FROM geographies WHERE id = 'geo-DE'"
            ) == "geo-m49-150"
            assert await _scalar(conn, "SELECT level FROM geographies WHERE id = 'geo-001'") == 1
            assert await _scalar(
                conn, "SELECT name FROM geographies WHERE id = 'u-emea'"
            ) == "EMEA (Custom (migrated))"
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "057")
    finally:
        await engine.dispose()
