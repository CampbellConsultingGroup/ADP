"""Document, traceability, and view endpoints — ADP-SPEC-011.

All endpoints are read-only projections from the canonical model (ART-II).
No side effects; no confirmation required; available to all authenticated roles.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from adp.docs.generator import DocumentGenerator
from adp.docs.models import TraceabilityMatrix, ViewBundle
from adp.docs.traceability import TraceabilityGenerator
from adp.renderer.orchestrator import RenderOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["documents"])


async def get_design_store():  # type: ignore[return]
    """Dependency — overridable in tests."""
    from adp.store.store import DesignStore  # type: ignore[attr-defined]

    return DesignStore()


async def get_render_orchestrator() -> RenderOrchestrator:
    """Dependency — overridable in tests."""
    store = await get_design_store()
    return RenderOrchestrator(design_store=store)


def _get_design_or_404(design_id: str, store):  # type: ignore[return]
    design = store.get(design_id)
    if design is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Design {design_id!r} not found",
        )
    return design


@router.get("/{design_id}/document", response_class=PlainTextResponse)
async def get_document(
    design_id: str,
    raw_request: Request,
    store=Depends(get_design_store),
) -> PlainTextResponse:
    """Generate and return a stakeholder Markdown document for the design (ART-II / FR-001)."""
    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    logger.info(
        "document.start",
        extra={"event": "document.start", "design_id": design_id, "correlation_id": correlation_id},
    )
    design = _get_design_or_404(design_id, store)
    doc = DocumentGenerator().generate(design)
    return PlainTextResponse(doc.markdown, media_type="text/markdown; charset=utf-8")


@router.get("/{design_id}/traceability", response_model=TraceabilityMatrix)
async def get_traceability(
    design_id: str,
    raw_request: Request,
    store=Depends(get_design_store),
) -> TraceabilityMatrix:
    """Generate and return the requirements traceability matrix (FR-003 / ART-XI)."""
    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    logger.info(
        "traceability.start",
        extra={
            "event": "traceability.start",
            "design_id": design_id,
            "correlation_id": correlation_id,
        },
    )
    design = _get_design_or_404(design_id, store)
    return TraceabilityGenerator().generate(design)


@router.get("/{design_id}/views", response_model=ViewBundle)
async def get_views(
    design_id: str,
    raw_request: Request,
    store=Depends(get_design_store),
    orchestrator: RenderOrchestrator = Depends(get_render_orchestrator),
) -> ViewBundle:
    """Return all three C4 level renders for the design from a single model (FR-002 / US2)."""
    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    logger.info(
        "views.start",
        extra={"event": "views.start", "design_id": design_id, "correlation_id": correlation_id},
    )
    _get_design_or_404(design_id, store)

    context = orchestrator.render(design_id, "context")
    container = orchestrator.render(design_id, "container")
    component = orchestrator.render(design_id, "component")

    return ViewBundle(
        design_id=design_id, context=context, container=container, component=component
    )
