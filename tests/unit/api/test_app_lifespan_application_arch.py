"""Unit tests: adp.api.app's Application registry export lifespan wiring
(ADP-SPEC-045 T016). The underlying scheduling logic is already thoroughly
tested in tests/unit/export/test_export_common.py; this only checks the
thin env-var-reading wrapper -- reusing the SAME env vars as ADP-SPEC-044.
"""

from __future__ import annotations

from adp.api import app as app_module


def test_start_application_arch_export_noop_when_root_unset(monkeypatch) -> None:
    monkeypatch.delenv("ADP_BUSINESS_ARCH_EXPORT_ROOT", raising=False)
    task = app_module.start_application_arch_export()
    assert task is None


async def test_start_application_arch_export_starts_task_when_root_set(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("ADP_BUSINESS_ARCH_EXPORT_ROOT", str(tmp_path))
    monkeypatch.setenv("ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS", "3600")  # won't actually fire

    task = app_module.start_application_arch_export()
    try:
        assert task is not None
        assert not task.done()
    finally:
        await app_module.stop_application_arch_export(task)


async def test_stop_application_arch_export_noop_for_none() -> None:
    await app_module.stop_application_arch_export(None)  # must not raise
