"""Backfill the unified search index for existing registry rows (ADP-b6o).

Run once after applying migration 011 (and any time the embedding model changes):

    python -m adp.search.backfill
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from adp.search import (
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_TECHNICAL_CAPABILITY,
    build_text,
    default_index,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger("adp.search.backfill")


async def reindex_capabilities(session: "AsyncSession") -> int:
    """Upsert index rows for every business + technical capability. Returns count."""
    from adp.application import store as astore
    from adp.business import store as bstore

    index = default_index()
    count = 0

    for cap in await bstore.list_capabilities(session):
        await index.upsert(
            ENTITY_BUSINESS_CAPABILITY, cap.id, build_text(cap.name, cap.description), session
        )
        count += 1

    tech_caps = (await astore.list_technical_capabilities(session)).items
    for tc in tech_caps:
        await index.upsert(
            ENTITY_TECHNICAL_CAPABILITY, tc.id, build_text(tc.name, tc.description), session
        )
        count += 1

    return count


async def main() -> None:
    from adp.business import store as bstore

    factory = bstore._get_session_factory()
    async with factory() as session:
        count = await reindex_capabilities(session)
        await session.commit()
    _logger.info("search backfill complete: %d capabilities indexed", count)
    print(f"Reindexed {count} capabilities into searchable_items.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
