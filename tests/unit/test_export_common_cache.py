"""ADP-blp.18: steady-state export cycles skip unchanged files without reading them."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from adp.export import common

NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    monkeypatch.setattr(common, "_seen", {})


@pytest.fixture()
def reads(monkeypatch):
    """Count full file reads."""
    count = {"n": 0}
    real = Path.read_text

    def counting(self, *args, **kwargs):
        count["n"] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting)
    return count


def test_unchanged_file_is_skipped_without_a_read(tmp_path, reads):
    path = tmp_path / "a.json"
    data = {"id": "a", "name": "Alpha"}
    common._write_entity_file(path, data, NOW)
    first_mtime = path.stat().st_mtime_ns
    for _ in range(3):
        common._write_entity_file(path, dict(data), NOW)
    assert reads["n"] == 0
    assert path.stat().st_mtime_ns == first_mtime


def test_changed_data_is_rewritten(tmp_path):
    path = tmp_path / "a.json"
    common._write_entity_file(path, {"id": "a", "name": "Alpha"}, NOW)
    common._write_entity_file(path, {"id": "a", "name": "Beta"}, NOW)
    assert json.loads(path.read_text())["name"] == "Beta"


def test_existing_identical_file_is_adopted_after_a_restart(tmp_path, reads):
    """A new process has an empty cache: it reads once, finds the same content, never rewrites."""
    path = tmp_path / "a.json"
    data = {"id": "a"}
    common._write_entity_file(path, data, NOW)
    mtime = path.stat().st_mtime_ns
    common._seen.clear()
    reads["n"] = 0
    common._write_entity_file(path, data, NOW)
    common._write_entity_file(path, data, NOW)
    assert reads["n"] == 1
    assert path.stat().st_mtime_ns == mtime


def test_file_changed_or_removed_by_someone_else_is_restored(tmp_path):
    path = tmp_path / "a.json"
    data = {"id": "a", "name": "Alpha"}
    common._write_entity_file(path, data, NOW)

    path.write_text('{"id": "a", "name": "tampered", "extra": true}')
    common._write_entity_file(path, data, NOW)
    assert json.loads(path.read_text())["name"] == "Alpha"

    path.unlink()
    common._write_entity_file(path, data, NOW)
    assert path.exists()


def test_orphan_cleanup_forgets_the_file(tmp_path):
    path = tmp_path / "a.json"
    common._write_entity_file(path, {"id": "a"}, NOW)
    common._cleanup_orphan_files(tmp_path, live_ids=set())
    assert not path.exists()
    assert path not in common._seen


async def test_cycle_lock_always_runs_off_postgres():
    class _Session:
        def get_bind(self):
            class _Bind:
                class dialect:  # noqa: N801
                    name = "sqlite"

            return _Bind()

    async def reconcile(root, session):
        return None

    assert await common._try_cycle_lock(_Session(), reconcile) is True

    class _Broken:
        def get_bind(self):
            raise RuntimeError("no bind")

    assert await common._try_cycle_lock(_Broken(), reconcile) is True
