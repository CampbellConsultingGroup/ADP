#!/usr/bin/env python3
"""Seed the EA pattern registry with four governed demo patterns (935-pattern-registry FR-023).

Imports every ``scripts/seed_data/patterns/*.yaml`` file and promotes each version
``draft -> proposed -> current`` (reason "Seed", confirmation id ``seed-<key>``), which also
projects each one into the knowledge base. Run AFTER ``seed_knowledge.py``: the seed patterns
cite its ``PRIN-*`` principles, and promotion requires every reference to resolve.

936-pattern-conformance: then creates the demo adoptions in ``ADOPTIONS`` against the retail
estate (run AFTER ``seed_retail.py``, which also wipes adoptions) and prints each one's derived
conformance status. Order: seed_retail.py -> seed_knowledge.py -> seed_patterns.py.

Idempotent: a re-run sees ``unchanged`` imports, skips versions that are already current, and
skips adoptions whose name already exists. Never wipes anything.

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

BACKBONE = "ea.integration.domain-event-backbone"
TRANSITION = "ea.integration.mesh-to-backbone"
HUB = "Enterprise Event Hub"

# (pattern key, adoption name, business domain name, [(role key, application name)])
ADOPTIONS: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    (BACKBONE, "Marketing & Loyalty — event backbone", "Marketing & Loyalty", [("backbone", HUB)]),
    (
        BACKBONE,
        "E-commerce & Digital — event backbone",
        "E-commerce & Digital",
        [("backbone", HUB)],
    ),
    (
        TRANSITION,
        "E-commerce & Digital — mesh migration",
        "E-commerce & Digital",
        [("backbone", HUB)],
    ),
]


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
            state = "promoted to current" if path else f"left {detail.lifecycle.value}"
            print(f"  {state:20} {key}@{version}")

        failures += await seed_adoptions(session)
    await engine.dispose()
    return failures


async def seed_adoptions(session) -> int:  # type: ignore[no-untyped-def]
    """Create the demo adoptions (skipping existing names) and print their derived status."""
    import sqlalchemy as sa

    from adp.patterns import adoptions as ad
    from adp.patterns.conformance_models import AdoptionCreate, PinIn
    from adp.patterns.engine import evaluate_pattern
    from adp.patterns.snapshot_store import SnapshotPermissions, _domains, build_snapshot
    from adp.patterns.store import _applications_mirror

    domains = {r.name: r.id for r in await session.execute(sa.select(_domains))}
    apps = {r.name: r.id for r in await session.execute(sa.select(_applications_mirror))}
    existing = {(a.pattern_key, a.name) for a in (await ad.list_adoptions(session)).items}
    failures = 0
    print("Adoptions:")
    for key, name, domain, pins in ADOPTIONS:
        if (key, name) in existing:
            print(f"  exists     {name}")
            continue
        if domain not in domains or any(app not in apps for _, app in pins):
            print(f"  SKIPPED    {name}: run seed_retail.py first (domain or application missing)")
            failures += 1
            continue
        body = AdoptionCreate(
            pattern_key=key,
            name=name,
            scope_type="business_domain",
            scope_ref=domains[domain],
            pins=[
                PinIn(role_key=r, element_type="application", element_id=apps[a]) for r, a in pins
            ],
        )
        try:
            await ad.create_adoption(body, ACTOR, session)
            await session.commit()
            print(f"  created    {name}")
        except Exception as exc:  # noqa: BLE001 - report and continue with the others
            await session.rollback()
            print(f"  FAILED     {name}: {exc}")
            failures += 1

    snapshot = await build_snapshot(session, SnapshotPermissions(True, True, True))
    for adoption in (await ad.list_adoptions(session)).items:
        resolved = await ad.resolve_definition(adoption, session)
        if resolved is None:
            continue
        report = evaluate_pattern(resolved[0], snapshot, ad.scope_of(adoption), list(adoption.pins))
        plateau = (
            f" (plateau {report.plateau.reached} -> {report.plateau.next})"
            if report.plateau
            else ""
        )
        print(f"  {report.status.value:25} {adoption.name}{plateau}")
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
