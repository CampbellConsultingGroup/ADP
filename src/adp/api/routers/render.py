"""Render router — POST /api/v1/designs/{design_id}/render.

ART-VI / QG-10: every render request emits a structured log entry.
ART-XII / FR-002: RenderRequest.extra="forbid" — no style override fields accepted;
any unknown field causes 422 before the renderer is called.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from adp.renderer.orchestrator import RenderOrchestrator
from adp.theme.models import RenderRequest, RenderResult, ThemeValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["render"])


async def get_render_orchestrator() -> RenderOrchestrator:
    """Dependency — overridable in tests via app.dependency_overrides."""
    from adp.api.deps import get_design_store

    store = await get_design_store()
    return RenderOrchestrator(design_store=store)


@router.post(
    "/{design_id}/render",
    response_model=RenderResult,
    status_code=status.HTTP_200_OK,
)
async def render_design(
    design_id: str,
    request: RenderRequest,
    raw_request: Request,
    orchestrator: RenderOrchestrator = Depends(get_render_orchestrator),
) -> RenderResult:
    """Render a design to Structurizr DSL + SVG + PNG at the given C4 level.

    Styling is applied exclusively from the locked theme (ART-XII).
    No per-element or per-diagram style overrides are accepted (FR-002).
    """
    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    # ART-VI / QG-10: structured log at request entry
    logger.info(
        "render.start",
        extra={
            "event": "render.start",
            "design_id": design_id,
            "level": request.level,
            "correlation_id": correlation_id,
        },
    )

    try:
        result = orchestrator.render(design_id, request.level)
    except ThemeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Theme validation failed: {exc}",
        ) from exc
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Design {design_id!r} not found",
        )

    logger.info(
        "render.complete",
        extra={
            "event": "render.complete",
            "design_id": design_id,
            "level": request.level,
            "correlation_id": correlation_id,
            "dsl_len": len(result.dsl),
            "svg_len": len(result.svg),
        },
    )

    return result
