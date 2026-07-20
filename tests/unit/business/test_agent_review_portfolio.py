"""Unit tests: portfolio-scope Agent Review (ADP-SPEC-040).

Covers PortfolioContext generation/grounding -- distinct from the
per-capability CapabilityContext tests in test_agent_review_duplicates.py.
Only propose_new_capability and flag_capability_for_removal apply at this
scope.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adp.agents.models import GroundingCitation
from adp.business import store as bstore
from adp.business.agent_review import PortfolioContext, _parse_portfolio_suggestions
from adp.business.models import BusinessCapability


def _cap(
    id_: str, level: int, name: str = "Cap", parent_id: str | None = None
) -> BusinessCapability:
    now = datetime.now(timezone.utc)
    return BusinessCapability(
        id=id_,
        name=name,
        description=None,
        level=level,  # type: ignore[arg-type]
        parent_id=parent_id,
        position=0,
        created_at=now,
        updated_at=now,
    )


def _stage(
    stage_id: str, stage_name: str = "Stage", value_stream_id: str = "VS-1",
    value_stream_name: str = "Value Stream",
) -> bstore.CapabilityStageRef:
    return bstore.CapabilityStageRef(
        stage_id=stage_id, stage_name=stage_name,
        value_stream_id=value_stream_id, value_stream_name=value_stream_name,
    )


def _context(capabilities=None, uncovered_stages=None) -> PortfolioContext:
    return PortfolioContext(
        capabilities=capabilities or [], uncovered_stages=uncovered_stages or [],
    )


def _llm_response(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {}}


# ── propose_new_capability (reused at portfolio scope) ────────────────────────

async def test_propose_new_capability_grounded_against_portfolio_wide_uncovered_stage():
    context = _context(
        capabilities=[_cap("CAP-1", level=1)],
        uncovered_stages=[_stage("STAGE-1", stage_name="Returns Processing")],
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "Returns Management",
                "proposed_description": "Handles product returns.",
                "proposed_level": 1,
                "supporting_stage_id": "STAGE-1",
                "rationale": "Returns Processing stage has no capability coverage.",
            }
        ]
    })

    suggestions = await _parse_portfolio_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].capability_id is None
    assert suggestions[0].proposed_name == "Returns Management"
    assert not suggestions[0].advisory


async def test_propose_new_capability_unresolvable_stage_is_advisory():
    context = _context(uncovered_stages=[_stage("STAGE-1")])
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "X",
                "proposed_level": 1,
                "supporting_stage_id": "STAGE-99-invented",
                "rationale": "x",
            }
        ]
    })

    suggestions = await _parse_portfolio_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


# ── flag_capability_for_removal (portfolio-only) ──────────────────────────────

async def test_flag_capability_for_removal_is_grounded_against_full_portfolio():
    context = _context(capabilities=[_cap("CAP-1", level=1), _cap("CAP-2", level=3)])
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_capability_for_removal",
                "target_capability_id": "CAP-2",
                "rationale": "Placeholder name, no description, fully redundant.",
            }
        ]
    })

    suggestions = await _parse_portfolio_suggestions(response, context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.type == "flag_capability_for_removal"
    assert suggestion.capability_id == "CAP-2"
    assert suggestion.citations == [
        GroundingCitation(entity_type="business_capability", entity_id="CAP-2")
    ]
    assert not suggestion.advisory


async def test_flag_capability_for_removal_unresolvable_target_is_advisory():
    context = _context(capabilities=[_cap("CAP-1", level=1)])
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_capability_for_removal",
                "target_capability_id": "CAP-99-invented",
                "rationale": "x",
            }
        ]
    })

    suggestions = await _parse_portfolio_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_flag_capability_for_removal_missing_fields_is_dropped():
    context = _context(capabilities=[_cap("CAP-1", level=1)])
    response = _llm_response({
        "suggestions": [{"type": "flag_capability_for_removal", "rationale": "x"}]
    })
    suggestions = await _parse_portfolio_suggestions(response, context)
    assert suggestions == []


async def test_reclassify_type_is_ignored_at_portfolio_scope():
    """FR-010-adjacent: portfolio scope only ever produces the two types
    above -- an out-of-scope type from a misbehaving model is dropped, not
    error."""
    context = _context(capabilities=[_cap("CAP-1", level=1)])
    response = _llm_response({
        "suggestions": [
            {"type": "reclassify_strategic_relevance", "strategic_relevance": 1, "rationale": "x"}
        ]
    })
    suggestions = await _parse_portfolio_suggestions(response, context)
    assert suggestions == []


async def test_multiple_portfolio_suggestion_types_in_one_response():
    context = _context(
        capabilities=[_cap("CAP-1", level=1), _cap("CAP-2", level=3)],
        uncovered_stages=[_stage("STAGE-1")],
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "New Cap",
                "proposed_level": 1,
                "supporting_stage_id": "STAGE-1",
                "rationale": "x",
            },
            {
                "type": "flag_capability_for_removal",
                "target_capability_id": "CAP-2",
                "rationale": "y",
            },
        ]
    })

    suggestions = await _parse_portfolio_suggestions(response, context)

    types = {s.type for s in suggestions}
    assert types == {"propose_new_capability", "flag_capability_for_removal"}


async def test_empty_llm_choices_returns_empty_list():
    context = _context(capabilities=[_cap("CAP-1", level=1)])
    suggestions = await _parse_portfolio_suggestions({"choices": [], "usage": {}}, context)
    assert suggestions == []


async def test_malformed_json_response_returns_empty_list():
    context = _context(capabilities=[_cap("CAP-1", level=1)])
    response = {"choices": [{"message": {"content": "not json"}}], "usage": {}}
    suggestions = await _parse_portfolio_suggestions(response, context)
    assert suggestions == []
