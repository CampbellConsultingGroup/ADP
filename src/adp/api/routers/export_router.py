"""Export and import endpoints — ADP-SPEC-011.

POST /api/v1/designs/{id}/export — ART-VIII gated; writes durable export bundle.
POST /api/v1/designs/import — re-imports a canonical model.json.
"""

from __future__ import annotations

import logging
import os
import uuid

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request, status

from adp.export.bundle import ExportOrchestrator
from adp.export.importer import DesignImporter
from adp.export.models import ExportRequest, ExportResult, ImportRequest, ImportResult

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

# ADP-izw: the destination is an operator-configured setting, not client
# input -- see ExportRequest's own docstring for why. Read fresh per request
# (not module-scope) so a test can monkeypatch the env var without reloading
# this module, matching adp.api.app's own ADP_BUSINESS_ARCH_EXPORT_ROOT
# precedent for the sibling export features.
_EXPORT_ROOT_ENV_VAR = "ADP_DESIGN_EXPORT_ROOT"

# Authorization for this route is enforced centrally, not here: the
# app-level `enforce_route_permission` dependency (adp.authz.enforcement,
# installed on the FastAPI app itself in adp.api.app.create_app) maps
# POST /api/v1/designs/{design_id}/export to ActionType.EXPORT_DESIGN,
# which only Solution/Enterprise Architect and Platform Admin hold
# (adp.authz.permissions.PERMISSION_GRANTS) -- confirmed live via
# tests/authz/test_enforcement.py::test_reviewer_denied_export. A prior,
# unused local `_EXPORT_ROLES` constant here (dead code, superseded by the
# above mechanism, never actually wired to anything) was removed as part
# of ADP-izw to stop it misleadingly suggesting this route was unprotected.


async def get_design_store():  # type: ignore[return]
    """Dependency — overridable in tests."""
    from adp.api.deps import get_design_store as _get

    return await _get()


def _get_actor(request: Request) -> str:
    return request.headers.get("X-Actor", "unknown")


@router.post(
    "/api/v1/designs/{design_id}/export",
    response_model=ExportResult,
    status_code=status.HTTP_200_OK,
)
async def export_design(
    design_id: str,
    request: ExportRequest,
    raw_request: Request,
    store=Depends(get_design_store),
) -> ExportResult:
    """Write a complete, validated export bundle to the configured VCS path.

    ART-VIII: ExportRequest.confirmation_id must be non-empty (validated by Pydantic).
    ART-IX: audit entry is written into the exported model.json.
    ART-VI: structured log emitted at start and completion (inside ExportOrchestrator).

    The destination is ADP_DESIGN_EXPORT_ROOT (operator-configured, not
    client-supplied — ADP-izw). A 503 is returned rather than silently
    no-op'ing when it's unset: unlike the background reconciliation
    features that share this "unset disables the feature" convention, this
    is a synchronous, user-triggered action expecting a concrete result,
    so silence would just look like a hang or a swallowed failure.
    """
    export_root = os.environ.get(_EXPORT_ROOT_ENV_VAR)
    if not export_root:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Design export is not configured — set {_EXPORT_ROOT_ENV_VAR}.",
        )

    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    actor = _get_actor(raw_request)

    logger.info(
        "export.request",
        extra={
            "event": "export.request",
            "design_id": design_id,
            "export_root": export_root,
            "confirmation_id": request.confirmation_id,
            "correlation_id": correlation_id,
            "actor": actor,
        },
    )

    try:
        orchestrator = ExportOrchestrator(design_store=store)
        result = orchestrator.export(
            design_id=design_id,
            export_root=export_root,
            confirmation_id=request.confirmation_id,
            actor=actor,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Design {design_id!r} not found",
        )
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Export failed: {exc}",
        )

    return result


@router.post(
    "/api/v1/designs/import",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
)
async def import_design(
    request: ImportRequest,
    raw_request: Request,
) -> ImportResult:
    """Re-import an exported canonical model JSON and validate it (FR-007)."""
    correlation_id = raw_request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    logger.info("import.start", extra={"event": "import.start", "correlation_id": correlation_id})

    try:
        design = DesignImporter().import_from_json(request.model_json)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except pydantic.ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema validation failed: {exc}",
        )

    return ImportResult(
        design_id=design.id,
        schema_version=design.schema_version,
        element_count=len(design.elements),
        relationship_count=len(design.relationships),
        validation_warnings=[],
    )
