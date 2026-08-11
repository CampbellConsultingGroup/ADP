"""Diagrams store — async SQLAlchemy CRUD (ADP-SPEC-046).

Persists diagram metadata + opaque DSL source via migration 024. All
functions accept an AsyncSession and are called from the router inside
`async with session_factory() as session: ...` blocks, mirroring every
other domain store in this codebase (adp.business.store, adp.chat.store).

The backend never parses or validates `dsl_source` (research.md Decision
2) -- it's an opaque, size-capped text blob (enforced at the Pydantic
layer, models.py) as far as this store is concerned.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adp.diagrams.models import (
    Diagram,
    DiagramCreate,
    DiagramListResponse,
    DiagramSummary,
    DiagramUpdate,
)

_metadata = sa.MetaData()

_diagrams = sa.Table(
    "diagrams",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("title", sa.String(255), nullable=False),
    sa.Column("diagram_type", sa.Text(), nullable=False),
    sa.Column("dsl_source", sa.Text(), nullable=False, server_default=""),
    sa.Column("created_by", sa.String(255), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


# ── Module-level session factory (set by deps or tests) ──────────────────────

_engine: Any = None
_session_factory: Any = None


def _get_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        db_url = os.environ.get(
            "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
        )
        _engine = create_async_engine(db_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def get_session() -> AsyncSession:
    return _get_session_factory()()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rowcount(result: Any) -> int:
    """DML executes return CursorResult at runtime; session.execute is typed
    as Result[Any], which lacks rowcount."""
    return cast("sa.CursorResult[Any]", result).rowcount


def _row_to_diagram(row: Any) -> Diagram:
    return Diagram(
        id=row.id,
        title=row.title,
        diagram_type=row.diagram_type,
        dsl_source=row.dsl_source,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _row_to_summary(row: Any) -> DiagramSummary:
    return DiagramSummary(
        id=row.id, title=row.title, diagram_type=row.diagram_type, updated_at=row.updated_at
    )


async def create_diagram(
    body: DiagramCreate, actor: str | None, session: AsyncSession
) -> Diagram:
    now = _now()
    diagram_id = str(uuid.uuid4())
    await session.execute(
        _diagrams.insert().values(
            id=diagram_id,
            title=body.title,
            diagram_type=body.diagram_type,
            dsl_source=body.dsl_source,
            created_by=actor,
            created_at=now,
            updated_at=now,
        )
    )
    diagram = await get_diagram(diagram_id, session)
    assert diagram is not None  # just inserted
    return diagram


async def get_diagram(diagram_id: str, session: AsyncSession) -> Diagram | None:
    result = await session.execute(
        sa.select(_diagrams).where(_diagrams.c.id == diagram_id)
    )
    row = result.mappings().first()
    return _row_to_diagram(row) if row else None


async def list_diagrams(session: AsyncSession) -> DiagramListResponse:
    result = await session.execute(sa.select(_diagrams).order_by(_diagrams.c.updated_at.desc()))
    items = [_row_to_summary(row) for row in result.mappings().all()]
    return DiagramListResponse(items=items, total=len(items))


async def update_diagram(
    diagram_id: str, body: DiagramUpdate, session: AsyncSession
) -> Diagram | None:
    values: dict[str, Any] = {}
    if body.title is not None:
        values["title"] = body.title
    if body.dsl_source is not None:
        values["dsl_source"] = body.dsl_source
    if not values:
        return await get_diagram(diagram_id, session)

    values["updated_at"] = _now()
    result = await session.execute(
        _diagrams.update().where(_diagrams.c.id == diagram_id).values(**values)
    )
    if _rowcount(result) == 0:
        return None
    return await get_diagram(diagram_id, session)


async def delete_diagram(diagram_id: str, session: AsyncSession) -> bool:
    result = await session.execute(_diagrams.delete().where(_diagrams.c.id == diagram_id))
    return _rowcount(result) > 0
