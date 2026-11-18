"""Integration test: migration 051 (mapping rationale, 943 / ADP-55k.4) applies and reverts
cleanly. Existing realizations read NULL/NULL (unclassified, everywhere); the rationale CHECK
refuses unknown values; deleting a geography sets a realization's geography_id to NULL and keeps
its rationale.

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
    collect_ignore_glob = ["test_migration_051.py"]


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


_APP = (
    "INSERT INTO applications (id, name, lifecycle_status, created_at, updated_at)"
    " VALUES (:id, :name, 'active', now(), now())"
)
_AC = (
    "INSERT INTO application_capabilities (id, name, parent_id, level, created_at, updated_at)"
    " VALUES (:id, :name, :parent, :level, now(), now())"
)
_REAL = (
    "INSERT INTO app_capability_realizations (app_capability_id, app_id, created_at)"
    " VALUES (:ac, :app, now())"
)
_COLS = (
    "SELECT rationale, geography_id FROM app_capability_realizations"
    " WHERE app_capability_id = :ac AND app_id = :app"
)


async def _scalar(conn, sql: str, params: dict | None = None):
    return (await conn.execute(sa.text(sql), params or {})).scalar_one()


async def test_migration_051_columns_check_and_set_null(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "050")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for aid, name in [("pos", "Store POS"), ("ecom", "Commerce Cloud")]:
                await conn.execute(sa.text(_APP), {"id": aid, "name": name})
            for acid, name, parent, level in [
                ("a1", "Commerce", None, 1),
                ("a2", "Promotions", "a1", 2),
                ("a3", "Promotion Evaluation", "a2", 3),
            ]:
                await conn.execute(
                    sa.text(_AC), {"id": acid, "name": name, "parent": parent, "level": level}
                )
            await conn.execute(sa.text(_REAL), {"ac": "a3", "app": "pos"})
            await conn.execute(sa.text(_REAL), {"ac": "a3", "app": "ecom"})
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "051")
        async with engine.begin() as conn:
            # Existing rows: unclassified, everywhere.
            row = (await conn.execute(sa.text(_COLS), {"ac": "a3", "app": "pos"})).one()
            assert tuple(row) == (None, None)
            await conn.execute(
                sa.text(
                    "UPDATE app_capability_realizations SET rationale = 'tactical',"
                    " geography_id = 'geo-BR' WHERE app_id = 'ecom'"
                )
            )
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("UPDATE app_capability_realizations SET rationale = 'maybe'")
                )
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("UPDATE app_capability_realizations SET geography_id = 'no-such-geo'")
                )
        async with engine.begin() as conn:
            # Geography delete clears the scope, keeps the rationale.
            await conn.execute(sa.text("DELETE FROM geographies WHERE id = 'geo-BR'"))
            row = (await conn.execute(sa.text(_COLS), {"ac": "a3", "app": "ecom"})).one()
            assert tuple(row) == ("tactical", None)
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "050")
        async with engine.begin() as conn:
            cols = {
                r[0]
                for r in await conn.execute(
                    sa.text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'app_capability_realizations'"
                    )
                )
            }
            assert not {"rationale", "geography_id"} & cols
            assert await _scalar(conn, "SELECT count(*) FROM app_capability_realizations") == 2
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "051")
    finally:
        await engine.dispose()
