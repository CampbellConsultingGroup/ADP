"""Deterministic stand-ins that let the harness drive real pipeline steps
without a database, live LLM, or telemetry backend.
"""

from __future__ import annotations

from typing import Any

from adp.knowledge.schema import CitationRef


class _ResolvedItem:
    """Minimal shape of a resolved knowledge item — only ``version`` is read by
    ``validate_citations_step``.
    """

    def __init__(self, version: str) -> None:
        self.version = version


class FakeKnowledgeRetrieval:
    """Resolves citations against an in-memory ``item_id -> version`` index.

    Mirrors ``adp.knowledge.retrieval.KnowledgeRetrieval.resolve_citation``:
    returns the item when present, ``None`` when the citation is unresolvable.
    """

    def __init__(self, index: dict[str, str]) -> None:
        self._index = index

    async def resolve_citation(self, citation: CitationRef) -> _ResolvedItem | None:
        version = self._index.get(citation.item_id)
        return _ResolvedItem(version) if version is not None else None


class NoOpTelemetry:
    """Swallows step spans so real steps run without a telemetry backend."""

    def emit_step_span(self, step: Any) -> None:  # noqa: D102
        return None
