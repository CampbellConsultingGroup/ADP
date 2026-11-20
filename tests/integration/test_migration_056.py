"""Integration test: migration 056 (business domain owner) applies and reverts cleanly.

Free-text org_unit values that name exactly one division (case and surrounding spaces
ignored) become a link and the text is cleared; other text is kept. Deleting the division
clears the link. Downgrade writes a linked division's name back into the text.

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
    collect_ignore_glob = ["test_migration_056.py"]


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


_SEED = [
    "INSERT INTO org_units (id, name, parent_id, level, created_at, updated_at) VALUES"
    " ('ent', 'Retail Co', NULL, 1, now(), now()),"
    " ('ops', 'Retail Operations', 'ent', 2, now(), now()),"
    " ('fin', 'Finance', 'ent', 2, now(), now())",
    "INSERT INTO business_domains (id, name, classification, org_unit, risk_flags,"
    " created_at, updated_at) VALUES"
    " ('d1', 'Stores', 'strategic', ' retail operations ', '{}', now(), now()),"
    " ('d2', 'People', 'commodity', 'People', '{}', now(), now()),"
    " ('d3', 'Group', 'commodity', 'Retail Co', '{}', now(), now()),"
    " ('d4', 'Empty', 'commodity', NULL, '{}', now(), now())",
]


async def _domains(conn) -> dict[str, tuple]:
    rows = await conn.execute(
        sa.text("SELECT id, org_unit, owner_org_unit_id FROM business_domains")
    )
    return {r[0]: (r[1], r[2]) for r in rows}


async def test_migration_056_links_matching_text(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "055")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for stmt in _SEED:
                await conn.execute(sa.text(stmt))
        await engine.dispose()

        _run_alembic(migration_db_url, "upgrade", "056")
        async with engine.begin() as conn:
            assert await _domains(conn) == {
                "d1": (None, "ops"),  # matched a division: linked, text cleared
                "d2": ("People", None),  # no such division: text kept
                "d3": ("Retail Co", None),  # the enterprise is not a division
                "d4": (None, None),
            }
            await conn.execute(
                sa.text("UPDATE business_domains SET owner_org_unit_id = 'fin' WHERE id = 'd4'")
            )
            await conn.execute(sa.text("DELETE FROM org_units WHERE id = 'fin'"))
            assert (await _domains(conn))["d4"] == (None, None)
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "055")
        async with engine.begin() as conn:
            text = await conn.execute(
                sa.text("SELECT org_unit FROM business_domains WHERE id = 'd1'")
            )
            assert text.scalar_one() == "Retail Operations"
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "056")
    finally:
        await engine.dispose()
