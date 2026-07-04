"""SQLAlchemy ORM table definitions and KnowledgeIndex database operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, Float, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from adp.knowledge.schema import KnowledgeItem, KnowledgeRelationship

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

metadata = sa.MetaData()

knowledge_items = sa.Table(
    "knowledge_items",
    metadata,
    Column("id", String, primary_key=True),
    Column("version", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("full_text", Text, nullable=False),
    Column("metadata", JSONB, nullable=False, default={}),
    Column("source_ref", Text, nullable=False),
    Column("schema_version", Text, nullable=False, default="1.0.0"),
    Column("active", Boolean, nullable=False, default=True),
    Column("embedding", Vector(384), nullable=False),
    Column("indexed_at", DateTime(timezone=True), nullable=False),
)

knowledge_relationships = sa.Table(
    "knowledge_relationships",
    metadata,
    Column("id", String, primary_key=True),
    Column("source_id", String, nullable=False),
    Column("target_id", String, nullable=False),
    Column("relationship_type", Text, nullable=False),
    Column("weight", Float, nullable=False, default=1.0),
    Index("ix_kr_source_type", "source_id", "relationship_type"),
)


class KnowledgeIndex:
    """Low-level async database operations for the knowledge index."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def upsert_item(
        self,
        item: KnowledgeItem,
        embedding: list[float],
        session: "AsyncSession",
    ) -> None:
        """Insert or update a knowledge item with its embedding."""
        now = datetime.now(timezone.utc)
        values = {
            "id": item.id,
            "version": item.version,
            "kind": item.kind.value,
            "title": item.title,
            "full_text": item.full_text,
            "metadata": item.metadata,
            "source_ref": item.source_ref,
            "schema_version": item.schema_version,
            "active": True,
            "embedding": embedding,
            "indexed_at": now,
        }
        stmt = sa.dialects.postgresql.insert(knowledge_items).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={k: v for k, v in values.items() if k != "id"},
        )
        await session.execute(stmt)

    async def get_item(
        self,
        item_id: str,
        version: str | None,
        session: "AsyncSession",
        *,
        include_inactive: bool = False,
    ) -> KnowledgeItem | None:
        """Retrieve an item by id (and optionally version).

        include_inactive=True allows resolving citations for deactivated old versions.
        """
        q = sa.select(knowledge_items).where(knowledge_items.c.id == item_id)
        if version is not None:
            q = q.where(knowledge_items.c.version == version)
        if not include_inactive:
            q = q.where(knowledge_items.c.active.is_(True))
        q = q.order_by(knowledge_items.c.indexed_at.desc()).limit(1)

        row = (await session.execute(q)).fetchone()
        if row is None:
            return None

        return KnowledgeItem(
            id=row.id,
            version=row.version,
            kind=row.kind,
            title=row.title,
            full_text=row.full_text,
            metadata=row.metadata or {},
            source_ref=row.source_ref,
            schema_version=row.schema_version,
            active=row.active,
            embedding=[],  # embeddings not returned to callers
            indexed_at=row.indexed_at,
        )

    async def get_all_active_ids(self, session: "AsyncSession") -> set[str]:
        """Return all ids where active=TRUE; used by Indexer to find deactivation candidates."""
        rows = await session.execute(
            sa.select(knowledge_items.c.id).where(knowledge_items.c.active.is_(True))
        )
        return {row.id for row in rows}

    async def mark_inactive(
        self, item_ids: list[str], session: "AsyncSession"
    ) -> int:
        """Mark items not present in the latest canonical index run as inactive."""
        if not item_ids:
            return 0
        result: Any = await session.execute(
            knowledge_items.update()
            .where(knowledge_items.c.id.in_(item_ids))
            .values(active=False)
        )
        return int(result.rowcount)

    async def upsert_relationship(
        self,
        rel: KnowledgeRelationship,
        session: "AsyncSession",
    ) -> None:
        """Insert or update a typed relationship between two knowledge items."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(knowledge_relationships).values(
            id=rel.id,
            source_id=rel.source_id,
            target_id=rel.target_id,
            relationship_type=rel.relationship_type,
            weight=rel.weight,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={"weight": rel.weight},
        )
        await session.execute(stmt)
