"""LLM-as-Judge Validation HTTP API — ADP-SPEC-008 / ADP-3ei.

Thin HTTP adapter over adp.validation.ValidationOrchestrator. This is the
first-ever HTTP wiring for the validation pipeline — previously the
orchestrator was fully implemented but only ever exercised directly in unit
tests (no route called it in production). Mirrors the create+poll+decide
shape of intake.py/recommend.py.

ART-VIII: overriding a FAIL verdict requires an explicit, non-empty
justification (the orchestrator's own long-standing contract — unchanged).
ART-IX: an override writes an audit entry to the design.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator

from adp.telemetry.context import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["validate"])


# ── Pydantic v2 request / response models ─────────────────────────────────────

class ValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    design_version: int | None = None


class FindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    critic_name: str
    severity: str
    description: str
    element_id: str | None = None
    score: float | None = None


class VerdictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict_id: str
    status: str
    composite_score: float | None
    design_version: int
    citations_present: bool
    findings: list[FindingResponse]
    overridden_by: str | None = None
    override_justification: str | None = None


class ValidateStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    design_id: str
    status: str
    verdict: VerdictResponse | None = None
    result_summary: str | None = None
    error_description: str | None = None


class OverrideVerdictRequest(BaseModel):
    """Matches ValidationOrchestrator.override_verdict's existing contract
    (justification-only) — it never required a separate confirmation token."""

    model_config = ConfigDict(extra="forbid")

    justification: str

    @field_validator("justification")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("justification must be non-empty (FR-006)")
        return v


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    """Return actor identity: authenticated user if available, else X-Actor header."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_design_store_dep():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


async def _get_op_store_dep():  # type: ignore[return]
    from adp.api.deps import get_operation_store
    return await get_operation_store()


async def _get_validation_capture():  # type: ignore[return]
    from adp.api.deps import get_validation_capture_store
    return await get_validation_capture_store()


def _resolve_validation_model(model: str | None = None) -> str:
    """Return the model id that _make_validate_orchestrator would actually use."""
    from adp.api.routers.config import get_api_key, get_validation_model

    if not get_api_key():
        return "stub"
    return model or get_validation_model()


def _make_validate_orchestrator(model: str | None = None, capture: object | None = None):
    """Create ValidationOrchestrator with stub knowledge retrieval and configured LLM.

    `capture` is the ValidationCaptureStore to use (caller resolves it via the
    _get_validation_capture FastAPI dependency, so tests can override it).
    """
    from adp.agents.llm_stub import StubLLMClient
    from adp.api.routers.config import get_api_key, get_validation_model
    from adp.api.routers.recommend import _make_stub_knowledge_retrieval
    from adp.llm.client import LLMClient
    from adp.validation.orchestrator import ValidationOrchestrator

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = get_api_key()

    if not api_key:
        llm = StubLLMClient(base_url="http://stub", api_key="stub", model="stub")  # type: ignore[assignment]
    else:
        active_model = model or get_validation_model()
        llm = LLMClient(base_url=endpoint, api_key=api_key, model=active_model)  # type: ignore[assignment]

    knowledge = _make_stub_knowledge_retrieval()
    store_dep = None  # orchestrator gets the real store injected by the caller

    return ValidationOrchestrator(
        llm=llm,
        knowledge_retrieval=knowledge,
        design_store=store_dep,  # type: ignore[arg-type]
        capture_store=capture,
    )


def _verdict_dict_to_response(v: dict[str, Any]) -> VerdictResponse:
    return VerdictResponse(
        verdict_id=v["verdict_id"],
        status=v["status"],
        composite_score=v.get("composite_score"),
        design_version=v["design_version"],
        citations_present=v.get("citations_present", False),
        findings=[
            FindingResponse(
                finding_id=f["finding_id"],
                critic_name=f["critic_name"],
                severity=f["severity"],
                description=f["description"],
                element_id=f.get("element_id"),
                score=f.get("score"),
            )
            for f in v.get("findings", [])
        ],
        overridden_by=v.get("overridden_by"),
        override_justification=v.get("override_justification"),
    )


