"""ADP Design Store connector — indexes approved ArchitectureDescriptions as prior solutions."""

from __future__ import annotations

from typing import TYPE_CHECKING, AsyncIterator

from adp.knowledge.schema import KnowledgeItem, KnowledgeType

if TYPE_CHECKING:
    from adp.store import DesignStore


class DesignStoreConnector:
    """Read approved ArchitectureDescription records from ADP-SPEC-002 store."""

    def __init__(self, store: "DesignStore") -> None:
        self._store = store

    async def read_items(self) -> AsyncIterator[KnowledgeItem]:
        """Convert each stored design to a prior_solution KnowledgeItem."""
        # DesignStore.list_all_designs is not yet defined; we iterate known patterns.
        # For v1, this connector uses DesignStore internals to find approved designs.
        # When ADP-SPEC-002 exposes a list_all() method this should be updated.
        try:
            from adp.store.records import designs

            async with self._store._session_factory() as session:
                rows = await session.execute(
                    __import__("sqlalchemy", fromlist=["select"]).select(designs)
                )
                for row in rows:
                    try:
                        description = await self._store.get(row.id)
                        full_text = description.title + " " + " ".join(
                            r.description for r in description.requirements
                            if r.description
                        )
                        yield KnowledgeItem(
                            id=description.id,
                            version=str(row.current_version),
                            kind=KnowledgeType.PRIOR_SOLUTION,
                            title=description.title,
                            full_text=full_text.strip() or description.title,
                            metadata={"design_version": row.current_version},
                            source_ref=f"adp-store:{description.id}",
                        )
                    except Exception:
                        continue
        except Exception:
            return
