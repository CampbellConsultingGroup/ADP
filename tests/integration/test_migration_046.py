"""Integration test: migration 046 (application capabilities, 937 / ADP-6et.1) applies and
reverts cleanly, and the database itself enforces what the store relies on: the level CHECK, the
case-insensitive sibling-name index (including L1 roots, whose parent is NULL), duplicate-link
primary keys, and CASCADE from every end of every link table -- deleting a business capability,
technical capability, application or application capability removes only its own links.

Uses its own dedicated container (same reasoning as test_migration_043.py: it downgrades below
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
    collect_ignore_glob = ["test_migration_046.py"]


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


_BIZ = (
    "INSERT INTO business_capabilities (id, name, level, parent_id, position, created_at,"
    " updated_at) VALUES (:id, :name, :level, :parent, 0, now(), now())"
)
_TECH = (
    "INSERT INTO technical_capabilities (id, name, level, parent_id, created_at)"
    " VALUES (:id, :name, :level, :parent, now())"
)
_APP = (
    "INSERT INTO applications (id, name, lifecycle_status, created_at, updated_at)"
    " VALUES (:id, :name, 'active', now(), now())"
)
_AC = (
    "INSERT INTO application_capabilities (id, name, parent_id, level, created_at, updated_at)"
    " VALUES (:id, :name, :parent, :level, now(), now())"
)
_BIZ_LINK = (
    "INSERT INTO business_capability_app_capability_links"
    " (business_capability_id, app_capability_id, created_at) VALUES (:b, :a, now())"
)
_TECH_LINK = (
    "INSERT INTO app_capability_tech_cap_links (app_capability_id, tech_cap_id, created_at)"
    " VALUES (:a, :t, now())"
)
_REALIZES = (
    "INSERT INTO app_capability_realizations (app_capability_id, app_id, created_at)"
    " VALUES (:a, :app, now())"
)


async def _count(conn, table: str) -> int:
    return (await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


async def test_migration_046_upgrade_downgrade_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "045")
    _run_alembic(migration_db_url, "upgrade", "046")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(_BIZ), {"id": "b1", "name": "Sales", "level": 1, "parent": None}
            )
            await conn.execute(
                sa.text(_BIZ), {"id": "b3", "name": "Accept Payment", "level": 3, "parent": "b1"}
            )
            await conn.execute(
                sa.text(_TECH), {"id": "t1", "name": "Security", "level": 2, "parent": None}
            )
            await conn.execute(
                sa.text(_TECH), {"id": "t2", "name": "P2PE", "level": 3, "parent": "t1"}
            )
            await conn.execute(sa.text(_APP), {"id": "pos", "name": "Store POS"})
            await conn.execute(
                sa.text(_AC),
                {"id": "a1", "name": "Transaction Processing", "parent": None, "level": 1},
            )
            await conn.execute(
                sa.text(_AC), {"id": "a2", "name": "Payments", "parent": "a1", "level": 2}
            )
            await conn.execute(
                sa.text(_AC),
                {"id": "a3", "name": "Tender Authorization", "parent": "a2", "level": 3},
            )
            await conn.execute(
                sa.text(_AC), {"id": "a4", "name": "Card Refund", "parent": "a2", "level": 3}
            )
            for a in ("a3", "a4"):
                await conn.execute(sa.text(_BIZ_LINK), {"b": "b3", "a": a})
                await conn.execute(sa.text(_TECH_LINK), {"a": a, "t": "t2"})
                await conn.execute(sa.text(_REALIZES), {"a": a, "app": "pos"})
            await conn.execute(sa.text(_TECH_LINK), {"a": "a3", "t": "t1"})

        # Level CHECK, sibling-name index (case-insensitive, NULL-parent roots too), dup links.
        await _expect_integrity_error(
            engine, _AC, {"id": "x1", "name": "Deep", "parent": "a3", "level": 4}
        )
        await _expect_integrity_error(
            engine, _AC, {"id": "x2", "name": "PAYMENTS", "parent": "a1", "level": 2}
        )
        await _expect_integrity_error(
            engine, _AC, {"id": "x3", "name": "transaction processing", "parent": None, "level": 1}
        )
        await _expect_integrity_error(engine, _BIZ_LINK, {"b": "b3", "a": "a3"})
        await _expect_integrity_error(engine, _TECH_LINK, {"a": "a3", "t": "t2"})
        await _expect_integrity_error(engine, _REALIZES, {"a": "a3", "app": "pos"})
        # No cascade on the self-FK: a parent with children can't be deleted at the DB level either.
        await _expect_integrity_error(
            engine, "DELETE FROM application_capabilities WHERE id = 'a2'", {}
        )

        async with engine.begin() as conn:
            # Technical capability -> its links only.
            await conn.execute(sa.text("DELETE FROM technical_capabilities WHERE id = 't2'"))
            assert await _count(conn, "app_capability_tech_cap_links") == 1
            # Application -> its realizations only.
            await conn.execute(sa.text("DELETE FROM applications WHERE id = 'pos'"))
            assert await _count(conn, "app_capability_realizations") == 0
            # Business capability -> its links only; application capabilities stay.
            await conn.execute(sa.text("DELETE FROM business_capabilities WHERE id = 'b3'"))
            assert await _count(conn, "business_capability_app_capability_links") == 0
            assert await _count(conn, "application_capabilities") == 4
            # Application capability -> its remaining links.
            await conn.execute(sa.text("DELETE FROM application_capabilities WHERE id = 'a3'"))
            assert await _count(conn, "app_capability_tech_cap_links") == 0
            assert await _count(conn, "technical_capabilities") == 1
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "downgrade", "045")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert (
                not {
                    "application_capabilities",
                    "business_capability_app_capability_links",
                    "app_capability_tech_cap_links",
                    "app_capability_realizations",
                }
                & tables
            )
            assert {"business_capabilities", "technical_capabilities", "applications"} <= tables
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "upgrade", "046")  # and back up again
