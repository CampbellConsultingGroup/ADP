"""Unit tests: flag_duplicate suggestion generation is scoped to the same
hierarchy level only (ADP-SPEC-039 US1, FR-011).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adp.agents.models import GroundingCitation
from adp.business import store as bstore
from adp.business.agent_review import CapabilityContext, _parse_suggestions
from adp.business.models import BusinessCapability, BusinessDomain


def _cap(
    id_: str, level: int, name: str = "Cap",
    strategic_relevance=None, maturity_level=None, domain_id=None,
) -> BusinessCapability:
    now = datetime.now(timezone.utc)
    return BusinessCapability(
        id=id_,
        name=name,
        description=None,
        level=level,  # type: ignore[arg-type]
        parent_id=None,
        position=0,
        created_at=now,
        updated_at=now,
        strategic_relevance=strategic_relevance,
        maturity_level=maturity_level,
        domain_id=domain_id,
    )


def _domain(
    id_: str, name: str = "Domain", scope_statement: str | None = "Scope."
) -> BusinessDomain:
    now = datetime.now(timezone.utc)
    return BusinessDomain(
        id=id_,
        name=name,
        scope_statement=scope_statement,
        classification="strategic",  # type: ignore[arg-type]
        org_unit=None,
        risk_flags=[],
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


def _context(
    capability: BusinessCapability, same_level_siblings=None, assignable_domains=None,
    uncovered_stages=None,
) -> CapabilityContext:
    return CapabilityContext(
        capability=capability,
        parent=None,
        children=[],
        same_level_siblings=same_level_siblings or [],
        stages=[],
        applications=[],
        technical_capabilities=[],
        designs=[],
        assignable_domains=assignable_domains or [],
        uncovered_stages=uncovered_stages or [],
    )


def _llm_response(content: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {}}


async def test_citation_within_same_level_is_grounded():
    context = _context(
        _cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1, name="Sibling")]
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_duplicate",
                "duplicate_of_capability_id": "CAP-2",
                "rationale": "Overlaps.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].duplicate_of_capability_id == "CAP-2"
    assert not suggestions[0].advisory


async def test_citation_outside_same_level_pool_is_advisory():
    """A citation to a real capability that ISN'T in the same-level pool (e.g.
    the LLM cited a child or a capability at a different level) can't be
    grounded, even though the id is real elsewhere in the system -- proving
    level-scoping is enforced via the grounding pool, not just prompt wording.
    """
    context = _context(
        _cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1, name="Sibling")]
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_duplicate",
                "duplicate_of_capability_id": "CAP-99-different-level",
                "rationale": "Overlaps.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_no_plausible_duplicate_returns_empty_list():
    context = _context(_cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1)])
    response = _llm_response({"suggestions": []})
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []


async def test_empty_llm_choices_returns_empty_list():
    """Matches the no-API-key stub client's {"choices": [], "usage": {}} shape."""
    context = _context(_cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1)])
    suggestions = await _parse_suggestions({"choices": [], "usage": {}}, context)
    assert suggestions == []


async def test_unrecognized_type_is_ignored():
    context = _context(_cap("CAP-1", level=1))
    response = _llm_response({
        "suggestions": [{"type": "propose_new_capability", "rationale": "Not yet supported"}]
    })
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []


async def test_malformed_json_response_returns_empty_list():
    context = _context(_cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1)])
    response = {"choices": [{"message": {"content": "not json"}}], "usage": {}}
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []


# ── US2: reclassify_strategic_relevance / set_maturity_level ─────────────────

