"""Requirements Intake HTTP API — ADP-SPEC-014.

Thin HTTP adapter over adp.intake.ExtractionOrchestrator (ADP-SPEC-006).
Source text is NEVER stored, logged, or persisted after extraction.
ART-VIII: every proposal requires an explicit per-proposal human action — no auto-confirm.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from adp.intake.models import (
    IntakeSubmission,
    RequirementKind,
    SubmissionMode,
)
from adp.telemetry.context import get_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/designs", tags=["intake"])


# ── Pydantic v2 request / response models ─────────────────────────────────────

class IntakeSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["bulk_text", "structured_form"]
    # Known-requirements free-text. Optional: empty means no requirements to
    # extract (the caller may be submitting only the framing fields below).
    text: str = ""
    kind: RequirementKind | None = None
    # Optional model override — if not provided, uses the globally configured extraction model
    model: str | None = None
    # ADP-SPEC intake framing — persisted to the canonical model (inputs to
    # recommendation). Required in the UI; optional here so existing bulk_text /
    # structured_form callers are unaffected.
    business_problem: str | None = None
    desired_outcome: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "IntakeSubmitRequest":
        if self.mode == "structured_form" and self.kind is None:
            raise ValueError("kind is required when mode is 'structured_form'")
        # Avoid wasting an LLM call on trivially short text; empty is allowed
        # (no known requirements) and simply skips extraction.
        if self.mode == "bulk_text" and self.text and len(self.text) < 20:
            raise ValueError(
                "text is too short for extraction (minimum 20 characters for bulk_text mode)"
            )
        return self


class IntakeSubmitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    design_id: str
    mode: str
    status: str


class ProposalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    draft_statement: str
    kind: str
    source_excerpt: str
    confidence: float
    verification_status: str
    status: str
    confirmed_statement: str | None = None


class IntakeStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    design_id: str
    status: str
    proposals: list[ProposalResponse]
    result_summary: str | None = None
    error_description: str | None = None


class ConfirmProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edited_statement: str | None = None


class ConfirmProposalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    title: str
    description: str
    kind: str
    # I1 fix: proposal_id is None for direct-add (T030), non-null for proposal confirm
    proposal_id: str | None = None


class DirectRequirementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    kind: RequirementKind
    description: str | None = None

    @field_validator("statement")
    @classmethod
    def _validate_statement(cls, v: str) -> str:
        if len(v.strip()) < 10:
            raise ValueError("statement must be at least 10 characters")
        return v


class RequirementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    description: str
    kind: str
    satisfies: list[str]


class RequirementListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    requirements: list[RequirementItem]
    total: int


# ── Capability gap analysis (ADP-zg3.4) ────────────────────────────────────────

class CapabilityMatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    requirement_title: str
    capability_id: str
    capability_name: str
    relevance: float


class CapabilityGapItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    requirement_title: str


class CapabilityGapSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: list[CapabilityMatchItem]
    missing: list[CapabilityGapItem]


class CapabilityGapAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    business_capabilities: CapabilityGapSection
    technical_capabilities: CapabilityGapSection


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _get_actor(request: Request) -> str:
    """Return actor identity: authenticated user if available, else X-Actor header."""
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_design_store():  # type: ignore[return]
    from adp.api.deps import get_design_store
    return await get_design_store()


async def _get_op_store():  # type: ignore[return]
    from adp.api.deps import get_operation_store
    return await get_operation_store()


async def _get_business_session():
    from adp.business import store as bstore
    factory = bstore._get_session_factory()
    async with factory() as session:
        yield session


async def _get_application_session():
    from adp.application import store as astore
    factory = astore._get_session_factory()
    async with factory() as session:
        yield session


def _make_orchestrator(model: str | None = None):  # type: ignore[return]
    """Create ExtractionOrchestrator; stub LLMClient if ADP_LLM_ENDPOINT is not set.

    Uses the model from:
    1. The request-specified model (if provided)
    2. The globally configured extraction model (from PUT /api/v1/config/llm)
    3. ADP_LLM_MODEL env var fallback
    4. claude-sonnet-4-6 default
    """
    from adp.agents.llm_stub import StubLLMClient
    from adp.api.routers.config import get_api_key, get_extraction_model
    from adp.intake.orchestrator import ExtractionOrchestrator
    from adp.llm.client import LLMClient

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = get_api_key()

    if not api_key:
        # Graceful degradation: stub client returns empty extraction
        llm = StubLLMClient(base_url="http://stub", api_key="stub", model="stub")  # type: ignore[assignment]
    else:
        active_model = model or get_extraction_model()
        llm = LLMClient(base_url=endpoint, api_key=api_key, model=active_model)  # type: ignore[assignment]

    return ExtractionOrchestrator(llm_client=llm)


def _proposals_from_store(op: dict) -> list[ProposalResponse]:
    """Convert stored proposal dicts to ProposalResponse objects.

    Proposals are stored as serialized dicts (ADP-SPEC-024).
    """
    proposals_raw = op.get("proposals", {})
    result = []
    for p in proposals_raw.values():
        if isinstance(p, dict):
            result.append(ProposalResponse(
                proposal_id=p["proposal_id"],
                draft_statement=p["draft_statement"],
                kind=p["kind"],
                source_excerpt=p.get("source_excerpt", ""),
                confidence=p.get("confidence", 0.0),
                verification_status=p.get("verification_status", "unverified"),
                status=p.get("status", "pending"),
                confirmed_statement=p.get("confirmed_statement"),
            ))
        else:
            # Legacy in-memory path (e.g. in unit tests using raw objects)
            result.append(ProposalResponse(
                proposal_id=p.proposal_id,
                draft_statement=p.draft_statement,
                kind=p.kind.value,
                source_excerpt=p.source_excerpt,
                confidence=p.confidence,
                verification_status=p.verification_status.value,
                status=p.status.value,
                confirmed_statement=p.confirmed_statement,
            ))
    return result


# ── US1: Submit intake + poll status ──────────────────────────────────────────

@router.post(
    "/{design_id}/intake",
    response_model=IntakeSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_intake(
    design_id: str,
    request: IntakeSubmitRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    store=Depends(_get_design_store),
    op_store=Depends(_get_op_store),
) -> IntakeSubmitResponse:
    """Start AI extraction from text or structured form (ADP-SPEC-014 US1 / FR-001).

    ART-VIII: source text is passed to the background task only; deleted after extraction.
    Returns immediately with an operation_id for polling.
    """
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]
    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    actor = _get_actor(raw_request)

    # ADP-SPEC: persist intake framing to the canonical model. Round-trips via
    # DesignStore (a new immutable design version). Raw source text is NOT stored.
    if request.business_problem is not None or request.desired_outcome is not None:
        if request.business_problem is not None:
            design.business_problem = request.business_problem
        if request.desired_outcome is not None:
            design.desired_outcome = request.desired_outcome
        design.updated_at = datetime.now(timezone.utc)
        await store.save(design, actor=actor)

    operation_id = str(uuid.uuid4())
    correlation_id = raw_request.headers.get("X-Trace-ID", get_trace_id() or str(uuid.uuid4()))

    await op_store.create(operation_id, "intake", design_id, actor, {
        "proposals": {},
        "correlation_id": correlation_id,
        "result_summary": None,
        "error_description": None,
    })

    # Extraction only runs when there is known-requirements text to extract.
    has_text = bool(request.text and request.text.strip())
    if has_text:
        submission = IntakeSubmission(
            submission_id=str(uuid.uuid4()),
            mode=SubmissionMode(request.mode),
            text=request.text,
            submitted_by=actor,
            submitted_at=datetime.now(timezone.utc),
            operation_id=operation_id,
        )
        orchestrator = _make_orchestrator(model=request.model)
        background_tasks.add_task(orchestrator.run, submission, op_store)
        op_status = "pending"
    else:
        # Nothing to extract — the caller submitted only framing fields.
        await op_store.update(
            operation_id,
            status="completed",
            payload_patch={"result_summary": "No known requirements provided; framing saved."},
        )
        op_status = "completed"

    logger.info(
        "intake.submit",
        extra={
            "event": "intake.submit",
            "design_id": design_id,
            "operation_id": operation_id,
            "mode": request.mode,
            "correlation_id": correlation_id,
            "extraction": has_text,
        },
    )

    return IntakeSubmitResponse(
        operation_id=operation_id,
        design_id=design_id,
        mode=request.mode,
        status=op_status,
    )


@router.get(
    "/{design_id}/intake/{operation_id}",
    response_model=IntakeStatusResponse,
)
async def get_intake_status(
    design_id: str,
    operation_id: str,
    op_store=Depends(_get_op_store),
) -> IntakeStatusResponse:
    """Poll extraction status and retrieve proposals (ADP-SPEC-014 US1 / FR-002)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    return IntakeStatusResponse(
        operation_id=operation_id,
        design_id=op["design_id"],
        status=op["status"],
        proposals=_proposals_from_store(op),
        result_summary=op.get("result_summary"),
        error_description=op.get("error_description"),
    )


