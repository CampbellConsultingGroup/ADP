"""Unit tests: flag_duplicate suggestion generation is scoped to the same
hierarchy level only (ADP-SPEC-039 US1, FR-011).
"""

from __future__ import annotations

from datetime import datetime, timezone

from adp.business.agent_review import _parse_suggestions
from adp.business.models import BusinessCapability


def _cap(id_: str, level: int, name: str = "Cap") -> BusinessCapability:
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
    )


def _llm_response(content: dict) -> dict:
    import json

    return {"choices": [{"message": {"content": json.dumps(content)}}], "usage": {}}


async def test_citation_within_same_level_is_grounded():
    same_level_siblings = [_cap("CAP-2", level=1, name="Sibling")]
    response = _llm_response({
        "suggestions": [
            {"type": "flag_duplicate", "duplicate_of_capability_id": "CAP-2", "rationale": "Overlaps."}
        ]
    })

    suggestions = await _parse_suggestions(response, "CAP-1", same_level_siblings)

    assert len(suggestions) == 1
    assert suggestions[0].duplicate_of_capability_id == "CAP-2"
    assert not suggestions[0].advisory


async def test_citation_outside_same_level_pool_is_advisory():
    """A citation to a real capability that ISN'T in the same-level pool (e.g.
    the LLM cited a child or a capability at a different level) can't be
    grounded, even though the id is real elsewhere in the system -- proving
    level-scoping is enforced via the grounding pool, not just prompt wording.
    """
    same_level_siblings = [_cap("CAP-2", level=1, name="Sibling")]
    response = _llm_response({
        "suggestions": [
            {
                "type": "flag_duplicate",
                "duplicate_of_capability_id": "CAP-99-different-level",
                "rationale": "Overlaps.",
            }
        ]
    })

    suggestions = await _parse_suggestions(response, "CAP-1", same_level_siblings)

    assert len(suggestions) == 1
    assert suggestions[0].advisory


async def test_no_plausible_duplicate_returns_empty_list():
    response = _llm_response({"suggestions": []})
    suggestions = await _parse_suggestions(response, "CAP-1", [_cap("CAP-2", level=1)])
    assert suggestions == []


async def test_empty_llm_choices_returns_empty_list():
    """Matches the no-API-key stub client's {"choices": [], "usage": {}} shape."""
    suggestions = await _parse_suggestions(
        {"choices": [], "usage": {}}, "CAP-1", [_cap("CAP-2", level=1)]
    )
    assert suggestions == []


async def test_non_flag_duplicate_type_is_ignored_in_v1():
    response = _llm_response({
        "suggestions": [
            {"type": "set_maturity_level", "maturity_level": 3, "rationale": "Not yet supported"}
        ]
    })
    suggestions = await _parse_suggestions(response, "CAP-1", [])
    assert suggestions == []


async def test_malformed_json_response_returns_empty_list():
    response = {"choices": [{"message": {"content": "not json"}}], "usage": {}}
    suggestions = await _parse_suggestions(response, "CAP-1", [_cap("CAP-2", level=1)])
    assert suggestions == []