async def test_set_maturity_level_suggestion_has_no_citations_and_is_never_advisory():
    """Targets the reviewed capability's own field, not another entity -- there
    is nothing to ground, so it's never marked advisory."""
    context = _context(_cap("CAP-1", level=1, maturity_level=None))
    response = _llm_response({
        "suggestions": [
            {
                "type": "set_maturity_level",
                "maturity_level": 3,
                "rationale": "Documented and standardized.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].maturity_level == 3
    assert suggestions[0].citations == []
    assert not suggestions[0].advisory


async def test_set_maturity_level_captures_previous_value_snapshot():
    context = _context(_cap("CAP-1", level=1, maturity_level=2))
    response = _llm_response({
        "suggestions": [
            {
                "type": "set_maturity_level",
                "maturity_level": 3,
                "rationale": "Now standardized org-wide.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert suggestions[0].previous_maturity_level == 2
    assert suggestions[0].maturity_level == 3


async def test_reclassify_strategic_relevance_captures_previous_value_snapshot():
    context = _context(_cap("CAP-1", level=1, strategic_relevance=3))
    response = _llm_response({
        "suggestions": [
            {
                "type": "reclassify_strategic_relevance",
                "strategic_relevance": 1,
                "rationale": "Now core to strategy.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert suggestions[0].previous_strategic_relevance == 3
    assert suggestions[0].strategic_relevance == 1


async def test_out_of_range_maturity_level_is_dropped():
    context = _context(_cap("CAP-1", level=1))
    response = _llm_response({
        "suggestions": [{"type": "set_maturity_level", "maturity_level": 6, "rationale": "x"}]
    })
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []


# ── US3: assign_domain ────────────────────────────────────────────────────────

async def test_assign_domain_citation_is_grounded_against_business_domain_not_capability():
    """Cross-entity-type grounding (T033): the citation's entity_type is
    'business_domain', looked up against the domains pool -- not
    'business_capability', even though both pools exist on the same context."""
    context = _context(
        _cap("CAP-1", level=1),
        same_level_siblings=[_cap("CAP-2", level=1, name="Sibling")],
        assignable_domains=[_domain("DOM-1", name="Retail Ops")],
    )
    response = _llm_response({
        "suggestions": [
            {"type": "assign_domain", "domain_id": "DOM-1", "rationale": "Matches scope."}
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].domain_id == "DOM-1"
    assert suggestions[0].citations == [
        GroundingCitation(entity_type="business_domain", entity_id="DOM-1")
    ]
    assert not suggestions[0].advisory


async def test_assign_domain_citation_to_unknown_domain_is_advisory():
    context = _context(
        _cap("CAP-1", level=1), assignable_domains=[_domain("DOM-1", name="Retail Ops")]
    )
    response = _llm_response({
        "suggestions": [
            {"type": "assign_domain", "domain_id": "DOM-99-invented", "rationale": "x"}
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_assign_domain_citation_to_a_real_capability_id_is_not_grounded_as_a_domain():
    """A citation pointing at a real capability id (wrong entity type) must not
    be accidentally grounded by the capability lookup -- entity_type routing
    must be exact."""
    context = _context(
        _cap("CAP-1", level=1),
        same_level_siblings=[_cap("CAP-2", level=1, name="Sibling")],
        assignable_domains=[_domain("DOM-1", name="Retail Ops")],
    )
    response = _llm_response({
        "suggestions": [{"type": "assign_domain", "domain_id": "CAP-2", "rationale": "x"}]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_assign_domain_not_produced_below_l1_even_if_llm_suggests_it():
    """FR-012 defensive gate: _build_assign_domain_suggestion drops it even if
    the model ignores the prompt's L1-only framing."""
    context = _context(
        _cap("CAP-1", level=2), assignable_domains=[_domain("DOM-1", name="Retail Ops")]
    )
    response = _llm_response({
        "suggestions": [{"type": "assign_domain", "domain_id": "DOM-1", "rationale": "x"}]
    })

    suggestions = await _parse_suggestions(response, context)

    assert suggestions == []


async def test_assign_domain_not_produced_when_already_assigned():
    """FR-012 defensive gate: dropped when the capability already has a
    domain_id, even if the model ignores the prompt's framing."""
    context = _context(
        _cap("CAP-1", level=1, domain_id="DOM-EXISTING"),
        assignable_domains=[_domain("DOM-1", name="Retail Ops")],
    )
    response = _llm_response({
        "suggestions": [{"type": "assign_domain", "domain_id": "DOM-1", "rationale": "x"}]
    })

    suggestions = await _parse_suggestions(response, context)

    assert suggestions == []


async def test_multiple_suggestion_types_in_one_response():
    context = _context(
        _cap("CAP-1", level=1), same_level_siblings=[_cap("CAP-2", level=1, name="Sibling")]
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_duplicate",
                "duplicate_of_capability_id": "CAP-2",
                "rationale": "Overlaps.",
            },
            {
                "type": "set_maturity_level",
                "maturity_level": 2,
                "rationale": "Emerging processes.",
            },
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    types = {s.type for s in suggestions}
    assert types == {"flag_duplicate", "set_maturity_level"}


# ── US4: propose_new_capability ────────────────────────────────────────────────

async def test_propose_new_capability_citation_is_grounded_against_uncovered_stage():
    """T038: grounding checks the *supporting-context* citation (the uncovered
    stage) -- never a 'proposed capability id', which doesn't exist yet."""
    context = _context(
        _cap("CAP-1", level=2),
        uncovered_stages=[_stage("STAGE-1", stage_name="Returns Processing")],
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "Returns Management",
                "proposed_description": "Handles product returns.",
                "proposed_level": 2,
                "proposed_parent_id": None,
                "supporting_stage_id": "STAGE-1",
                "rationale": "Returns Processing stage has no capability coverage.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.capability_id is None
    assert suggestion.proposed_name == "Returns Management"
    assert suggestion.proposed_level == 2
    assert suggestion.citations == [
        GroundingCitation(entity_type="value_stream_stage", entity_id="STAGE-1")
    ]
    assert not suggestion.advisory


async def test_propose_new_capability_unresolvable_stage_citation_is_advisory():
    """Acceptance Scenario 2: no verifiable supporting citation -> advisory."""
    context = _context(
        _cap("CAP-1", level=2),
        uncovered_stages=[_stage("STAGE-1", stage_name="Returns Processing")],
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "Invented Capability",
                "proposed_level": 2,
                "supporting_stage_id": "STAGE-99-invented",
                "rationale": "x",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_propose_new_capability_citation_to_a_real_capability_id_is_not_grounded_as_a_stage():
    """Entity-type routing must be exact -- a capability id cited in the stage
    field must not be accidentally grounded by the capability lookup pool."""
    context = _context(
        _cap("CAP-1", level=2),
        same_level_siblings=[_cap("CAP-2", level=2, name="Sibling")],
        uncovered_stages=[_stage("STAGE-1", stage_name="Returns Processing")],
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "New Capability",
                "proposed_level": 2,
                "supporting_stage_id": "CAP-2",
                "rationale": "x",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, context)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_propose_new_capability_missing_required_fields_is_dropped():
    context = _context(
        _cap("CAP-1", level=2), uncovered_stages=[_stage("STAGE-1")]
    )
    response = _llm_response({
        "suggestions": [{"type": "propose_new_capability", "rationale": "x"}]
    })
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []


async def test_propose_new_capability_out_of_range_level_is_dropped():
    context = _context(
        _cap("CAP-1", level=2), uncovered_stages=[_stage("STAGE-1")]
    )
    response = _llm_response({
        "suggestions": [
            {
                "type": "propose_new_capability",
                "proposed_name": "X",
                "proposed_level": 4,
                "supporting_stage_id": "STAGE-1",
                "rationale": "x",
            }
        ]
    })
    suggestions = await _parse_suggestions(response, context)
    assert suggestions == []
