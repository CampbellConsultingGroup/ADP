"""Integration tests: the pattern registry on real PostgreSQL (935-pattern-registry).

- Concurrent promotions within one family never leave two current versions; a loser of the race
  gets ConcurrentPromotionError (the partial unique index, research.md D4).
- The knowledge projection writes a real pgvector row and survives deprecation as inactive.

Docker-gated like every integration suite; runs in CI.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adp.patterns import store as pstore
from adp.patterns.registry_models import ConcurrentPromotionError, LifecycleTransitionRequest
from adp.patterns.registry_models import PatternLifecycle as L

FIX = Path(__file__).resolve().parents[1] / "unit" / "patterns" / "fixtures" / "valid"
BACKBONE = (FIX / "ea.integration.domain-event-backbone@1.0.0.yaml").read_text()
MESH = (FIX / "ea.integration.point-to-point-mesh@1.0.0.yaml").read_text()
ONE_SOR = (FIX / "ea.data.one-sor-per-capability@1.0.0.yaml").read_text()
KEY = "ea.integration.domain-event-backbone"


def _version(text: str, version: str) -> str:
    text = re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)
    return re.sub(r"^  principles: .*$", "  principles: []", text, count=1, flags=re.M)


def _req(to: L) -> LifecycleTransitionRequest:
    return LifecycleTransitionRequest(to=to, reason="integration", confirmation_id=f"c-{to}")


async def _prepare(factory: async_sessionmaker, versions: list[str]) -> None:
    async with factory() as s:
        for text in (MESH, ONE_SOR):
            await pstore.import_pattern(text, "it", s)
        for v in versions:
            await pstore.import_pattern(_version(BACKBONE, v), "it", s)
        await s.commit()
        for v in versions:
            await pstore.transition(KEY, v, _req(L.PROPOSED), "it", s)
        await s.commit()


async def test_concurrent_promotions_leave_exactly_one_current(db_engine) -> None:
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    await _prepare(factory, ["1.0.0", "1.1.0", "1.2.0"])
    async with factory() as s:
        await pstore.transition(KEY, "1.0.0", _req(L.CURRENT), "it", s, embedding=[0.0] * 384)
        await s.commit()

    async def promote(version: str) -> str:
        async with factory() as s:
            try:
                await pstore.transition(
                    KEY, version, _req(L.CURRENT), "it", s, embedding=[0.0] * 384
                )
                await s.commit()
                return "ok"
            except ConcurrentPromotionError:
                return "conflict"

    outcomes = await asyncio.gather(promote("1.1.0"), promote("1.2.0"))
    assert set(outcomes) <= {"ok", "conflict"}
    assert "ok" in outcomes
    async with factory() as s:
        current = (
            await s.execute(
                sa.select(sa.func.count())
                .select_from(pstore._versions)
                .where(
                    pstore._versions.c.pattern_key == KEY, pstore._versions.c.lifecycle == "current"
                )
            )
        ).scalar_one()
    assert current == 1


async def test_projection_writes_vector_row_and_deactivates(db_engine) -> None:
    factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    await _prepare(factory, ["1.0.0"])
    async with factory() as s:
        await pstore.transition(KEY, "1.0.0", _req(L.CURRENT), "it", s, embedding=[0.5] * 384)
        await s.commit()
        row = (
            await s.execute(
                sa.text("SELECT kind, active, version FROM knowledge_items WHERE id = :id"),
                {"id": f"adp-pattern:{KEY}"},
            )
        ).one()
        assert (row.kind, row.active, row.version) == ("reference_architecture", True, "1.0.0")
        await pstore.transition(KEY, "1.0.0", _req(L.DEPRECATED), "it", s)
        await s.commit()
        active = (
            await s.execute(
                sa.text("SELECT active FROM knowledge_items WHERE id = :id"),
                {"id": f"adp-pattern:{KEY}"},
            )
        ).scalar_one()
        assert active is False


@pytest.fixture(autouse=True)
def _no_model(monkeypatch):  # type: ignore[no-untyped-def]
    """Never load sentence-transformers here; embeddings are passed in explicitly."""
    monkeypatch.setattr("adp.knowledge.embedder.embed_or_zero", lambda title, text: [0.0] * 384)
