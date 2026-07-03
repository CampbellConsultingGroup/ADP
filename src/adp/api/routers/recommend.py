"""Architecture Recommendation HTTP API — ADP-SPEC-018.

Thin HTTP adapter over adp.recommendation.RecommendationOrchestrator (ADP-SPEC-007).
ART-VIII: accepting a recommendation requires explicit confirmation_id — no auto-accept.
ART-IX: every accepted option writes an audit entry.
ART-XI: created elements carry provenance = option_id.
ART-VII: advisory options require advisory_acknowledged=True before acceptance.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator

from adp.telemetry.context import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["recommend"])

# In-process operation store — same pattern as intake.
_recommend_store: dict[str, Any] = {}


# ── Pydantic v2 request / response models ─────────────────────────────────────

class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_ids: list[str]
    model: str | None = None

    @field_validator("requirement_ids")
    @classmethod
    def _require_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("requirement_ids must contain at least one requirement ID")
        return v


class TradeOffEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: str
    stance: Literal["meets", "partially_meets", "does_not_meet"]
    rationale: str


class ProposedElementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: str
    description: str | None = None
    satisfies: list[str]


class SolutionOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    rank: int
    title: str
    rationale: str
    advisory: bool
    satisfies: list[str]
    trade_offs: list[TradeOffEntryResponse]
    proposed_elements: list[ProposedElementResponse]
    grounded_on: list[str]
    ranking_score: float
    status: str


class RecommendStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    design_id: str
    status: str
    options: list[SolutionOptionResponse]
    result_summary: str | None = None
    error_description: str | None = None


class AcceptOptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_id: str
    advisory_acknowledged: bool = False

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty — accepting a recommendation is a "
                "consequential action per ART-VIII"
            )
        return v


class ElementSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str


class AcceptOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str
    elements_created: list[ElementSummaryResponse]
    audit_entry_id: str


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    return request.headers.get("X-Actor", "architect")


async def _get_design_store_dep():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


def _make_stub_knowledge_retrieval():
    """Return a no-op KnowledgeRetrieval when pgvector is not indexed.

    The stub's hybrid_search() returns [], causing all generated options to be
    marked advisory=True. This is the correct behaviour for an empty knowledge base.
    """
    from adp.knowledge.retrieval import KnowledgeRetrieval

    class _StubKnowledgeRetrieval(KnowledgeRetrieval):
        async def hybrid_search(self, *args: Any, **kwargs: Any) -> list:  # type: ignore[override]
            return []

        async def relationship_query(self, *args: Any, **kwargs: Any) -> list:  # type: ignore[override]
            return []

        async def resolve_citation(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            return None

    return _StubKnowledgeRetrieval.__new__(_StubKnowledgeRetrieval)


def _make_recommend_orchestrator(model: str | None = None):
    """Create RecommendationOrchestrator with stub knowledge retrieval and configured LLM."""
    from adp.api.routers.config import get_recommendation_model
    from adp.intake.llm import LLMClient
    from adp.recommendation.orchestrator import RecommendationOrchestrator

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = os.environ.get("ADP_LLM_API_KEY", "")

    if not api_key:
        class _StubLLMClient(LLMClient):
            async def extract(self, text: str, correlation_id: str | None = None) -> dict:  # type: ignore[override]
                return {"choices": [], "usage": {}}

        llm = _StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    else:
        active_model = model or get_recommendation_model()
        llm = LLMClient(base_url=endpoint, api_key=api_key, model=active_model)

    knowledge = _make_stub_knowledge_retrieval()
    store_dep = None  # orchestrator gets store via operation args
    return RecommendationOrchestrator(
        llm=llm,
        knowledge_retrieval=knowledge,
        design_store=store_dep,  # type: ignore[arg-type]
    )


def _map_option_to_response(opt: Any) -> SolutionOptionResponse:
    """Convert SolutionOption dataclass → SolutionOptionResponse Pydantic model."""
    return SolutionOptionResponse(
        option_id=opt.option_id,
        rank=opt.rank,
        title=opt.title,
        rationale=opt.rationale,
        advisory=opt.advisory,
        satisfies=list(opt.satisfies or []),
        trade_offs=[
            TradeOffEntryResponse(
                criterion=tf.criterion,
                stance=tf.stance.value if hasattr(tf.stance, "value") else str(tf.stance),
                rationale=tf.rationale,
            )
            for tf in (opt.trade_offs or [])
        ],
        proposed_elements=[
            ProposedElementResponse(
                name=pe.name,
                kind=pe.kind.value if hasattr(pe.kind, "value") else str(pe.kind),
                description=pe.description,
                satisfies=list(pe.satisfies or []),
            )
            for pe in (opt.proposed_elements or [])
        ],
        grounded_on=[
            ref.item_id if hasattr(ref, "item_id") else str(ref)
            for ref in (opt.grounded_on or [])
        ],
        ranking_score=float(opt.ranking_score or 0.0),
        status=str(opt.status or "pending"),
    )


# ── US1: Submit recommendation request + poll status ─────────────────────────

@router.post(
    "/{design_id}/recommend",
    response_model=RecommendStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_recommendation(
    design_id: str,
    request: RecommendRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    store=Depends(_get_design_store_dep),
) -> RecommendStatusResponse:
    """Start the 5-step recommendation pipeline as a background task (FR-001).

    Returns immediately with operation_id for polling.
    ART-VIII: no recommendation is auto-accepted; explicit accept endpoint required.
    """
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    operation_id = str(uuid.uuid4())
    correlation_id = raw_request.headers.get("X-Trace-ID", get_trace_id() or str(uuid.uuid4()))
    actor = _get_actor(raw_request)

    _recommend_store[operation_id] = {
        "status": "pending",
        "design_id": design_id,
        "requirement_ids": request.requirement_ids,
        "options": {},
        "result_summary": None,
        "error_description": None,
        "correlation_id": correlation_id,
        "created_at": datetime.now(timezone.utc),
    }

    orchestrator = _make_recommend_orchestrator(model=request.model)
    orchestrator._store = store  # inject the real store for the background run

    background_tasks.add_task(
        orchestrator.run,
        operation_id,
        design_id,
        request.requirement_ids,
        _recommend_store,
        correlation_id,
    )

    logger.info(
        "recommend.start",
        extra={
            "event": "recommend.start",
            "design_id": design_id,
            "operation_id": operation_id,
            "requirement_count": len(request.requirement_ids),
            "actor": actor,
        },
    )

    return RecommendStatusResponse(
        operation_id=operation_id,
        design_id=design_id,
        status="pending",
        options=[],
    )


@router.get(
    "/{design_id}/recommend/{operation_id}",
    response_model=RecommendStatusResponse,
)
async def get_recommendation_status(
    design_id: str,
    operation_id: str,
) -> RecommendStatusResponse:
    """Poll recommendation pipeline status and retrieve ranked options (FR-002)."""
    op = _recommend_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    options_dict: dict[str, Any] = op.get("options", {})
    options = sorted(
        [_map_option_to_response(opt) for opt in options_dict.values()],
        key=lambda o: o.rank,
    )

    return RecommendStatusResponse(
        operation_id=operation_id,
        design_id=op["design_id"],
        status=op["status"],
        options=options,
        result_summary=op.get("result_summary"),
        error_description=op.get("error_description"),
    )


# ── US2: Accept one option ─────────────────────────────────────────────────────

@router.post(
    "/{design_id}/recommend/{operation_id}/options/{option_id}/accept",
    response_model=AcceptOptionResponse,
)
async def accept_option(
    design_id: str,
    operation_id: str,
    option_id: str,
    request: AcceptOptionRequest,
    raw_request: Request,
    store=Depends(_get_design_store_dep),
) -> AcceptOptionResponse:
    """Accept one option — materialises proposed elements into the canonical design.

    ART-VIII: requires non-empty confirmation_id (validated by Pydantic).
    ART-VII: advisory options require advisory_acknowledged=True.
    ART-IX: writes audit entry.
    ART-XI: created elements carry provenance = option_id.
    """
    op = _recommend_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    options_dict: dict[str, Any] = op.get("options", {})
    option = options_dict.get(option_id)
    if option is None:
        raise HTTPException(status_code=404, detail=f"Option {option_id!r} not found")

    if option.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Option {option_id!r} has already been actioned (status={option.status})",
        )

    if option.advisory and not request.advisory_acknowledged:
        raise HTTPException(
            status_code=422,
            detail=(
                "advisory option requires advisory_acknowledged=true — "
                "this option lacks full knowledge-base grounding (ART-VII)"
            ),
        )

    actor = _get_actor(raw_request)
    orchestrator = _make_recommend_orchestrator()
    orchestrator._store = store  # type: ignore[attr-defined]

    try:
        created_elements = await orchestrator.materialize_option(
            option_id=option_id,
            operation_id=operation_id,
            accepting_actor=actor,
            operation_store=_recommend_store,
            design_id=design_id,
            advisory_acknowledged=request.advisory_acknowledged,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Get the audit entry ID that materialize_option wrote
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]
    try:
        design = await store.get(design_id)
        audit_entry_id = design.audit_log[-1].id if design.audit_log else "AUD-000"
    except DesignNotFoundError:
        audit_entry_id = "AUD-000"

    logger.info(
        "recommend.accepted",
        extra={
            "event": "recommend.accepted",
            "design_id": design_id,
            "option_id": option_id,
            "elements_created": len(created_elements),
            "actor": actor,
        },
    )

    return AcceptOptionResponse(
        option_id=option_id,
        elements_created=[
            ElementSummaryResponse(id=el.id, name=el.name, kind=str(el.kind))
            for el in created_elements
        ],
        audit_entry_id=audit_entry_id,
    )
