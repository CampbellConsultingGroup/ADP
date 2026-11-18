"""Integration test: migration 045 (EA pattern adoptions, ADP-mmm.3 / 936) applies and reverts
cleanly, and the database itself enforces what the store relies on: scope CHECKs, the partial
unique indexes (one adoption per pattern per domain / portfolio), unique names, CASCADE from
family, domain and application, and RESTRICT on a pinned version.

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
    collect_ignore_glob = ["test_migration_045.py"]


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


_DOMAIN = (
    "INSERT INTO business_domains (id, name, classification, risk_flags, created_at, updated_at)"
    " VALUES (:id, :name, 'strategic', '{}', now(), now())"
)
_APP = (
    "INSERT INTO applications (id, name, lifecycle_status, created_at, updated_at)"
    " VALUES (:id, :name, 'active', now(), now())"
)
_FAMILY = (
    "INSERT INTO ea_pattern (pattern_key, kind, owner_role, created_at, created_by)"
    " VALUES (:k, 'reference-architecture', 'enterprise', now(), 't')"
)
_VERSION = (
    "INSERT INTO ea_pattern_version (id, pattern_key, version, lifecycle, name, summary,"
    " definition, digest, created_at, created_by, lifecycle_changed_at, lifecycle_changed_by)"
    " VALUES (:id, :k, '1.0.0', 'current', 'n', 's', '{}'::jsonb, :d, now(), 't', now(), 't')"
)
_ADOPTION = (
    "INSERT INTO ea_pattern_adoption (id, pattern_key, pinned_version_id, scope_type, scope_ref,"
    " name, created_at, created_by, updated_at)"
    " VALUES (:id, :k, :v, :st, :sr, :n, now(), 't', now())"
)
_MEMBER = "INSERT INTO ea_pattern_adoption_member (adoption_id, application_id) VALUES (:a, :app)"
_PIN = (
    "INSERT INTO ea_pattern_adoption_pin (adoption_id, role_key, element_type, element_id)"
    " VALUES (:a, 'backbone', :t, 'hub')"
)


async def _count(conn, table: str) -> int:
    return (await conn.execute(sa.text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608


async def _expect_integrity_error(engine, sql: str, params: dict) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(sa.text(sql), params)


def _ad(id_: str, st: str, sr: str | None, n: str, v: str | None = None, k: str = "ea.t.p") -> dict:
    return {"id": id_, "k": k, "v": v, "st": st, "sr": sr, "n": n}


async def test_migration_045_upgrade_downgrade_constraints_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "044")
    _run_alembic(migration_db_url, "upgrade", "045")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text(_DOMAIN), {"id": "d1", "name": "Claims"})
            await conn.execute(sa.text(_DOMAIN), {"id": "d2", "name": "Billing"})
            await conn.execute(sa.text(_APP), {"id": "app1", "name": "Core"})
            await conn.execute(sa.text(_FAMILY), {"k": "ea.t.p"})
            await conn.execute(sa.text(_VERSION), {"id": "v1", "k": "ea.t.p", "d": "0" * 64})
            await conn.execute(
                sa.text(_ADOPTION), _ad("ad1", "business_domain", "d1", "Claims", "v1")
            )
            await conn.execute(sa.text(_ADOPTION), _ad("ad2", "portfolio", None, "All"))
            await conn.execute(sa.text(_ADOPTION), _ad("ad3", "application_set", None, "Set A"))
            await conn.execute(sa.text(_ADOPTION), _ad("ad4", "application_set", None, "Set B"))
            await conn.execute(sa.text(_ADOPTION), _ad("ad5", "business_domain", "d2", "Billing"))
            await conn.execute(sa.text(_MEMBER), {"a": "ad3", "app": "app1"})
            await conn.execute(sa.text(_PIN), {"a": "ad1", "t": "application"})

        # CHECKs and uniqueness.
        await _expect_integrity_error(engine, _ADOPTION, _ad("x1", "galaxy", None, "x1"))
        await _expect_integrity_error(engine, _ADOPTION, _ad("x2", "business_domain", None, "x2"))
        await _expect_integrity_error(engine, _ADOPTION, _ad("x3", "portfolio", "d1", "x3"))
        await _expect_integrity_error(engine, _ADOPTION, _ad("x4", "business_domain", "d1", "x4"))
        await _expect_integrity_error(engine, _ADOPTION, _ad("x5", "portfolio", None, "x5"))
        await _expect_integrity_error(
            engine, _ADOPTION, _ad("x6", "application_set", None, "Set A")
        )
        await _expect_integrity_error(engine, _PIN, {"a": "ad2", "t": "technology_standard"})

        # RESTRICT: a pinned version cannot be deleted.
        await _expect_integrity_error(
            engine, "DELETE FROM ea_pattern_version WHERE id = :id", {"id": "v1"}
        )

        # CASCADE: domain → adoption (+ pins); application → membership.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM business_domains WHERE id = 'd1'"))
            assert await _count(conn, "ea_pattern_adoption") == 4
            assert await _count(conn, "ea_pattern_adoption_pin") == 0
            await conn.execute(sa.text("DELETE FROM applications WHERE id = 'app1'"))
            assert await _count(conn, "ea_pattern_adoption_member") == 0
            assert await _count(conn, "ea_pattern_adoption") == 4
        # CASCADE: family → adoptions.
        async with engine.begin() as conn:
            await conn.execute(sa.text("DELETE FROM ea_pattern WHERE pattern_key = 'ea.t.p'"))
            assert await _count(conn, "ea_pattern_adoption") == 0
    finally:
        await engine.dispose()

    _run_alembic(migration_db_url, "downgrade", "044")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            tables = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
            assert not {t for t in tables if t.startswith("ea_pattern_adoption")}
            assert "ea_pattern" in tables
    finally:
        await engine.dispose()
