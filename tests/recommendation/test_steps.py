"""Tests for recommendation pipeline step functions (US1–US4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.knowledge.schema import CitationRef, RetrievalResult, RetrievalResultEntry
from adp.models import ElementKind
from adp.recommendation.models import (
    ProposedElement,
    RecommendationState,
    SolutionOption,
    TradeOffStance,
)
from adp.recommendation.steps import (
    analyze_tradeoffs_step,
    generate_step,
    rank_step,
    retrieve_step,
    validate_citations_step,
)
from adp.recommendation.telemetry import RecommendationTelemetry
from tests.knowledge.conftest import make_item

_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def _mock_telemetry() -> MagicMock:
    t = MagicMock(spec=RecommendationTelemetry)
    t.emit_step_span = MagicMock()
    return t


def _base_state(**kwargs) -> RecommendationState:
    from adp.models import Requirement

    req = Requirement(id="REQ-001", title="Stateless", description="System must be stateless")
    return {
        "operation_id": "op-001",
        "design_id": "DESIGN-001",
        "requirement_ids": ["REQ-001"],
        "requirements": [req],
        "retrieved_knowledge": [],
        "candidate_options": [],
        "ranked_options": [],
        "validated_options": [],
        "correlation_id": "corr-001",
        "error": None,
        "option_count": 3,
        "ranking_weights": (0.4, 0.3, 0.3),
        **kwargs,
    }


def _make_kr(result_entries=None) -> MagicMock:
    entries = result_entries or []
    kr = MagicMock()
    kr.hybrid_search = AsyncMock(
        return_value=RetrievalResult(
            items=entries,
            query_id="q-001",
            latency_ms=5.0,
        )
    )
    kr.resolve_citation = AsyncMock(return_value=make_item("PAT-001"))
    return kr


def _make_entry(
    item_id: str = "PAT-001", version: str = "1.0.0", kind: str = "pattern"
) -> RetrievalResultEntry:
    item = make_item(item_id, version)
    # Override kind for testing
    object.__setattr__(item, "kind", kind) if hasattr(item, "__dataclass_fields__") else None
    item = MagicMock()
    item.id = item_id
    item.version = version
    item.kind = kind
    item.title = f"Item {item_id}"
    item.full_text = f"Content of {item_id}"
    entry = MagicMock(spec=RetrievalResultEntry)
    entry.item = item
    entry.citation = CitationRef(item_id=item_id, item_version=version)
    entry.relevance_score = 0.85
    return entry


def _make_option(option_id: str = "opt-001", advisory: bool = False) -> SolutionOption:
    return SolutionOption(
        option_id=option_id,
        operation_id="op-001",
        title="Test Option",
        rationale="Reuses existing patterns",
        grounded_on=[CitationRef(item_id="PAT-001", item_version="1.0.0")],
        satisfies=["REQ-001"],
        proposed_elements=[
            ProposedElement(name="API Gateway", kind=ElementKind.CONTAINER,
                            description="Entry point", satisfies=["REQ-001"])
        ],
        advisory=advisory,
    )


def _llm_generation_response(count: int = 3) -> dict:
    options = [
        {
            "title": f"Option {i}",
            "rationale": f"Rationale {i}",
            "grounded_on": ["PAT-001"],
            "satisfies": ["REQ-001"],
            "proposed_elements": [
                {"name": f"Element {i}", "kind": "container",
                 "description": "Desc", "satisfies": ["REQ-001"]}
            ],
        }
        for i in range(1, count + 1)
    ]
    return {
        "choices": [{"message": {"content": json.dumps({"options": options})}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200},
    }


# ── US1: Retrieve step ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retrieve_step_calls_knowledge_retrieval() -> None:
    """retrieve_step calls hybrid_search once per requirement."""
    kr = _make_kr([_make_entry("PAT-001")])
    state = await retrieve_step(_base_state(), knowledge_retrieval=kr, telemetry=_mock_telemetry())
    assert kr.hybrid_search.call_count >= 1
    assert len(state["retrieved_knowledge"]) >= 1


@pytest.mark.asyncio
async def test_retrieve_step_deduplicates_by_id() -> None:
    """retrieve_step deduplicates entries with the same item_id."""
    entry = _make_entry("PAT-001")
    kr = _make_kr([entry, entry])  # same id twice
    from adp.models import Requirement

    req1 = Requirement(id="REQ-001", title="R1", description="stateless")
    req2 = Requirement(id="REQ-002", title="R2", description="secure")
    state = await retrieve_step(
        _base_state(requirement_ids=["REQ-001", "REQ-002"], requirements=[req1, req2]),
        knowledge_retrieval=kr,
        telemetry=_mock_telemetry(),
    )
    ids = [e.citation.item_id for e in state["retrieved_knowledge"]]
    assert ids.count("PAT-001") == 1


# ── US1: Generate step ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_step_produces_structured_options() -> None:
    """generate_step produces SolutionOptions with grounded_on, satisfies, proposed_elements."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=_llm_generation_response(3))

    state = await generate_step(
        _base_state(retrieved_knowledge=[_make_entry("PAT-001")]),
        llm=mock_llm,
        telemetry=_mock_telemetry(),
        option_count=3,
    )

    assert len(state["candidate_options"]) == 3
    for opt in state["candidate_options"]:
        assert opt.grounded_on, "Option must have at least one citation"
        assert opt.satisfies, "Option must satisfy at least one requirement"
        assert opt.proposed_elements, "Option must have at least one proposed element"
        assert opt.proposed_elements[0].kind in (
            ElementKind.PERSON, ElementKind.SYSTEM, ElementKind.CONTAINER, ElementKind.COMPONENT
        ), "ProposedElement kind must be a valid ElementKind"


