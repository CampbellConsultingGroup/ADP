"""Architecture Recommendation HTTP API — ADP-SPEC-018/019.

Thin HTTP adapter over adp.recommendation.RecommendationOrchestrator (ADP-SPEC-007).
ART-VIII: accepting a recommendation requires explicit confirmation_id — no auto-accept.
ART-IX: every accepted option writes an audit entry.
ART-XI: created elements carry provenance = option_id.
ART-VII: advisory options require advisory_acknowledged=True before acceptance.
ADP-SPEC-019: accept/reject decisions written to knowledge base (fire-and-forget).
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator

from adp.telemetry.context import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["recommend"])


# ── SolutionOption serialization helpers (ADP-SPEC-024) ──────────────────────

def _option_to_dict(opt: Any) -> dict:
    """Serialize a SolutionOption dataclass to a JSON-safe dict."""
    return {
        "option_id": opt.option_id,
        "operation_id": opt.operation_id,
        "rank": opt.rank,
        "title": opt.title,
        "rationale": opt.rationale,
        "advisory": opt.advisory,
        "grounded_on": [
            {"item_id": r.item_id, "item_version": r.item_version}
            for r in (opt.grounded_on or [])
        ],
        "satisfies": list(opt.satisfies or []),
        "trade_offs": [
            {
                "criterion": t.criterion,
                "stance": str(t.stance.value) if hasattr(t.stance, "value") else str(t.stance),  # type: ignore[arg-type]
                "rationale": t.rationale,
            }
            for t in (opt.trade_offs or [])
        ],
        "proposed_elements": [
            {
                "name": e.name,
                "kind": e.kind.value if hasattr(e.kind, "value") else str(e.kind),
                "description": e.description,
                "satisfies": list(e.satisfies or []),
            }
            for e in (opt.proposed_elements or [])
        ],
        "ranking_score": opt.ranking_score,
        "coverage_score": getattr(opt, "coverage_score", 0.0),
        "principle_score": getattr(opt, "principle_score", 0.0),
        "tradeoff_score": getattr(opt, "tradeoff_score", 0.0),
        "status": opt.status,
        "accepted_by": getattr(opt, "accepted_by", None),
        "accepted_at": (
            getattr(opt, "accepted_at", None).isoformat()  # type: ignore[union-attr]
            if getattr(opt, "accepted_at", None) else None
        ),
        "knowledge_source": getattr(opt, "knowledge_source", "knowledge_base"),
    }


def _dict_to_option(d: dict) -> Any:
    """Reconstruct a SolutionOption dataclass from a stored dict."""
    from datetime import datetime as _dt

    from adp.knowledge.schema import CitationRef
    from adp.models import ElementKind
    from adp.recommendation.models import (
        ProposedElement,
        SolutionOption,
        TradeOffEntry,
        TradeOffStance,
    )

    accepted_at = None
    if d.get("accepted_at"):
        accepted_at = _dt.fromisoformat(d["accepted_at"])

    opt = SolutionOption(
        option_id=d["option_id"],
        operation_id=d["operation_id"],
        rank=d.get("rank", 0),
        title=d.get("title", ""),
        rationale=d.get("rationale", ""),
        advisory=d.get("advisory", False),
        grounded_on=[
            CitationRef(item_id=r["item_id"], item_version=r["item_version"])
            for r in d.get("grounded_on", [])
        ],
        satisfies=d.get("satisfies", []),
        trade_offs=[
            TradeOffEntry(
                criterion=t["criterion"],
                stance=TradeOffStance(t["stance"]),
                rationale=t["rationale"],
            )
            for t in d.get("trade_offs", [])
        ],
        proposed_elements=[
            ProposedElement(
                name=e["name"],
                kind=ElementKind(e["kind"]),
                description=e.get("description"),
                satisfies=e.get("satisfies", []),
            )
            for e in d.get("proposed_elements", [])
        ],
        ranking_score=d.get("ranking_score", 0.0),
        coverage_score=d.get("coverage_score", 0.0),
        principle_score=d.get("principle_score", 0.0),
        tradeoff_score=d.get("tradeoff_score", 0.0),
        status=d.get("status", "pending"),
        accepted_by=d.get("accepted_by"),
        accepted_at=accepted_at,
        knowledge_source=d.get("knowledge_source", "knowledge_base"),
    )
    return opt


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
    # ADP-SPEC-019: "knowledge_base" or "requirements_only"
    knowledge_source: str = "knowledge_base"


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
    # ADP-SPEC-019: optional reason stored in knowledge base
    acceptance_reason: str | None = None

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


class RejectOptionRequest(BaseModel):
    """ADP-SPEC-019: rejection requires a reason so it can inform the knowledge base."""

    model_config = ConfigDict(extra="forbid")

    rejection_reason: str

    @field_validator("rejection_reason")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "rejection_reason must be non-empty — a reason helps future recommendations learn"
            )
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
    from adp.llm.client import LLMClient
    from adp.recommendation.orchestrator import RecommendationOrchestrator

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = os.environ.get("ADP_LLM_API_KEY", "")

    if not api_key:
        class _StubLLMClient(LLMClient):
            async def extract(self, text: str, correlation_id: str | None = None) -> dict:  # type: ignore[override]
                return {"choices": [], "usage": {}}

            async def chat(  # type: ignore[override]
                self, system: str, user: str, correlation_id: str | None = None
            ) -> dict:
                return {"choices": [], "usage": {}}

        llm = _StubLLMClient(base_url="http://stub", api_key="stub", model="stub")  # type: ignore[assignment]
    else:
        active_model = model or get_recommendation_model()
        llm = LLMClient(base_url=endpoint, api_key=api_key, model=active_model)  # type: ignore[assignment]

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
                stance=tf.stance.value if hasattr(tf.stance, "value") else str(tf.stance),  # type: ignore[arg-type]
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
        knowledge_source=getattr(opt, "knowledge_source", "knowledge_base"),
    )


async def _write_knowledge_item(
    item_id: str,
    title: str,
    full_text: str,
    metadata: dict,
    store: Any,
) -> None:
    """Fire-and-forget write of a decision knowledge item (ADP-SPEC-019 FR-005/FR-006).

    Uses zero-vector placeholder embedding — real embeddings generated on next adp-reindex.
    Silently swallows all exceptions (KB write must never block the HTTP response).
    """
    try:
        from adp.knowledge.index import KnowledgeIndex
        from adp.knowledge.schema import KnowledgeItem
        from adp.knowledge.schema import KnowledgeType as KnowledgeItemKind

        item = KnowledgeItem(
            id=item_id,
            version="1.0.0",
            kind=KnowledgeItemKind.PRINCIPLE,  # closest kind for decisions
            title=title,
            full_text=full_text,
            metadata=metadata,
            source_ref="adp:recommendation-decision",
            schema_version="1.0.0",
        )
        zero_embedding = [0.0] * 384  # matches vector(384) column; adp-reindex upgrades

        from adp.store.store import DesignStore  # type: ignore[attr-defined]
        if isinstance(store, DesignStore):
            async with store._session_factory() as session:
                idx = KnowledgeIndex(session_factory=None)  # type: ignore[arg-type]
                await idx.upsert_item(item, zero_embedding, session)
        # If store is not a real DesignStore (test mock), skip silently
    except Exception as exc:
        logger.warning("KB write skipped: %s", exc)


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
    op_store=Depends(_get_op_store_dep),
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

    await op_store.create(operation_id, "recommend", design_id, actor, {
        "requirement_ids": request.requirement_ids,
        "options": {},
        "result_summary": None,
        "error_description": None,
        "correlation_id": correlation_id,
    })

    orchestrator = _make_recommend_orchestrator(model=request.model)
    orchestrator._store = store  # inject the real store for the background run

    background_tasks.add_task(
        orchestrator.run,
        operation_id,
        design_id,
        request.requirement_ids,
        op_store,
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
    op_store=Depends(_get_op_store_dep),
) -> RecommendStatusResponse:
    """Poll recommendation pipeline status and retrieve ranked options (FR-002)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    options_dict: dict[str, Any] = op.get("options", {})
    # Reconstruct SolutionOption from stored dicts (ADP-SPEC-024)
    recons = [_dict_to_option(v) if isinstance(v, dict) else v for v in options_dict.values()]
    options = sorted(
        [_map_option_to_response(opt) for opt in recons],
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
    op_store=Depends(_get_op_store_dep),
) -> AcceptOptionResponse:
    """Accept one option — materialises proposed elements into the canonical design.

    ART-VIII: requires non-empty confirmation_id (validated by Pydantic).
    ART-VII: advisory options require advisory_acknowledged=True.
    ART-IX: writes audit entry.
    ART-XI: created elements carry provenance = option_id.
    """
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    options_dict: dict[str, Any] = op.get("options", {})
    option_raw = options_dict.get(option_id)
    if option_raw is None:
        raise HTTPException(status_code=404, detail=f"Option {option_id!r} not found")

    # Reconstruct SolutionOption from stored dict (ADP-SPEC-024)
    option = _dict_to_option(option_raw) if isinstance(option_raw, dict) else option_raw

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
            operation_store=op_store,
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

    # ADP-SPEC-019 FR-005: write accepted option to knowledge base (fire-and-forget)
    reason = request.acceptance_reason or "Accepted by architect"
    elements_str = ", ".join(
        f"{pe.name} ({pe.kind.value if hasattr(pe.kind, 'value') else pe.kind})"
        for pe in (option.proposed_elements or [])
    )
    import asyncio
    asyncio.create_task(_write_knowledge_item(
        item_id=f"rec-accept-{option_id}",
        title=f"[Accepted] {option.title}",
        full_text=(
            f"{option.rationale}\n\nElements: {elements_str}\n"
            f"Acceptance reason: {reason}"
        ),
        metadata={
            "item_type": "accepted_recommendation",
            "option_id": option_id,
            "satisfies": list(option.satisfies or []),
            "reason": reason,
            "design_id": design_id,
        },
        store=store,
    ))

    return AcceptOptionResponse(
        option_id=option_id,
        elements_created=[
            ElementSummaryResponse(id=el.id, name=el.name, kind=str(el.kind))
            for el in created_elements
        ],
        audit_entry_id=audit_entry_id,
    )


