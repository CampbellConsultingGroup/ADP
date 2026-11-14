#!/usr/bin/env python3
"""Seed the EA pattern registry with four governed demo patterns (935-pattern-registry FR-023).

Imports every ``scripts/seed_data/patterns/*.yaml`` file and promotes each version
``draft -> proposed -> current`` (reason "Seed", confirmation id ``seed-<key>``), which also
projects each one into the knowledge base. Run AFTER ``seed_knowledge.py``: the seed patterns
cite its ``PRIN-*`` principles, and promotion requires every reference to resolve.

Idempotent: a re-run sees ``unchanged`` imports and skips versions that are already current.
Unlike ``seed_retail.py`` this never wipes anything; patterns also survive a retail re-seed.

Usage:
    python scripts/seed_patterns.py
Requires ADP_DATABASE_URL (or uses the default local URL).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.knowledge.embedder import embed_or_zero
from adp.patterns import store as pstore
from adp.patterns.projection import build_projection
from adp.patterns.registry_models import (
    ImportStatus,
    LifecycleTransitionRequest,
    PatternLifecycle,
    PatternRegistryError,
)

SEED_DIR = Path(__file__).parent / "seed_data" / "patterns"
ACTOR = "seed"


def seed_files() -> list[Path]:
    return sorted(SEED_DIR.glob("*.yaml"))


async def seed(db_url: str) -> int:
    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    imported: list[tuple[str, str]] = []
    failures = 0
    async with factory() as session:
        # 1. Import everything first, so relation targets exist before any promotion.
        for path in seed_files():
            result = await pstore.import_pattern(path.read_text(encoding="utf-8"), ACTOR, session)
            if result.status == ImportStatus.REJECTED or result.version is None:
                print(f"  REJECTED {path.name}: {[i.code for i in result.issues]}")
                failures += 1
                continue
            await session.commit()
            v = result.version
            imported.append((v.pattern_key, v.version))
            print(f"  {result.status.value:9} {v.pattern_key}@{v.version}")

        # 2. Promote each version to current.
        for key, version in imported:
            detail = await pstore.get_version_detail(key, version, session)
            path = {
                PatternLifecycle.DRAFT: [PatternLifecycle.PROPOSED, PatternLifecycle.CURRENT],
                PatternLifecycle.PROPOSED: [PatternLifecycle.CURRENT],
            }.get(detail.lifecycle, [])
            try:
                for to in path:
                    embedding = None
                    if to == PatternLifecycle.CURRENT:
                        item = build_projection(detail.definition)
                        embedding = await asyncio.to_thread(
                            embed_or_zero, item.title, item.full_text
                        )
                    req = LifecycleTransitionRequest(
                        to=to, reason="Seed", confirmation_id=f"seed-{key}"
                    )
                    await pstore.transition(key, version, req, ACTOR, session, embedding=embedding)
                    await session.commit()
            except PatternRegistryError as exc:
                await session.rollback()
                print(f"  NOT PROMOTED {key}@{version}: {exc}")
                for issue in getattr(exc, "issues", []):
                    print(f"      {issue.code} {issue.path}: {issue.message}")
                failures += 1
                continue
            state = "already current" if not path else "promoted to current"
            print(f"  {state:20} {key}@{version}")
    await engine.dispose()
    return failures


def main() -> None:
    db_url = os.environ.get(
        "ADP_DATABASE_URL", "postgresql+asyncpg://adp_user:adp_pass@127.0.0.1:5432/adp"
    )
    print(f"Seeding EA patterns into {db_url.rsplit('@', 1)[-1]} ...")
    failures = asyncio.run(seed(db_url))
    print("Done." if failures == 0 else f"Done with {failures} failure(s).")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
