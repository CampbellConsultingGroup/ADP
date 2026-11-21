"""Integration test: migration 058 (947 GEO-02) turns operating geographies into links.

Seeds two operating geographies at 057, upgrades, checks they are undated ``operates_in`` links
and that the new tables enforce their rules, then downgrades and checks the old table is back.

Uses its own database (it downgrades below head), like test_migration_057.py.
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
    collect_ignore_glob = ["test_migration_058.py"]


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


_SEED_057 = [
    "INSERT INTO org_units (id, name, level, created_at, updated_at)"
    " VALUES ('ou', 'Retail Co', 1, now(), now())",
    "INSERT INTO org_unit_geographies (org_unit_id, geography_id, created_at)"
    " VALUES ('ou', 'geo-DE', now()), ('ou', 'geo-m49-150', now())",
]


async def _scalar(conn, sql: str):
    return (await conn.execute(sa.text(sql))).scalar_one()


async def test_migration_058_moves_operating_geographies(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "057")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for stmt in _SEED_057:
                await conn.execute(sa.text(stmt))
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "058")
        async with engine.begin() as conn:
            assert (
                await _scalar(
                    conn,
                    "SELECT count(*) FROM org_unit_geo_links WHERE org_unit_id = 'ou'"
                    " AND relation = 'operates_in' AND valid_from IS NULL AND valid_to IS NULL",
                )
                == 2
            )
            assert (
                await _scalar(
                    conn,
                    "SELECT count(*) FROM information_schema.tables"
                    " WHERE table_name = 'org_unit_geographies'",
                )
                == 0
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO legal_entities (id, name, created_at, updated_at)"
                    " VALUES ('le', 'Retail GmbH', now(), now())"
                )
            )
        # The relation vocabulary and the date rule are enforced by the database too.
        for bad in (
            "INSERT INTO legal_entity_geo_links (id, legal_entity_id, relation, geography_id,"
            " created_at, updated_at) VALUES ('x', 'le', 'deployed_in', 'geo-DE', now(), now())",
            "INSERT INTO org_unit_geo_links (id, org_unit_id, relation, geography_id, valid_from,"
            " valid_to, created_at, updated_at) VALUES ('y', 'ou', 'operates_in', 'geo-FR',"
            " '2021-01-01', '2020-01-01', now(), now())",
            "INSERT INTO legal_entities (id, name, created_at, updated_at)"
            " VALUES ('le2', 'RETAIL GMBH', now(), now())",
        ):
            with pytest.raises(IntegrityError):
                async with engine.begin() as conn:
                    await conn.execute(sa.text(bad))
        # A legal entity link to the org unit (dropped again by the downgrade).
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    "INSERT INTO legal_entity_org_units (legal_entity_id, org_unit_id, created_at)"
                    " VALUES ('le', 'ou', now())"
                )
            )
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "057")
        async with engine.begin() as conn:
            assert (
                await _scalar(
                    conn, "SELECT count(*) FROM org_unit_geographies WHERE org_unit_id = 'ou'"
                )
                == 2
            )
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "058")
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM org_units WHERE id = 'ou'"))
            assert await _scalar(conn, "SELECT count(*) FROM org_unit_geo_links") == 0
    finally:
        await engine.dispose()
