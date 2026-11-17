"""ADP-blp.26: the stores' duplicate table declarations must agree, and one helper can create
the whole schema for a test."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from tests.support import schema


def test_mirrors_agree_with_the_owning_declaration():
    """A store's narrow copy of another store's table may leave columns out, but every column
    it does declare must exist, with the same kind of type, in the widest declaration."""
    assert schema.find_drift() == []


def test_duplicate_declarations_are_known():
    """If this number grows, a new mirror was added: prefer reading through the owner."""
    duplicated = {name for name, tables in schema.declarations().items() if len(tables) > 1}
    assert len(duplicated) <= 27, sorted(duplicated)


async def test_create_schema_builds_every_store_table_once(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/all.db")
    async with engine.begin() as conn:
        await conn.run_sync(schema.create_schema)
        await conn.run_sync(schema.create_schema)  # idempotent
        names = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
        columns = await conn.run_sync(
            lambda c: {col["name"] for col in sa.inspect(c).get_columns("business_capabilities")}
        )
    await engine.dispose()
    assert set(schema.declarations()) <= names
    # Built from the owner's declaration, not a narrow mirror.
    assert {"id", "name", "level", "parent_id", "position", "maturity_level"} <= columns