# ── Start validation + poll status ────────────────────────────────────────────

@router.post(
    "/{design_id}/validate",
    response_model=ValidateStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_validation(
    design_id: str,
    request: ValidateRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    store=Depends(_get_design_store_dep),
    op_store=Depends(_get_op_store_dep),
    capture=Depends(_get_validation_capture),
) -> ValidateStatusResponse:
    """Start the LLM-as-Judge validation pipeline as a background task.

    Returns immediately with an operation_id for polling.
    """
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    operation_id = str(uuid.uuid4())
    correlation_id = raw_request.headers.get("X-Trace-ID", get_trace_id() or str(uuid.uuid4()))
    actor = _get_actor(raw_request)

    await op_store.create(operation_id, "validate", design_id, actor, {
        "verdict": None,
        "result_summary": None,
        "error_description": None,
        "correlation_id": correlation_id,
    })

    orchestrator = _make_validate_orchestrator(model=request.model, capture=capture)
    orchestrator._store = store  # inject the real store for the background run

    background_tasks.add_task(
        orchestrator.run,
        operation_id,
        design_id,
        op_store,
        request.design_version,
        correlation_id,
        actor,
    )

    logger.info(
        "validate.start",
        extra={
            "event": "validate.start",
            "design_id": design_id,
            "operation_id": operation_id,
            "actor": actor,
        },
    )

    return ValidateStatusResponse(
        operation_id=operation_id,
        design_id=design_id,
        status="pending",
        verdict=None,
    )


@router.get(
    "/{design_id}/validate/{operation_id}",
    response_model=ValidateStatusResponse,
)
async def get_validation_status(
    design_id: str,
    operation_id: str,
    op_store=Depends(_get_op_store_dep),
) -> ValidateStatusResponse:
    """Poll validation pipeline status and retrieve the verdict."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    verdict_data = op.get("verdict")
    verdict_response = _verdict_dict_to_response(verdict_data) if verdict_data else None

    return ValidateStatusResponse(
        operation_id=operation_id,
        design_id=op["design_id"],
        status=op["status"],
        verdict=verdict_response,
        result_summary=op.get("result_summary"),
        error_description=op.get("error_description"),
    )


# ── Override a FAIL verdict ────────────────────────────────────────────────────

@router.post(
    "/{design_id}/validate/{operation_id}/override",
    response_model=ValidateStatusResponse,
)
async def override_verdict(
    design_id: str,
    operation_id: str,
    request: OverrideVerdictRequest,
    raw_request: Request,
    store=Depends(_get_design_store_dep),
    op_store=Depends(_get_op_store_dep),
    capture=Depends(_get_validation_capture),
) -> ValidateStatusResponse:
    """Override a FAIL verdict with a recorded justification (ART-VIII / FR-006)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    actor = _get_actor(raw_request)
    orchestrator = _make_validate_orchestrator(capture=capture)
    orchestrator._store = store  # type: ignore[attr-defined]

    verdict_data = op.get("verdict") or {}
    verdict_id = verdict_data.get("verdict_id", "")

    try:
        await orchestrator.override_verdict(
            verdict_id=verdict_id,
            operation_id=operation_id,
            reviewing_actor=actor,
            justification=request.justification,
            operation_store=op_store,
            design_id=design_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    updated_op = await op_store.get(operation_id) or {}
    verdict_response = _verdict_dict_to_response(updated_op["verdict"])

    logger.info(
        "validate.override",
        extra={
            "event": "validate.override",
            "design_id": design_id,
            "operation_id": operation_id,
            "actor": actor,
        },
    )

    return ValidateStatusResponse(
        operation_id=operation_id,
        design_id=design_id,
        status=updated_op["status"],
        verdict=verdict_response,
        result_summary=updated_op.get("result_summary"),
        error_description=updated_op.get("error_description"),
    )
