"""Unit tests for the Agent Review toolkit's grounding validator (ADP-SPEC-039, ART-VII)."""

from __future__ import annotations

from adp.agents.grounding import verify_references
from adp.agents.models import GroundingCitation


async def _always_true(entity_id: str) -> bool:
    return True


async def _always_false(entity_id: str) -> bool:
    return False


async def test_no_citations_is_fully_grounded():
    result = await verify_references([], lookups={})
    assert result.resolved == []
    assert result.unresolved == []
    assert result.fully_grounded


async def test_resolved_citation_is_grounded():
    citation = GroundingCitation(entity_type="business_capability", entity_id="CAP-001")
    result = await verify_references([citation], lookups={"business_capability": _always_true})
    assert result.resolved == [citation]
    assert result.unresolved == []
    assert result.fully_grounded


async def test_unresolved_citation_marks_advisory():
    citation = GroundingCitation(entity_type="business_capability", entity_id="CAP-999")
    result = await verify_references([citation], lookups={"business_capability": _always_false})
    assert result.resolved == []
    assert result.unresolved == [citation]
    assert not result.fully_grounded


async def test_unrecognized_entity_type_fails_closed():
    """An entity_type with no registered lookup is treated as unresolved,
    never silently trusted (fail closed)."""
    citation = GroundingCitation(entity_type="business_domain", entity_id="DOM-001")
    result = await verify_references([citation], lookups={"business_capability": _always_true})
    assert result.unresolved == [citation]
    assert not result.fully_grounded


async def test_mixed_citations_split_correctly():
    good = GroundingCitation(entity_type="business_capability", entity_id="CAP-001")
    bad = GroundingCitation(entity_type="business_domain", entity_id="DOM-999")
    result = await verify_references(
        [good, bad],
        lookups={"business_capability": _always_true, "business_domain": _always_false},
    )
    assert result.resolved == [good]
    assert result.unresolved == [bad]
    assert not result.fully_grounded
