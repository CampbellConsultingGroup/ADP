"""Knowledge base linker — resolves named principles/capabilities to ids (FR-005)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adp.knowledge import KnowledgeRetrieval

_logger = logging.getLogger("adp.intake")


class KnowledgeLinker:
    """Match named references from extraction to knowledge base ids."""

    def __init__(
        self,
        knowledge_retrieval: "KnowledgeRetrieval | None" = None,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._retrieval = knowledge_retrieval
        self._threshold = confidence_threshold

    async def link(self, referenced_names: list[str]) -> list[str]:
        """Resolve named references to knowledge base ids.

        Returns empty list if knowledge base is not configured or no matches above threshold.
        """
        if self._retrieval is None or not referenced_names:
            return []

        from adp.knowledge.schema import RetrievalQuery

        linked_ids: list[str] = []
        for name in referenced_names:
            try:
                result = await self._retrieval.keyword_search(
                    RetrievalQuery(query_text=name, limit=1)
                )
                if result.items and result.items[0].relevance_score >= self._threshold:
                    linked_ids.append(result.items[0].citation.item_id)
            except Exception as exc:
                _logger.warning("Linker lookup failed for %r: %s", name, exc)

        return list(dict.fromkeys(linked_ids))  # deduplicate, preserve order