# ── US2: Confirm / Reject proposals ───────────────────────────────────────────

@router.post(
    "/{design_id}/intake/{operation_id}/proposals/{proposal_id}/confirm",
    response_model=ConfirmProposalResponse,
)
async def confirm_proposal(
    design_id: str,
    operation_id: str,
    proposal_id: str,
    request: ConfirmProposalRequest,
    raw_request: Request,
    store=Depends(_get_design_store),
    op_store=Depends(_get_op_store),
) -> ConfirmProposalResponse:
    """Confirm a proposal → writes Requirement + AuditEntry (ART-VIII / ART-IX / FR-003)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    proposals = op.get("proposals", {})
    proposal = proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")

    # Proposal is a dict; check status as string
    if isinstance(proposal, dict):
        proposal_status = proposal.get("status")
    else:
        proposal_status = proposal.status.value
    if proposal_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal {proposal_id!r} has already been actioned (status={proposal_status})",
        )

    actor = _get_actor(raw_request)
    orchestrator = _make_orchestrator()

    try:
        requirement = await orchestrator.confirm_proposal(
            proposal_id=proposal_id,
            operation_id=operation_id,
            confirming_actor=actor,
            edited_statement=request.edited_statement,
            operation_store=op_store,
            design_store=store,
            design_id=design_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    proposal_kind = proposal.get("kind") if isinstance(proposal, dict) else proposal.kind.value
    return ConfirmProposalResponse(
        requirement_id=requirement.id,
        title=requirement.title,
        description=requirement.description,
        kind=str(proposal_kind),
        proposal_id=proposal_id,
    )


@router.post(
    "/{design_id}/intake/{operation_id}/proposals/{proposal_id}/reject",
    status_code=status.HTTP_200_OK,
)
async def reject_proposal(
    design_id: str,
    operation_id: str,
    proposal_id: str,
    raw_request: Request,
    store=Depends(_get_design_store),
    op_store=Depends(_get_op_store),
) -> dict:
    """Reject a proposal — no Requirement written (ART-VIII / FR-004)."""
    op = await op_store.get(operation_id)
    if op is None:
        raise HTTPException(status_code=404, detail=f"Operation {operation_id!r} not found")

    proposals = op.get("proposals", {})
    proposal = proposals.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")

    if isinstance(proposal, dict):
        proposal_status = proposal.get("status")
    else:
        proposal_status = proposal.status.value
    if proposal_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Proposal {proposal_id!r} has already been actioned",
        )

    actor = _get_actor(raw_request)
    orchestrator = _make_orchestrator()

    await orchestrator.reject_proposal(
        proposal_id=proposal_id,
        operation_id=operation_id,
        rejecting_actor=actor,
        operation_store=op_store,
        design_store=store,
        design_id=design_id,
    )

    return {"proposal_id": proposal_id, "status": "rejected"}


# ── US3: Direct requirement add (structured form fast path) ───────────────────

@router.post(
    "/{design_id}/requirements",
    response_model=ConfirmProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_requirement(
    design_id: str,
    request: DirectRequirementRequest,
    raw_request: Request,
    store=Depends(_get_design_store),
) -> ConfirmProposalResponse:
    """Add a requirement directly without LLM extraction (ADP-SPEC-014 US3 / FR-005).

    ART-VIII: submitting the form IS the human confirmation — no proposal step.
    ART-IX: writes an audit entry.
    """
    from adp.models import AuditEntry, Requirement
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    actor = _get_actor(raw_request)

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    req_id = f"REQ-{len(design.requirements) + 1:03d}"
    statement = request.statement.strip()
    description = (request.description or statement).strip()

    requirement = Requirement(
        id=req_id,
        title=statement[:120],
        description=description,
    )

    from adp.audit.writer import next_audit_id as _next_audit_id
    audit_id = _next_audit_id(design)
    audit_entry = AuditEntry(
        id=audit_id,
        actor=actor,
        action="add-requirement",
        affected_entity=req_id,
        summary=f"Requirement {req_id} added directly via structured form",
        timestamp=datetime.now(timezone.utc),
        origin="human",
    )

    design.requirements.append(requirement)
    design.audit_log.append(audit_entry)
    await store.save(design, actor=actor)

    logger.info(
        "intake.requirement_added",
        extra={
            "event": "intake.requirement_added",
            "design_id": design_id,
            "requirement_id": req_id,
            "actor": actor,
        },
    )

    return ConfirmProposalResponse(
        requirement_id=req_id,
        title=requirement.title,
        description=requirement.description,
        kind=request.kind.value,
        proposal_id=None,  # I1 fix: null for direct add
    )


# ── US4: List requirements ────────────────────────────────────────────────────

@router.get(
    "/{design_id}/requirements",
    response_model=RequirementListResponse,
)
async def list_requirements(
    design_id: str,
    store=Depends(_get_design_store),
) -> RequirementListResponse:
    """List all requirements for a design (ADP-SPEC-014 US4 / FR-006)."""
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    # Build element satisfies map: req_id → list of element IDs that satisfy it
    satisfies_map: dict[str, list[str]] = {}
    for element in design.elements:
        for req_id in (element.satisfies or []):
            satisfies_map.setdefault(req_id, []).append(element.id)

    items = [
        RequirementItem(
            id=req.id,
            title=req.title,
            description=req.description,
            kind=getattr(req, "kind", "functional"),
            satisfies=satisfies_map.get(req.id, []),
        )
        for req in design.requirements
    ]

    return RequirementListResponse(
        design_id=design_id,
        requirements=items,
        total=len(items),
    )


# ── Capability gap analysis (ADP-zg3.4) ────────────────────────────────────────

@router.get(
    "/{design_id}/capability-gaps",
    response_model=CapabilityGapAnalysisResponse,
)
async def get_capability_gaps(
    design_id: str,
    store=Depends(_get_design_store),
    biz_session=Depends(_get_business_session),
    app_session=Depends(_get_application_session),
) -> CapabilityGapAnalysisResponse:
    """Compare confirmed requirements against the capability registries.

    Advisory only: surfaces which needed capabilities already exist
    (cited from the registry) and which appear to be gaps. Does not
    create or modify any registry records.
    """
    from adp.application.store import list_technical_capabilities
    from adp.business.store import list_capabilities
    from adp.intake.gap_analysis import (
        CapabilityRef,
        GapAnalysisSection,
        RequirementRef,
        analyze_section,
    )
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    requirements = [
        RequirementRef(id=req.id, title=req.title, description=req.description)
        for req in design.requirements
    ]

    biz_caps = await list_capabilities(biz_session)
    biz_refs = [
        CapabilityRef(id=c.id, name=c.name, description=c.description) for c in biz_caps
    ]
    biz_section = analyze_section(requirements, biz_refs)

    tech_caps = (await list_technical_capabilities(app_session)).items
    tech_refs = [
        CapabilityRef(id=c.id, name=c.name, description=c.description) for c in tech_caps
    ]
    tech_section = analyze_section(requirements, tech_refs)

    def _to_response(section: GapAnalysisSection) -> CapabilityGapSection:
        return CapabilityGapSection(
            present=[
                CapabilityMatchItem(
                    requirement_id=m.requirement_id,
                    requirement_title=m.requirement_title,
                    capability_id=m.capability_id,
                    capability_name=m.capability_name,
                    relevance=m.relevance,
                )
                for m in section.present
            ],
            missing=[
                CapabilityGapItem(
                    requirement_id=g.requirement_id, requirement_title=g.requirement_title
                )
                for g in section.missing
            ],
        )

    return CapabilityGapAnalysisResponse(
        design_id=design_id,
        business_capabilities=_to_response(biz_section),
        technical_capabilities=_to_response(tech_section),
    )


# ── Core design CRUD (wiring existing DesignStore) ────────────────────────────

@router.get("/{design_id}", response_model=None)
async def get_design(
    design_id: str,
    store=Depends(_get_design_store),
) -> dict:
    """Fetch a design from the store. Enables the web canvas to load designs (ADP-SPEC-003)."""
    from adp.store.store import DesignNotFoundError  # type: ignore[attr-defined]

    try:
        design = await store.get(design_id)
    except DesignNotFoundError:
        raise HTTPException(status_code=404, detail=f"Design {design_id!r} not found")

    return design.model_dump(mode="json")
