"""Integration test: migration 050 (regional assessments, 942 / ADP-55k.3) applies and reverts
cleanly, and the database enforces what the store relies on: the maturity, content and note-length
CHECKs, one assessment per capability and geography, and CASCADE on capability, geography and
region-specific flag delete (the flag itself survives losing its geographies).

Uses its own database (it downgrades below head), like test_migration_050.py.
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
    collect_ignore_glob = ["test_migration_050.py"]


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


_CAP = (
    "INSERT INTO business_capabilities (id, name, level, parent_id, position, created_at,"
    " updated_at) VALUES (:id, :name, :level, :parent, 0, now(), now())"
)
_RA = (
    "INSERT INTO capability_regional_assessments (id, capability_id, geography_id,"
    " maturity_level, note, created_at, updated_at)"
    " VALUES (:id, :cap, :geo, :m, :note, now(), now())"
)


async def _scalar(conn, sql: str, params: dict | None = None):
    return (await conn.execute(sa.text(sql), params or {})).scalar_one()


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


def _ra(id_: str, cap: str, geo: str, m: int | None = None, note: str | None = None) -> dict:
    return {"id": id_, "cap": cap, "geo": geo, "m": m, "note": note}


async def test_migration_050_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "050")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for cid, name, level, parent in [
                ("c1", "Sell", 1, None),
                ("c2", "Pay", 2, "c1"),
                ("c3", "Accept Payment", 3, "c2"),
            ]:
                await conn.execute(
                    sa.text(_CAP), {"id": cid, "name": name, "level": level, "parent": parent}
                )
            await conn.execute(sa.text(_RA), _ra("a1", "c3", "geo-m49-150", 4))
            await conn.execute(sa.text(_RA), _ra("a2", "c3", "geo-BR", None, "manual"))
            await conn.execute(sa.text(_RA), _ra("a3", "c2", "geo-DE", 2))
            await conn.execute(
                sa.text("INSERT INTO region_specific_capabilities VALUES ('c3', now())")
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO region_specific_capability_geographies"
                    " VALUES ('c3', 'geo-BR', now())"
                )
            )

        # Maturity 1-5; score or note required; note length; one per capability + geography.
        await _expect_integrity_error(engine, _RA, _ra("x1", "c3", "geo-DE", 6))
        await _expect_integrity_error(engine, _RA, _ra("x2", "c3", "geo-DE"))
        await _expect_integrity_error(engine, _RA, _ra("x3", "c3", "geo-DE", None, "x" * 1001))
        await _expect_integrity_error(engine, _RA, _ra("x4", "c3", "geo-m49-150", 2))

        async with engine.begin() as conn:
            # Geography delete removes its assessments and scope rows; the flag survives.
            await conn.execute(sa.text("DELETE FROM geographies WHERE id = 'geo-BR'"))
            assert (
                await _scalar(
                    conn,
                    "SELECT count(*) FROM capability_regional_assessments"
                    " WHERE geography_id = 'geo-BR'",
                )
                == 0
            )
            assert (
                await _scalar(conn, "SELECT count(*) FROM region_specific_capability_geographies")
                == 0
            )
            assert await _scalar(conn, "SELECT count(*) FROM region_specific_capabilities") == 1
            # Clearing the flag cascades its geographies.
            await conn.execute(
                sa.text(
                    "INSERT INTO region_specific_capability_geographies"
                    " VALUES ('c3', 'geo-DE', now())"
                )
            )
            await conn.execute(sa.text("DELETE FROM region_specific_capabilities"))
            assert (
                await _scalar(conn, "SELECT count(*) FROM region_specific_capability_geographies")
                == 0
            )
            # Capability delete removes its assessments.
            await conn.execute(sa.text("DELETE FROM business_capabilities WHERE id = 'c3'"))
            assert (
                await _scalar(
                    conn,
                    "SELECT count(*) FROM capability_regional_assessments"
                    " WHERE capability_id = 'c3'",
                )
                == 0
            )
            assert await _scalar(conn, "SELECT count(*) FROM capability_regional_assessments") == 1
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "049")
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
            assert (
                not {
                    "capability_regional_assessments",
                    "region_specific_capabilities",
                    "region_specific_capability_geographies",
                }
                & tables
            )
            assert "capability_org_mappings" in tables
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "050")
    finally:
        await engine.dispose()
