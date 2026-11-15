"""Integration test: migration 044 (EA pattern registry, ADP-mmm.2 / 935) applies and reverts
cleanly, and the database itself enforces what the store relies on: the named CHECKs, at most one
'current' version per family (partial unique index), and ON DELETE CASCADE from family to
versions to relations/events.

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
    collect_ignore_glob = ["test_migration_044.py"]


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


_FAMILY = (
    "INSERT INTO ea_pattern (pattern_key, kind, owner_role, created_at, created_by)"
    " VALUES (:k, :kind, 'enterprise', now(), 'test')"
)
_VERSION = (
    "INSERT INTO ea_pattern_version (id, pattern_key, version, lifecycle, name, summary,"
    " definition, digest, created_at, created_by, lifecycle_changed_at, lifecycle_changed_by)"
    " VALUES (:id, :k, :v, :lc, 'n', 's', '{}'::jsonb, :d, now(), 't', now(), 't')"
)
_RELATION = (
    "INSERT INTO ea_pattern_relation (source_version_id, target_pattern_key, relation_type)"
    " VALUES (:src, :tgt, :t)"
)
_EVENT = (
    "INSERT INTO ea_pattern_lifecycle_event (id, version_id, from_state, to_state, reason,"
    " confirmation_id, actor, at) VALUES (:id, :v, 'draft', :to, :r, 'c', 't', now())"
)
_D = "0" * 64


async def _count(conn, table: str) -> int:
    return (await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


async def test_migration_044_upgrade_downgrade_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "043")
    _run_alembic(migration_db_url, "upgrade", "044")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert {
                "ea_pattern",
                "ea_pattern_version",
                "ea_pattern_relation",
                "ea_pattern_lifecycle_event",
            } <= tables
            checks = await conn.run_sync(
                lambda c: {
                    ck["name"]
                    for t in ("ea_pattern", "ea_pattern_version")
                    for ck in sa.inspect(c).get_check_constraints(t)
                }
            )
            assert {
                "ck_ea_pattern_key_format",
                "ck_ea_pattern_kind",
                "ck_ea_pattern_owner_role",
                "ck_ea_pattern_version_semver",
                "ck_ea_pattern_version_lifecycle",
            } <= checks
            await conn.execute(sa.text(_FAMILY), {"k": "ea.test.one", "kind": "anti-pattern"})
            for vid, ver, lc in (("v1", "1.0.0", "current"), ("v2", "1.1.0", "draft")):
                await conn.execute(
                    sa.text(_VERSION), {"id": vid, "k": "ea.test.one", "v": ver, "lc": lc, "d": _D}
                )
            await conn.execute(
                sa.text(_RELATION), {"src": "v1", "tgt": "ea.not.yet", "t": "replaces"}
            )
            await conn.execute(sa.text(_EVENT), {"id": "e1", "v": "v1", "to": "proposed", "r": "x"})

        # CHECKs.
        await _expect_integrity_error(engine, _FAMILY, {"k": "Bad Key", "kind": "anti-pattern"})
        await _expect_integrity_error(engine, _FAMILY, {"k": "ea.test.two", "kind": "nope"})
        await _expect_integrity_error(
            engine, _VERSION, {"id": "v3", "k": "ea.test.one", "v": "1.0", "lc": "draft", "d": _D}
        )
        await _expect_integrity_error(
            engine,
            _VERSION,
            {"id": "v3", "k": "ea.test.one", "v": "2.0.0", "lc": "complete", "d": _D},
        )
        await _expect_integrity_error(
            engine, _RELATION, {"src": "v1", "tgt": "ea.x.y", "t": "owns"}
        )
        await _expect_integrity_error(engine, _EVENT, {"id": "e2", "v": "v1", "to": "x", "r": "r"})
        await _expect_integrity_error(
            engine, _EVENT, {"id": "e3", "v": "v1", "to": "draft", "r": ""}
        )
        # UNIQUE (key, version) and at most one current per family.
        await _expect_integrity_error(
            engine, _VERSION, {"id": "v4", "k": "ea.test.one", "v": "1.0.0", "lc": "draft", "d": _D}
        )
        await _expect_integrity_error(
            engine,
            _VERSION,
            {"id": "v5", "k": "ea.test.one", "v": "3.0.0", "lc": "current", "d": _D},
        )

        # Deleting the family cascades to versions, relations and events.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM ea_pattern WHERE pattern_key = 'ea.test.one'"))
            for table in (
                "ea_pattern_version",
                "ea_pattern_relation",
                "ea_pattern_lifecycle_event",
            ):
                assert await _count(conn, table) == 0
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "downgrade", "043")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert not {t for t in tables if t.startswith("ea_pattern")}
    finally:
        await engine.dispose()