@pytest.mark.asyncio
async def test_generate_step_caps_options_at_option_count() -> None:
    """Generate step truncates LLM response exceeding option_count."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=_llm_generation_response(5))

    state = await generate_step(
        _base_state(), llm=mock_llm, telemetry=_mock_telemetry(), option_count=3
    )
    assert len(state["candidate_options"]) == 3


@pytest.mark.asyncio
async def test_generate_defaults_invalid_kind_to_component(caplog) -> None:
    """Invalid element kind defaults to COMPONENT with a logged warning."""
    import logging
    bad_response = {
        "choices": [{"message": {"content": json.dumps({"options": [{
            "title": "Opt",
            "rationale": "R",
            "grounded_on": ["PAT-001"],
            "satisfies": ["REQ-001"],
            "proposed_elements": [{"name": "X", "kind": "microservice",
                                   "description": "D", "satisfies": ["REQ-001"]}],
        }]})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=bad_response)

    with caplog.at_level(logging.WARNING, logger="adp.recommendation"):
        state = await generate_step(
            _base_state(), llm=mock_llm, telemetry=_mock_telemetry(), option_count=1
        )

    assert state["candidate_options"][0].proposed_elements[0].kind == ElementKind.COMPONENT
    assert any("component" in r.message.lower() or "kind" in r.message.lower()
               for r in caplog.records)


# ── US1: Rank step ────────────────────────────────────────────────────────────


def test_rank_step_assigns_sequential_ranks() -> None:
    """rank_step sorts by ranking_score descending and assigns ranks 1, 2, 3."""
    opts = [
        _make_option("opt-A"),
        _make_option("opt-B"),
        _make_option("opt-C"),
    ]
    opts[0].coverage_score = 0.9
    opts[1].coverage_score = 0.5
    opts[2].coverage_score = 0.7

    state = rank_step(
        _base_state(candidate_options=opts, ranked_options=[]),
        telemetry=_mock_telemetry(),
    )
    ranked = state["ranked_options"]
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
    assert ranked[2].rank == 3
    assert ranked[0].ranking_score >= ranked[1].ranking_score >= ranked[2].ranking_score


# ── US1: Validate citations ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_citations_marks_unresolvable_as_advisory() -> None:
    """Options with unresolvable citations are marked advisory=True."""
    opt_good = _make_option("opt-good")
    opt_bad = _make_option("opt-bad")
    opt_bad.grounded_on = [CitationRef(item_id="MISSING-999", item_version="1.0.0")]

    kr = MagicMock()

    async def mock_resolve(citation):
        if citation.item_id == "MISSING-999":
            return None
        return make_item(citation.item_id)

    kr.resolve_citation = mock_resolve

    state = await validate_citations_step(
        _base_state(ranked_options=[opt_good, opt_bad]),
        knowledge_retrieval=kr,
        telemetry=_mock_telemetry(),
    )

    opts_by_id = {o.option_id: o for o in state["validated_options"]}
    assert opts_by_id["opt-good"].advisory is False
    assert opts_by_id["opt-bad"].advisory is True


# ── US2: Trade-off analysis ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tradeoff_step_produces_entry_per_criterion() -> None:
    """analyze_tradeoffs_step produces one TradeOffEntry per criterion."""
    tradeoff_response = {
        "choices": [{"message": {"content": json.dumps({"trade_offs": [
            {"criterion": "NFR-001", "stance": "meets", "rationale": "Handles load."},
            {"criterion": "Zero Trust", "stance": "partially_meets", "rationale": "Partial."},
            {"criterion": "NFR-002", "stance": "does_not_meet", "rationale": "Blocking."},
        ]})}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 80},
    }
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=tradeoff_response)

    from adp.models import Requirement

    # Use valid REQ-NNN ids; "NFR-" style are criterion labels in the prompt, not Requirement ids
    req = Requirement(id="REQ-002", title="Performance NFR",
                      description="Response time must be under 200ms performance")
    principal_entry = _make_entry("PRIN-001", "1.0.0", "principle")
    principal_entry.item.title = "Zero Trust"

    state = await analyze_tradeoffs_step(
        _base_state(
            requirements=[req],
            retrieved_knowledge=[principal_entry],
            candidate_options=[_make_option()],
        ),
        llm=mock_llm,
        telemetry=_mock_telemetry(),
    )

    trade_offs = state["candidate_options"][0].trade_offs
    assert len(trade_offs) == 3
    stances = {te.criterion: te.stance for te in trade_offs}
    assert stances["NFR-001"] == TradeOffStance.MEETS
    assert stances["Zero Trust"] == TradeOffStance.PARTIALLY_MEETS
    assert stances["NFR-002"] == TradeOffStance.DOES_NOT_MEET


@pytest.mark.asyncio
async def test_tradeoff_step_surfaces_does_not_meet() -> None:
    """does_not_meet entries must appear in trade_offs, not be filtered."""
    response = {
        "choices": [{"message": {"content": json.dumps({"trade_offs": [
            {"criterion": "NFR-001", "stance": "does_not_meet", "rationale": "Cannot meet."}
        ]})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value=response)

    from adp.models import Requirement

    state = await analyze_tradeoffs_step(
        _base_state(
            requirements=[Requirement(
                id="REQ-002", title="P", description="performance latency metric"
            )],
            candidate_options=[_make_option()],
        ),
        llm=mock_llm,
        telemetry=_mock_telemetry(),
    )

    does_not_meet = [t for t in state["candidate_options"][0].trade_offs
                     if t.stance == TradeOffStance.DOES_NOT_MEET]
    assert len(does_not_meet) == 1


@pytest.mark.asyncio
async def test_tradeoff_parse_failure_leaves_empty_list_not_error() -> None:
    """Trade-off parse failure sets trade_offs=[] and continues without failing."""
    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(return_value={
        "choices": [{"message": {"content": "not valid json"}}],
        "usage": {},
    })

    state = await analyze_tradeoffs_step(
        _base_state(candidate_options=[_make_option()]),
        llm=mock_llm,
        telemetry=_mock_telemetry(),
    )

    assert state["candidate_options"][0].trade_offs == []
    assert state.get("error") is None  # pipeline continues
