"""Integration test: migration 022 (chat_conversations/chat_messages) applies
and reverts cleanly, and enforces the FK/cascade it declares (ADP-SPEC-041).

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


def _docker_available() -> bool:
    import shutil
    return shutil.which("docker") is not None


if not _docker_available():
    collect_ignore_glob = ["test_migration_022.py"]


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


async def test_migration_022_upgrade_creates_tables_with_cascade(migration_db_url):
    _run_alembic(migration_db_url, "upgrade", "021")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migration_db_url)
    try:
        _run_alembic(migration_db_url, "upgrade", "022")

        async with engine.begin() as conn:
            def _table_names(sync_conn):
                return sa.inspect(sync_conn).get_table_names()

            tables = await conn.run_sync(_table_names)
            assert "chat_conversations" in tables
            assert "chat_messages" in tables

            await conn.execute(
                sa.text(
                    "INSERT INTO chat_conversations (id, actor, title, created_at, updated_at) "
                    "VALUES ('C-1', 'alice', 'Test', now(), now())"
                )
            )
            await conn.execute(
                sa.text(
                    "INSERT INTO chat_messages "
                    "(id, conversation_id, role, content, citations, created_at) "
                    "VALUES ('M-1', 'C-1', 'user', 'hi', '[]', now())"
                )
            )

            # ON DELETE CASCADE: deleting the conversation removes its messages.
            await conn.execute(sa.text("DELETE FROM chat_conversations WHERE id = 'C-1'"))
            remaining = await conn.execute(
                sa.text("SELECT COUNT(*) FROM chat_messages WHERE conversation_id = 'C-1'")
            )
            assert remaining.scalar_one() == 0
    finally:
        await engine.dispose()

    # Downgrade cleanly removes both tables.
    _run_alembic(migration_db_url, "downgrade", "021")
    engine2 = create_async_engine(migration_db_url)
    try:
        async with engine2.begin() as conn:
            def _table_names2(sync_conn):
                return sa.inspect(sync_conn).get_table_names()

            tables_after_downgrade = await conn.run_sync(_table_names2)
        assert "chat_conversations" not in tables_after_downgrade
        assert "chat_messages" not in tables_after_downgrade
    finally:
        await engine2.dispose()

    # Restore to head so a subsequent run of this fixture starts clean.
    _run_alembic(migration_db_url, "upgrade", "022")
