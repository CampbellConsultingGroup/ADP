"""Integration test: migration 023 (agent_prompt_overrides/agent_prompt_history)
applies and reverts cleanly, and enforces the change_type CHECK constraint it
declares (ADP-SPEC-042).

Uses its own dedicated container rather than the shared session-scoped
`db_engine` fixture, since this test deliberately downgrades below head --
sharing that engine would corrupt state for every other integration test
in the same session regardless of execution order.
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
    collect_ignore_glob = ["test_migration_023.py"]


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
    """Override conftest.py's async autouse table-truncation fixture
    (ADP-isj) with a no-op: this file uses its own dedicated, non-shared
    container (see module docstring) rather than db_engine, so there's
    nothing to truncate and no reason to force the shared container to
    spin up just for this override."""
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


async def test_migration_023_upgrade_creates_tables_with_check_constraint(migration_db_url):
    _run_alembic(migration_db_url, "upgrade", "022")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migration_db_url)
    try:
        _run_alembic(migration_db_url, "upgrade", "023")

        async with engine.begin() as conn:
            def _table_names(sync_conn):
                return sa.inspect(sync_conn).get_table_names()

            tables = await conn.run_sync(_table_names)
            assert "agent_prompt_overrides" in tables
            assert "agent_prompt_history" in tables

            def _index_names(sync_conn):
                return {
                    ix["name"] for ix in sa.inspect(sync_conn).get_indexes("agent_prompt_history")
                }

            indexes = await conn.run_sync(_index_names)
            assert "ix_agent_prompt_history_agent_id_changed_at" in indexes

            await conn.execute(
                sa.text(
                    "INSERT INTO agent_prompt_overrides "
                    "(agent_id, prompt_text, updated_by, updated_at, version) "
                    "VALUES ('chat_assistant', 'You are helpful.', 'alice', now(), 1)"
                )
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO agent_prompt_history "
                    "(agent_id, actor, changed_at, change_type, prior_text, new_text, "
                    "confirmation_id) VALUES "
                    "('chat_assistant', 'alice', now(), 'edit', 'old', 'new', 'CONFIRM-1')"
                )
            )

        # change_type CHECK constraint rejects an out-of-set value.
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    sa.text(
                        "INSERT INTO agent_prompt_history "
                        "(agent_id, actor, changed_at, change_type, prior_text, new_text, "
                        "confirmation_id) VALUES "
                        "('chat_assistant', 'bob', now(), 'delete', 'old', 'new', 'CONFIRM-2')"
                    )
                )
    finally:
        await engine.dispose()

    # Downgrade cleanly removes both tables.
    _run_alembic(migration_db_url, "downgrade", "022")
    engine2 = create_async_engine(migration_db_url)
    try:
        async with engine2.begin() as conn:
            def _table_names2(sync_conn):
                return sa.inspect(sync_conn).get_table_names()

            tables_after_downgrade = await conn.run_sync(_table_names2)
        assert "agent_prompt_overrides" not in tables_after_downgrade
        assert "agent_prompt_history" not in tables_after_downgrade
    finally:
        await engine2.dispose()

    # Restore to head so a subsequent run of this fixture starts clean.
    _run_alembic(migration_db_url, "upgrade", "023")
