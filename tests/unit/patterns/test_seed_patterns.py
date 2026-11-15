"""The demo seed patterns (935 FR-023) are valid, cite only principles that seed_knowledge.py
really seeds, and can all be promoted to current in a fresh registry."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.patterns import parse_pattern_yaml
from adp.patterns import store as pstore
from adp.patterns.registry_models import LifecycleTransitionRequest
from adp.patterns.registry_models import PatternLifecycle as L
from adp.patterns.resolve import ReferenceLookups, resolve_references

ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = ROOT / "scripts" / "seed_data" / "patterns"
SEEDED_PRINCIPLES = frozenset(
    re.findall(r'"id": "(PRIN-\d+)"', (ROOT / "scripts" / "seed_knowledge.py").read_text())
)
FILES = sorted(SEED_DIR.glob("*.yaml"))


def test_seed_pattern_files() -> None:
    # 4 families; backbone, mesh and transition also have a stricter 1.1.0 (936)
    assert len(FILES) == 7
    assert len({p.name.split("@")[0] for p in FILES}) == 4
    assert len(SEEDED_PRINCIPLES) >= 6


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_seed_pattern_is_valid_and_cites_seeded_principles(path: Path) -> None:
    result = parse_pattern_yaml(path.read_text(encoding="utf-8"))
    assert result.ok, result.issues
    assert result.definition is not None
    lookups = ReferenceLookups(principles=SEEDED_PRINCIPLES)
    r1 = [
        i
        for i in resolve_references(result.definition, lookups, blocking=True)
        if i.code == "R1.unresolved_principle"
    ]
    assert r1 == []


async def test_all_seed_patterns_promote_in_a_fresh_registry(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/seed.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        for pid in SEEDED_PRINCIPLES:
            await session.execute(
                pstore._knowledge_items.insert().values(
                    id=pid,
                    version="1.0.0",
                    kind="principle",
                    title=pid,
                    full_text=pid,
                    metadata={},
                    source_ref="seed",
                    schema_version="1.0.0",
                    active=True,
                    embedding=[0.0] * 384,
                    indexed_at=pstore._now(),
                )
            )
        keys = []
        for path in FILES:
            result = await pstore.import_pattern(path.read_text(encoding="utf-8"), "seed", session)
            assert result.version is not None, result.issues
            keys.append((result.version.pattern_key, result.version.version))
        await session.commit()
        for key, version in keys:
            for to in (L.PROPOSED, L.CURRENT):
                req = LifecycleTransitionRequest(to=to, reason="Seed", confirmation_id="seed")
                await pstore.transition(key, version, req, "seed", session)
            await session.commit()
        listing = await pstore.list_versions(session, lifecycle=L.CURRENT)
        assert listing.total == 4
    await engine.dispose()


def test_seed_script_is_importable() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import seed_patterns  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    assert [p.name for p in seed_patterns.seed_files()] == [p.name for p in FILES]


def test_demo_adoptions_reference_real_seed_roles() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import seed_patterns  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    defs = {}
    for path in FILES:
        d = parse_pattern_yaml(path.read_text(encoding="utf-8")).definition
        assert d is not None
        defs[d.pattern] = d
    retail = (ROOT / "scripts" / "seed_retail.py").read_text(encoding="utf-8")
    for key, _name, domain, pins in seed_patterns.ADOPTIONS:
        assert key in defs
        assert f'"{domain}"' in retail, domain
        for role, app in pins:
            assert defs[key].roles[role].element_type.value == "application"
            assert f'"{app}"' in retail, app
