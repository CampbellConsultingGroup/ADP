"""Integration test: migration 052 (agent traceability, 944 / ADP-12x) applies and reverts
cleanly. The three automates link tables and control_agent_mapping cascade on both legs; the
mapping CHECK refuses unknown statuses; downgrade drops all four tables.

Uses its own container (it downgrades below head), like test_migration_051.py.
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
    collect_ignore_glob = ["test_migration_052.py"]

_TABLES = (
    "agent_capability_links", "agent_stage_links", "agent_activity_links", "control_agent_mapping",
)


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


_SEED = [
    "INSERT INTO agents (id, name, autonomy_level, human_approval, created_at, updated_at)"
    " VALUES ('ag1', 'Agent One', 2, 'on_write', now(), now()),"
    " ('ag2', 'Agent Two', 4, 'none', now(), now())",
    "INSERT INTO business_capabilities (id, name, level, position, created_at, updated_at)"
    " VALUES ('c3', 'Process Checkout', 3, 0, now(), now())",
    "INSERT INTO value_streams (id, name, position, created_at, updated_at)"
    " VALUES ('vs1', 'Order to Cash', 0, now(), now())",
    "INSERT INTO value_stream_stages (id, value_stream_id, name, position)"
    " VALUES ('st1', 'vs1', 'Take Order', 0)",
    "INSERT INTO value_chains (id, name, created_at, updated_at)"
    " VALUES ('ch1', 'Retail', now(), now())",
    "INSERT INTO value_chain_activities (id, value_chain_id, name, category)"
    " VALUES ('act1', 'ch1', 'Inbound Logistics', 'primary')",
    "INSERT INTO regulatory_frameworks (id, name, version, authority, jurisdiction)"
    " VALUES ('fw1', 'EU AI Act', '2024/1689', 'EU', 'EU')",
    "INSERT INTO controls (id, framework_id, code, title) VALUES ('ct1', 'fw1', 'Art. 50', 'T')",
    "INSERT INTO agent_capability_links (agent_id, capability_id)"
    " VALUES ('ag1', 'c3'), ('ag2', 'c3')",
    "INSERT INTO agent_stage_links (agent_id, stage_id) VALUES ('ag1', 'st1')",
    "INSERT INTO agent_activity_links (agent_id, activity_id) VALUES ('ag1', 'act1')",
    "INSERT INTO control_agent_mapping (control_id, agent_id, compliance_status)"
    " VALUES ('ct1', 'ag1', 'compliant'), ('ct1', 'ag2', 'partial')",
]


async def _count(conn, table: str, where: str = "") -> int:
    sql = f"SELECT count(*) FROM {table}" + (f" WHERE {where}" if where else "")
    return (await conn.execute(sa.text(sql))).scalar_one()


async def test_migration_052_tables_check_and_cascades(migration_db_url):
    from sqlalchemy.ext.asyncio import create_async_engine

    _run_alembic(migration_db_url, "upgrade", "052")
    engine = create_async_engine(migration_db_url)
    try:
        async with engine.begin() as conn:
            for stmt in _SEED:
                await conn.execute(sa.text(stmt))

        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text("UPDATE control_agent_mapping SET compliance_status = 'maybe'")
                )
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(
                    sa.text(
                        "INSERT INTO agent_capability_links (agent_id, capability_id)"
                        " VALUES ('ag1', 'no-such-cap')"
                    )
                )

        async with engine.begin() as conn:
            # Deleting an agent removes its links and mappings, never the targets.
            await conn.execute(sa.text("DELETE FROM agents WHERE id = 'ag2'"))
            assert await _count(conn, "agent_capability_links") == 1
            assert await _count(conn, "control_agent_mapping") == 1
            assert await _count(conn, "business_capabilities") == 1
            # Deleting each target removes the links that point at it, never the agent.
            await conn.execute(sa.text("DELETE FROM business_capabilities WHERE id = 'c3'"))
            await conn.execute(sa.text("DELETE FROM value_stream_stages WHERE id = 'st1'"))
            await conn.execute(sa.text("DELETE FROM value_chain_activities WHERE id = 'act1'"))
            await conn.execute(sa.text("DELETE FROM controls WHERE id = 'ct1'"))
            for table in _TABLES:
                assert await _count(conn, table) == 0
            assert await _count(conn, "agents") == 1
        await engine.dispose()

        _run_alembic(migration_db_url, "downgrade", "051")
        async with engine.begin() as conn:
            names = {
                r[0]
                for r in await conn.execute(
                    sa.text("SELECT table_name FROM information_schema.tables")
                )
            }
            assert not set(_TABLES) & names
            assert await _count(conn, "agents") == 1
        await engine.dispose()
        _run_alembic(migration_db_url, "upgrade", "052")
    finally:
        await engine.dispose()
