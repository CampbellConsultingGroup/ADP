"""Unit tests for adp.export.patterns (935-pattern-registry US6, FR-020): every current pattern
version is exported to patterns/<key>@<version>.yaml, byte-identical to the API download."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.export import patterns as pexport
from adp.patterns import store as pstore
from adp.patterns.registry_models import LifecycleTransitionRequest
from adp.patterns.registry_models import PatternLifecycle as L

FIX = Path(__file__).resolve().parents[1] / "patterns" / "fixtures" / "valid"
KEY = "ea.integration.point-to-point-mesh"
MESH = (FIX / f"{KEY}@1.0.0.yaml").read_text()


def _v(text: str, version: str) -> str:
    return re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)


@pytest.fixture()
async def session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/export.db")
    async with engine.begin() as conn:
        await conn.run_sync(pstore._metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _current(session, version: str) -> None:
    await pstore.import_pattern(_v(MESH, version), "t", session)
    for to in (L.PROPOSED, L.CURRENT):
        req = LifecycleTransitionRequest(to=to, reason="r", confirmation_id="c")
        await pstore.transition(KEY, version, req, "t", session)
    await session.commit()


async def test_current_versions_are_exported_byte_identical(session, tmp_path):
    await _current(session, "1.0.0")
    await pstore.import_pattern(_v(MESH, "2.0.0"), "t", session)  # draft: not exported
    await session.commit()
    root = tmp_path / "out"
    await pexport.run_reconciliation_cycle(root, session)
    files = sorted(p.name for p in (root / "patterns").iterdir())
    assert files == [f"{KEY}@1.0.0.yaml"]
    exported = (root / "patterns" / files[0]).read_bytes()
    assert exported == (await pstore.get_yaml(KEY, "1.0.0", session)).encode("utf-8")


async def test_unchanged_files_are_not_rewritten(session, tmp_path):
    await _current(session, "1.0.0")
    root = tmp_path / "out"
    await pexport.run_reconciliation_cycle(root, session)
    path = root / "patterns" / f"{KEY}@1.0.0.yaml"
    os.utime(path, (1, 1))
    await pexport.run_reconciliation_cycle(root, session)
    assert path.stat().st_mtime == 1


async def test_superseded_version_file_is_removed(session, tmp_path):
    await _current(session, "1.0.0")
    root = tmp_path / "out"
    await pexport.run_reconciliation_cycle(root, session)
    (root / "patterns" / "notes.txt").write_text("not ours")
    await _current(session, "1.1.0")
    await pexport.run_reconciliation_cycle(root, session)
    names = sorted(p.name for p in (root / "patterns").iterdir())
    assert names == [f"{KEY}@1.1.0.yaml", "notes.txt"]


@pytest.mark.parametrize(
    ("key", "version"),
    [("../etc.passwd", "1.0.0"), ("ea.a/b", "1.0.0"), ("ea.a.b", "1.0"), ("ea.a.b", "../1.0.0")],
)
def test_filename_rejects_unsafe_parts(key: str, version: str) -> None:
    with pytest.raises(ValueError):
        pexport.pattern_filename(key, version)


def test_filename_allows_dotted_keys() -> None:
    assert pexport.pattern_filename("ea.integration.x", "1.10.0") == "ea.integration.x@1.10.0.yaml"


async def test_cycle_swallows_errors(tmp_path, caplog):
    class Broken:
        async def execute(self, *a, **k):
            raise RuntimeError("db down")

    await pexport.run_reconciliation_cycle(tmp_path, Broken())  # type: ignore[arg-type]
    assert any("patterns_export.cycle_failed" in r.message for r in caplog.records)
