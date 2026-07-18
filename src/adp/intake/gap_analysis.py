"""Capability gap analysis for Requirements Intake (ADP-zg3.4).

Compares the capabilities implied by a design's confirmed requirements
against the existing business_capabilities and technical_capabilities
registries, reusing the same deterministic keyword-overlap approach as the
recommendation engine's registry grounding (ADP-SPEC-007,
adp.recommendation.reuse) rather than an LLM: a transparent, explainable
match is preferable to an opaque score for a decision an architect must
trust, and it keeps this analysis testable without a live LLM.

Granularity: each confirmed requirement is treated as one "needed
capability" signal. If an existing capability's name+description covers
enough of the requirement's terms, the requirement is "present" (cited
against that capability); otherwise it surfaces as "missing" (a gap).

Advisory only in v1 -- a missing capability is NOT auto-created in the
registry. Promoting a gap into a real capability record is a deliberate,
separate architect action left for a future iteration.
"""

from __future__ import annotations

from dataclasses import dataclass

from adp.recommendation.reuse import relevance, tokenize

# Below this fraction of a requirement's terms covered by the best-matching
# capability, the match is not considered real -- the requirement surfaces
# as a gap instead of a citation.
MATCH_THRESHOLD = 0.34


@dataclass(frozen=True)
class RequirementRef:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class CapabilityRef:
    id: str
    name: str
    description: str | None


@dataclass(frozen=True)
class CapabilityMatch:
    requirement_id: str
    requirement_title: str
    capability_id: str
    capability_name: str
    relevance: float


@dataclass(frozen=True)
class CapabilityGap:
    requirement_id: str
    requirement_title: str


@dataclass(frozen=True)
class GapAnalysisSection:
    present: list[CapabilityMatch]
    missing: list[CapabilityGap]


def _requirement_tokens(req: RequirementRef) -> set[str]:
    return tokenize(f"{req.title} {req.description}")


def _capability_tokens(cap: CapabilityRef) -> set[str]:
    return tokenize(f"{cap.name} {cap.description or ''}")


def analyze_section(
    requirements: list[RequirementRef],
    capabilities: list[CapabilityRef],
    *,
    threshold: float = MATCH_THRESHOLD,
) -> GapAnalysisSection:
    """Split requirements into needed-and-present vs needed-but-missing.

    For each requirement, the best-scoring capability (by keyword-overlap
    relevance) is cited if it meets `threshold`; otherwise the requirement
    is a gap. Deterministic and dependency-free by design (see module
    docstring) -- no LLM call, no live registry mutation.
    """
    cap_tokens = [(cap, _capability_tokens(cap)) for cap in capabilities]

    present: list[CapabilityMatch] = []
    missing: list[CapabilityGap] = []
    for req in requirements:
        req_tokens = _requirement_tokens(req)
        best_cap: CapabilityRef | None = None
        best_score = 0.0
        for cap, tokens in cap_tokens:
            score = relevance(req_tokens, tokens)
            if score > best_score:
                best_score = score
                best_cap = cap

        if best_cap is not None and best_score >= threshold:
            present.append(
                CapabilityMatch(
                    requirement_id=req.id,
                    requirement_title=req.title,
                    capability_id=best_cap.id,
                    capability_name=best_cap.name,
                    relevance=round(best_score, 3),
                )
            )
        else:
            missing.append(CapabilityGap(requirement_id=req.id, requirement_title=req.title))

    return GapAnalysisSection(present=present, missing=missing)
