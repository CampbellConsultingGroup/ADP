"""Diagrams HTTP API — ADP-SPEC-046.

Five CRUD endpoints (create/read/list/update/delete) plus one PNG-export
endpoint. Mutations require WRITE_DIAGRAM (enforced app-level via
adp.authz.enforcement's route→action prefix map); reads are ungated.

The backend never parses or validates `dsl_source` (research.md Decision 2)
-- it's opaque, size-capped text as far as this router/store is concerned.
"""

from __future__ import annotations

import logging

import cairosvg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from adp.diagrams import store as dstore
from adp.diagrams.models import (
    Diagram,
    DiagramCreate,
    DiagramListResponse,
    DiagramUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/diagrams", tags=["diagrams"])


async def _get_session():
    factory = dstore._get_session_factory()
    async with factory() as session:
        yield session


def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER

    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


# ── CRUD ───────────────────────────────────────────────────────────────────

@router.get("", response_model=DiagramListResponse)
async def list_diagrams(session: AsyncSession = Depends(_get_session)):
    return await dstore.list_diagrams(session)


@router.post("", response_model=Diagram, status_code=201)
async def create_diagram(
    body: DiagramCreate,
    request: Request,
    session: AsyncSession = Depends(_get_session),
):
    actor = _get_actor(request)
    diagram = await dstore.create_diagram(body, actor=actor, session=session)
    await session.commit()
    logger.info("diagram.create id=%s type=%s actor=%s", diagram.id, diagram.diagram_type, actor)
    return diagram


@router.get("/{diagram_id}", response_model=Diagram)
async def get_diagram(diagram_id: str, session: AsyncSession = Depends(_get_session)):
    diagram = await dstore.get_diagram(diagram_id, session)
    if diagram is None:
        raise HTTPException(status_code=404, detail=f"Diagram {diagram_id!r} not found")
    return diagram


@router.put("/{diagram_id}", response_model=Diagram)
async def update_diagram(
    diagram_id: str,
    body: DiagramUpdate,
    session: AsyncSession = Depends(_get_session),
):
    diagram = await dstore.update_diagram(diagram_id, body, session)
    if diagram is None:
        raise HTTPException(status_code=404, detail=f"Diagram {diagram_id!r} not found")
    await session.commit()
    return diagram


@router.delete("/{diagram_id}", status_code=204)
async def delete_diagram(diagram_id: str, session: AsyncSession = Depends(_get_session)):
    deleted = await dstore.delete_diagram(diagram_id, session)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Diagram {diagram_id!r} not found")
    await session.commit()


# ── Export (User Story 2, research.md Decision 3) ────────────────────────────

class DiagramExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    svg: str


@router.post("/{diagram_id}/export")
async def export_diagram_png(
    diagram_id: str,
    body: DiagramExportRequest,
    session: AsyncSession = Depends(_get_session),
):
    """Convert a client-rendered SVG string to PNG via cairosvg. Stateless
    with respect to dsl_source (contracts/diagrams-api.md) -- {diagram_id}
    exists only for the existence/permission check, not because this reads
    the diagram's stored content."""
    diagram = await dstore.get_diagram(diagram_id, session)
    if diagram is None:
        raise HTTPException(status_code=404, detail=f"Diagram {diagram_id!r} not found")

    try:
        png_bytes = cairosvg.svg2png(bytestring=body.svg.encode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid SVG: {exc}") from exc

    return Response(content=png_bytes, media_type="image/png")