@router.post(
    "/{design_id}/recommend/{operation_id}/options/{option_id}/reject",
    status_code=status.HTTP_200_OK,
)
async def reject_option(
    design_id: str,
    operation_id: str,
    option_id: str,
    request: RejectOptionRequest,
    raw_request: Request,
    store=Depends(_get_design_store_dep),
    op_store=Depends(_get_op_store_dep),
) -> dict:
    """Reject one option; record it as an anti-pattern in the knowledge base (ADP-SPEC-019)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    options_dict: dict[str, Any] = op.get("options", {})
    option_raw = options_dict.get(option_id)
    if option_raw is None:
        raise HTTPException(status_code=404, detail=f"Option {option_id!r} not found")

    option = _dict_to_option(option_raw) if isinstance(option_raw, dict) else option_raw

    if option.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Option {option_id!r} has already been actioned (status={option.status})",
        )

    # Use OperationStore's optimistic-concurrency update (ADP-SPEC-024)
    success = await op_store.update_option_status(operation_id, option_id, "rejected")
    if not success:
        raise HTTPException(
            status_code=409, detail=f"Option {option_id!r} was concurrently actioned"
        )

    actor = _get_actor(raw_request)

    logger.info(
        "recommend.rejected",
        extra={
            "event": "recommend.rejected",
            "design_id": design_id,
            "option_id": option_id,
            "actor": actor,
        },
    )

    # ADP-SPEC-019 FR-006: write rejected option as anti-pattern to knowledge base (fire-and-forget)
    import asyncio
    asyncio.create_task(_write_knowledge_item(
        item_id=f"rec-reject-{option_id}",
        title=f"[Rejected] {option.title}",
        full_text=f"{option.title}\n\nRejection reason: {request.rejection_reason}",
        metadata={
            "item_type": "rejected_recommendation",
            "option_id": option_id,
            "reason": request.rejection_reason,
            "design_id": design_id,
        },
        store=store,
    ))

    return {"option_id": option_id, "status": "rejected"}
