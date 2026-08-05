"""Unit tests for the shared, domain-agnostic export helpers (ADP-SPEC-045
research.md Decision 5) -- extracted from adp.export.business_arch so a
second (and future third+) domain doesn't re-implement atomic writes,
content-diffing, orphan cleanup, and the background-loop lifecycle.

These are the same behaviors ADP-SPEC-044's test_business_arch_io.py/
test_business_arch_background.py already proved for the pre-extraction code;
this file exercises them directly against their new home in adp.export.common
so the contract is validated independent of any one domain module.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from adp.export import common


def test_safe_filename_accepts_uuid_like_id() -> None:
    assert common._safe_filename("abc-123_DEF") == "abc-123_DEF.json"


def test_safe_filename_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        common._safe_filename("../../etc/passwd")


def test_write_file_atomic_creates_file(tmp_path) -> None:
    target = tmp_path / "sub" / "file.json"
    common._write_file_atomic(target, '{"id": "x"}')
    assert target.read_text(encoding="utf-8") == '{"id": "x"}'


def test_write_file_atomic_leaves_no_partial_file_on_failure(tmp_path) -> None:
    target = tmp_path / "file.json"
    target.write_text('{"id": "old"}', encoding="utf-8")
    with patch("os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            common._write_file_atomic(target, '{"id": "new"}')
    # Original file untouched; no stray .tmp files left behind.
    assert target.read_text(encoding="utf-8") == '{"id": "old"}'
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_entity_file_skips_rewrite_when_unchanged(tmp_path) -> None:
    target = tmp_path / "e.json"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    common._write_entity_file(target, {"id": "e1", "name": "Foo"}, now)
    mtime_before = target.stat().st_mtime_ns

    later = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    common._write_entity_file(target, {"id": "e1", "name": "Foo"}, later)
    mtime_after = target.stat().st_mtime_ns

    assert mtime_after == mtime_before
    # exported_at from the FIRST write is preserved (file was never rewritten).
    assert json.loads(target.read_text())["exported_at"] == now.isoformat()


def test_write_entity_file_rewrites_when_changed(tmp_path) -> None:
    target = tmp_path / "e.json"
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    common._write_entity_file(target, {"id": "e1", "name": "Foo"}, now)

    later = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    common._write_entity_file(target, {"id": "e1", "name": "Bar"}, later)

    body = json.loads(target.read_text())
    assert body["name"] == "Bar"
    assert body["exported_at"] == later.isoformat()


def test_cleanup_orphan_files_removes_only_dead_ids(tmp_path) -> None:
    d = tmp_path / "things"
    d.mkdir()
    (d / "live.json").write_text("{}")
    (d / "dead.json").write_text("{}")
    common._cleanup_orphan_files(d, live_ids={"live"})
    assert {f.stem for f in d.glob("*.json")} == {"live"}


def test_cleanup_orphan_files_noop_when_dir_missing(tmp_path) -> None:
    common._cleanup_orphan_files(tmp_path / "nonexistent", live_ids=set())  # no raise


def test_cleanup_orphan_dirs_removes_whole_dead_subtree(tmp_path) -> None:
    parent = tmp_path / "parents"
    live_dir = parent / "live-id"
    dead_dir = parent / "dead-id"
    (live_dir / "nested").mkdir(parents=True)
    (dead_dir / "nested").mkdir(parents=True)
    (dead_dir / "nested" / "f.json").write_text("{}")

    common._cleanup_orphan_dirs(parent, live_ids={"live-id"})

    assert live_dir.is_dir()
    assert not dead_dir.exists()


async def test_start_background_sync_noop_when_export_root_unset() -> None:
    calls = []

    async def fake_reconcile(export_root, session):
        calls.append((export_root, session))

    task = common.start_background_sync(
        None, 5, lambda: None, fake_reconcile, logger_name="adp.export.test"
    )
    assert task is None
    assert calls == []


async def test_start_background_sync_invokes_injected_reconcile_fn(tmp_path) -> None:
    calls = []

    class _FakeSessionCtx:
        async def __aenter__(self):
            return "fake-session"

        async def __aexit__(self, *exc):
            return False

    async def fake_reconcile(export_root, session):
        calls.append((export_root, session))

    task = common.start_background_sync(
        str(tmp_path),
        0.01,
        lambda: _FakeSessionCtx(),
        fake_reconcile,
        logger_name="adp.export.test",
    )
    assert task is not None
    await asyncio.sleep(0.05)
    await common.stop_background_sync(task)

    assert len(calls) >= 1
    assert calls[0] == (tmp_path, "fake-session")


async def test_stop_background_sync_noop_for_none() -> None:
    await common.stop_background_sync(None)  # no raise
