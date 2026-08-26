"""Backfill the unified search index for existing registry rows (ADP-b6o).

Run once after applying migration 011 (and any time the embedding model changes):

    python -m adp.search.backfill
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import sqlalchemy as sa

from adp.search import (
    ENTITY_APPLICATION,
    ENTITY_BUSINESS_CAPABILITY,
    ENTITY_BUSINESS_DOMAIN,
    ENTITY_TECHNICAL_CAPABILITY,
    ENTITY_VALUE_STREAM,
    ENTITY_VALUE_STREAM_STAGE,
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


async def reindex_all(session: "AsyncSession") -> dict[str, int]:
    """Indexes every write-hooked entity type in one pass (ADP-7bo): business +
    technical capabilities (via reindex_capabilities), applications, value
    streams, value stream stages, and business domains. Returns a per-
    entity_type count so an operator can see exactly which type came up short
    after a partial failure, rather than just a single total."""
    from adp.application import store as astore
    from adp.business import store as bstore

    index = default_index()
    counts: dict[str, int] = {
        ENTITY_BUSINESS_CAPABILITY: 0,
        ENTITY_TECHNICAL_CAPABILITY: 0,
        ENTITY_APPLICATION: 0,
        ENTITY_VALUE_STREAM: 0,
        ENTITY_VALUE_STREAM_STAGE: 0,
        ENTITY_BUSINESS_DOMAIN: 0,
    }

    cap_total = await reindex_capabilities(session)
    # reindex_capabilities doesn't break its own total down by type; re-derive
    # the per-type split the same cheap way rather than changing its signature.
    counts[ENTITY_BUSINESS_CAPABILITY] = len(await bstore.list_capabilities(session))
    counts[ENTITY_TECHNICAL_CAPABILITY] = cap_total - counts[ENTITY_BUSINESS_CAPABILITY]

    apps = (await astore.list_applications(session)).items
    for app in apps:
        await index.upsert(
            ENTITY_APPLICATION, app.id, build_text(app.name, app.description), session
        )
        counts[ENTITY_APPLICATION] += 1

    value_streams = await bstore.list_value_streams(session)
    for vs in value_streams:
        await index.upsert(
            ENTITY_VALUE_STREAM, vs.id, build_text(vs.name, vs.description), session
        )
        counts[ENTITY_VALUE_STREAM] += 1

    # No existing bulk "every stage across every value stream" function --
    # read the Core Table directly, mirroring adp.export.business_arch's own
    # precedent for this exact table (research.md D5).
    stage_rows = await session.execute(sa.select(bstore._stages))
    for row in stage_rows.mappings().all():
        await index.upsert(
            ENTITY_VALUE_STREAM_STAGE, row.id, build_text(row.name, row.description), session
        )
        counts[ENTITY_VALUE_STREAM_STAGE] += 1

    domains = await bstore.list_domains_full(session)
    for domain in domains:
        await index.upsert(
            ENTITY_BUSINESS_DOMAIN, domain.id,
            build_text(domain.name, domain.scope_statement, domain.org_unit), session,
        )
        counts[ENTITY_BUSINESS_DOMAIN] += 1

    return counts


async def main() -> None:
    from adp.business import store as bstore

    factory = bstore._get_session_factory()
    async with factory() as session:
        counts = await reindex_all(session)
        await session.commit()
    total = sum(counts.values())
    _logger.info("search backfill complete: %s", counts)
    print(f"Reindexed {total} entities into searchable_items: {counts}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
