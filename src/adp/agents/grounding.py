"""Grounding/citation validator for the Agent Review toolkit (ADP-SPEC-039, ART-VII).

Mirrors adp.recommendation.steps.validate_citations_step: every entity id a
suggestion cites is independently re-verified against the database, never
trusted from the LLM response. An unrecognized entity type fails closed
(treated as unresolved) rather than silently trusted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from adp.agents.models import GroundingCitation, GroundingResult

EntityLookup = Callable[[str], Awaitable[bool]]


async def verify_references(
    citations: list[GroundingCitation],
    lookups: dict[str, EntityLookup],
) -> GroundingResult:
    """Re-verify every citation against the database.

    `lookups` maps an entity_type to an async function that returns whether
    a given entity_id currently exists. A citation whose entity_type has no
    registered lookup is treated as unresolved (fail closed).
    """
    resolved: list[GroundingCitation] = []
    unresolved: list[GroundingCitation] = []

    for citation in citations:
        lookup = lookups.get(citation.entity_type)
        exists = await lookup(citation.entity_id) if lookup is not None else False
        (resolved if exists else unresolved).append(citation)

    return GroundingResult(resolved=resolved, unresolved=unresolved)
