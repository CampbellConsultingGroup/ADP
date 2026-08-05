"""Unit tests: background sync task lifecycle (ADP-SPEC-044 T013).

start_background_sync/stop_background_sync are the plumbing that lets
run_reconciliation_cycle actually run on a schedule -- tested separately from
the reconciliation content itself (test_business_arch_reconciliation.py).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from adp.export import business_arch


async def test_start_background_sync_is_noop_when_export_root_unset() -> None:
    task = business_arch.start_background_sync(
        export_root=None, interval_seconds=1, session_factory=AsyncMock()
    )
    assert task is None


async def test_start_background_sync_runs_reconciliation_on_schedule(monkeypatch) -> None:
    calls = []

    async def fake_cycle(export_root, session):
        calls.append(export_root)

    monkeypatch.setattr(business_arch, "run_reconciliation_cycle", fake_cycle)

    class _FakeSessionCtx:
        async def __aenter__(self):
            return "fake-session"

        async def __aexit__(self, *exc):
            return False

    def fake_session_factory():
        return _FakeSessionCtx()

    task = business_arch.start_background_sync(
        export_root="/tmp/whatever", interval_seconds=0.05, session_factory=fake_session_factory
    )
    assert isinstance(task, asyncio.Task)

    await asyncio.sleep(0.12)  # let a couple of cycles fire
    await business_arch.stop_background_sync(task)

    assert len(calls) >= 2
    assert task.cancelled() or task.done()


async def test_stop_background_sync_is_noop_for_none() -> None:
    await business_arch.stop_background_sync(None)  # must not raise
