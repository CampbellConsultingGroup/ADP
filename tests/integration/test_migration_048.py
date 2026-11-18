"""Integration test: migration 048 (org units + geography, 940 / ADP-55k.1) applies and reverts
cleanly, seeds the geography tree from the data file, and the database enforces what the store
relies on: level CHECKs, case-insensitive sibling names (including roots), unique country codes,
CASCADE on the link table, and SET NULL on applications / primary geography.

Uses its own database (it downgrades below head), like test_migration_047.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


def _docker_available() -> bool:
    import shutil

    return shutil.which("docker") is not None


if not _docker_available():
    collect_ignore_glob = ["test_migration_048.py"]


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


_OU = (
    "INSERT INTO org_units (id, name, parent_id, level, primary_geography_id, created_at,"
    " updated_at) VALUES (:id, :name, :parent, :level, :geo, now(), now())"
)
_APP = (
    "INSERT INTO applications (id, name, created_at, updated_at) VALUES (:id, :name, now(), now())"
)


async def _scalar(conn, sql: str, params: dict | None = None):
    return (await conn.execute(sa.text(sql), params or {})).scalar_one()


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


async def test_migration_048_seed_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    from adp.organization.geodata import geography_seed_rows

    expected = len(geography_seed_rows(datetime.now(timezone.utc)))
    _run_alembic(migration_db_url, "upgrade", "048")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            assert await _scalar(conn, "SELECT count(*) FROM geographies") == expected
            assert await _scalar(conn, "SELECT count(*) FROM geographies WHERE level = 2") == 5
            assert (
                await _scalar(conn, "SELECT parent_id FROM geographies WHERE id = 'geo-DE'")
                == "geo-m49-150"
            )
            assert (
                await _scalar(conn, "SELECT parent_id FROM geographies WHERE id = 'geo-TW'")
                == "geo-001"
            )

            await conn.execute(
                sa.text(_OU),
                {"id": "o1", "name": "Retail Co", "parent": None, "level": 1, "geo": "geo-DE"},
            )
            await conn.execute(sa.text(_APP), {"id": "a1", "name": "POS"})
            await conn.execute(
                sa.text("UPDATE applications SET owning_org_unit_id = 'o1' WHERE id = 'a1'")
            )
            await conn.execute(
                sa.text("INSERT INTO org_unit_geographies VALUES ('o1', 'geo-US', now())")
            )

        # Level CHECK, case-insensitive siblings (roots included), unique country code.
        await _expect_integrity_error(
            engine, _OU, {"id": "o4", "name": "x", "parent": None, "level": 4, "geo": None}
        )
        await _expect_integrity_error(
            engine, _OU, {"id": "o2", "name": "retail co", "parent": None, "level": 1, "geo": None}
        )
        await _expect_integrity_error(
            engine,
            "INSERT INTO geographies (id, name, code, parent_id, level, created_at, updated_at)"
            " VALUES ('g-x', 'Germany Two', 'DE', 'geo-m49-150', 3, now(), now())",
            {},
        )

        async with engine.begin() as conn:
            # Deleting the primary geography clears it; its links cascade.
            await conn.execute(
                sa.text("DELETE FROM org_unit_geographies WHERE geography_id = 'geo-DE'")
            )
            await conn.execute(sa.text("DELETE FROM geographies WHERE id = 'geo-DE'"))
            assert (
                await _scalar(conn, "SELECT primary_geography_id FROM org_units WHERE id = 'o1'")
                is None
            )
            await conn.execute(sa.text("DELETE FROM geographies WHERE id = 'geo-US'"))
            assert await _scalar(conn, "SELECT count(*) FROM org_unit_geographies") == 0
            # Deleting the org unit keeps the application, clears its link.
            await conn.execute(sa.text("DELETE FROM org_units WHERE id = 'o1'"))
            assert (
                await _scalar(conn, "SELECT owning_org_unit_id FROM applications WHERE id = 'a1'")
                is None
            )
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "047")
        async with engine.begin() as conn:
            tables = {
                r[0]
                for r in await conn.execute(
                    sa.text(
                        "SELECT table_name FROM information_schema.tables"
                        " WHERE table_schema = 'public'"
                    )
                )
            }
            assert not {"org_units", "geographies", "org_unit_geographies"} & tables
            cols = {
                r[0]
                for r in await conn.execute(
                    sa.text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'applications'"
                    )
                )
            }
            assert "owning_org_unit_id" not in cols
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "048")
    finally:
        await engine.dispose()
