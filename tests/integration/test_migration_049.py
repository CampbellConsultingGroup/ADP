"""Integration test: migration 049 (capability <-> org unit mappings, 941 / ADP-55k.2) applies and
reverts cleanly, and the database enforces what the store relies on: the role and geography
CHECKs, at most one owner per capability, no exact duplicates (NULL geography included), CASCADE on
capability and org-unit delete, SET NULL on geography delete.

Uses its own database (it downgrades below head), like test_migration_048.py.
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
    collect_ignore_glob = ["test_migration_049.py"]


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
_OU = (
    "INSERT INTO org_units (id, name, parent_id, level, created_at, updated_at)"
    " VALUES (:id, :name, NULL, 1, now(), now())"
)
_MAP = (
    "INSERT INTO capability_org_mappings (id, capability_id, org_unit_id, role, geography_id,"
    " created_at) VALUES (:id, :cap, :ou, :role, :geo, now())"
)


async def _scalar(conn, sql: str, params: dict | None = None):
    return (await conn.execute(sa.text(sql), params or {})).scalar_one()


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


def _m(id_: str, cap: str, ou: str, role: str, geo: str | None = None) -> dict:
    return {"id": id_, "cap": cap, "ou": ou, "role": role, "geo": geo}


async def test_migration_049_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "049")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(_CAP), {"id": "c1", "name": "Sell", "level": 1, "parent": None}
            )
            await conn.execute(
                sa.text(_CAP), {"id": "c2", "name": "Pay", "level": 2, "parent": "c1"}
            )
            await conn.execute(
                sa.text(_CAP), {"id": "c3", "name": "Accept Payment", "level": 3, "parent": "c2"}
            )
            await conn.execute(sa.text(_OU), {"id": "o1", "name": "Stores"})
            await conn.execute(sa.text(_OU), {"id": "o2", "name": "E-commerce"})
            await conn.execute(sa.text(_MAP), _m("m1", "c2", "o1", "owner"))
            await conn.execute(sa.text(_MAP), _m("m2", "c3", "o1", "performer"))
            await conn.execute(sa.text(_MAP), _m("m3", "c3", "o1", "performer", "geo-DE"))
            await conn.execute(sa.text(_MAP), _m("m4", "c3", "o2", "contributor"))

        # Role CHECK; geography only on performers; one owner; no duplicates (NULL geography too).
        await _expect_integrity_error(engine, _MAP, _m("x1", "c3", "o2", "sponsor"))
        await _expect_integrity_error(engine, _MAP, _m("x2", "c3", "o2", "contributor", "geo-DE"))
        await _expect_integrity_error(engine, _MAP, _m("x3", "c2", "o2", "owner"))
        await _expect_integrity_error(engine, _MAP, _m("x4", "c3", "o1", "performer"))
        await _expect_integrity_error(engine, _MAP, _m("x5", "c3", "o1", "performer", "geo-DE"))

        async with engine.begin() as conn:
            # Geography delete clears it (the store merges duplicates first; here there is none
            # left to collide once m2 is gone).
            await conn.execute(sa.text("DELETE FROM capability_org_mappings WHERE id = 'm2'"))
            await conn.execute(sa.text("DELETE FROM geographies WHERE id = 'geo-DE'"))
            assert (
                await _scalar(
                    conn, "SELECT geography_id FROM capability_org_mappings WHERE id = 'm3'"
                )
                is None
            )
            # Org unit delete cascades its mappings.
            await conn.execute(sa.text("DELETE FROM org_units WHERE id = 'o2'"))
            assert (
                await _scalar(
                    conn, "SELECT count(*) FROM capability_org_mappings WHERE org_unit_id = 'o2'"
                )
                == 0
            )
            # Capability delete cascades its mappings.
            await conn.execute(sa.text("DELETE FROM business_capabilities WHERE id = 'c3'"))
            assert (
                await _scalar(
                    conn, "SELECT count(*) FROM capability_org_mappings WHERE capability_id = 'c3'"
                )
                == 0
            )
            assert await _scalar(conn, "SELECT count(*) FROM capability_org_mappings") == 1
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "048")
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
            assert "capability_org_mappings" not in tables
            assert "org_units" in tables
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "049")
    finally:
        await engine.dispose()
