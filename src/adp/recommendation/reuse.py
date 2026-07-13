"""Reuse-candidate retrieval: surface existing applications (and the business
capabilities they provide) that are relevant to the requirements, so the
recommender can prefer reuse over net-new build (ADP-SPEC-007 registry grounding).

The relevance scorer is deliberately simple and dependency-free (keyword overlap):
applications are not embedded, and a transparent, explainable match is preferable
to an opaque score for a decision an architect must trust.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from adp.recommendation.models import ReuseCandidate

# Short, generic words that would otherwise inflate overlap scores.
_STOPWORDS = frozenset({
    "the", "and", "for", "with", "that", "this", "must", "shall", "should", "will",
    "system", "systems", "data", "user", "users", "support", "provide", "using",
    "able", "from", "into", "each", "any", "all", "are", "has", "have", "need",
})


def tokenize(text: str) -> set[str]:
    """Lowercase alphanumeric tokens of length >= 3, minus common stopwords."""
    return {
        tok
        for tok in re.split(r"[^a-z0-9]+", (text or "").lower())
        if len(tok) >= 3 and tok not in _STOPWORDS
    }


def relevance(requirement_tokens: set[str], candidate_tokens: set[str]) -> float:
    """Fraction of requirement terms the candidate covers (0.0–1.0).

    Recall-oriented: a candidate matching more of what the requirements ask for
    scores higher. Returns 0.0 when there is nothing to match.
    """
    if not requirement_tokens:
        return 0.0
    shared = requirement_tokens & candidate_tokens
    return len(shared) / len(requirement_tokens)


class ReuseProvider(Protocol):
    """Anything that can surface reuse candidates for a set of requirements."""

    async def find_candidates(
        self, requirements: list[Any], *, limit: int = 5
    ) -> list[ReuseCandidate]: ...


def _requirement_text(requirements: list[Any]) -> str:
    parts: list[str] = []
    for req in requirements:
        parts.append(str(getattr(req, "description", "") or ""))
        parts.append(str(getattr(req, "title", "") or ""))
    return " ".join(parts)


class ApplicationReuseProvider:
    """Scores the application registry against the requirements via keyword overlap."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def find_candidates(
        self, requirements: list[Any], *, limit: int = 5
    ) -> list[ReuseCandidate]:
        from adp.application.store import list_app_capability_links, list_applications

        req_tokens = tokenize(_requirement_text(requirements))
        if not req_tokens:
            return []

        candidates: list[ReuseCandidate] = []
        async with self._session_factory() as session:
            apps = (await list_applications(session)).items
            for app in apps:
                links = (await list_app_capability_links(app.id, session)).items
                cap_names = [ln.capability_name for ln in links]
                haystack = " ".join([app.name, app.description or "", *cap_names])
                score = relevance(req_tokens, tokenize(haystack))
                if score <= 0:
                    continue
                candidates.append(
                    ReuseCandidate(
                        app_id=app.id,
                        name=app.name,
                        description=app.description,
                        capabilities=cap_names,
                        time_classification=getattr(
                            app.time_classification, "value", None
                        ),
                        r_strategy=getattr(app.r_strategy, "value", None),
                        relevance=round(score, 3),
                    )
                )

        candidates.sort(key=lambda c: c.relevance, reverse=True)
        return candidates[:limit]
