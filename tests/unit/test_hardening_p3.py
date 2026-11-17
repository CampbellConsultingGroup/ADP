"""ADP-blp P3 hardening: background tasks (.24), CSV cells (.10), JWKS rotation (.13),
security headers (.11)."""

from __future__ import annotations

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

from adp import background
from adp.api.routers.governance import _csv_cell
from adp.auth import tokens
from adp.auth.tokens import JwksCache

# ── background.spawn ──────────────────────────────────────────────────────────


async def test_spawn_keeps_the_task_until_done_and_logs_failures(caplog):
    done = asyncio.Event()

    async def ok():
        done.set()

    async def boom():
        raise RuntimeError("write failed")

    background.spawn(ok(), name="ok")
    failing = background.spawn(boom(), name="reasoning-write")
    assert background.pending() == 2  # held strongly, not just by the event loop
    with caplog.at_level(logging.ERROR, logger="adp.background"):
        await background.drain()
    assert done.is_set()
    assert failing.done() and background.pending() == 0
    assert "background task reasoning-write failed: write failed" in caplog.text


async def test_drain_cancels_what_does_not_finish():
    async def forever():
        await asyncio.sleep(3600)

    task = background.spawn(forever(), name="slow")
    await background.drain(timeout=0.05)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    await asyncio.sleep(0)  # let the done-callback run
    assert background.pending() == 0


# ── CSV formula injection ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value", ['=HYPERLINK("http://x")', "+1", "-1", "@SUM(A1)", "\tx", "\rx"]
)
def test_formula_like_cells_are_neutralised(value):
    assert _csv_cell(value) == "'" + value


@pytest.mark.parametrize("value", ["Design A", "a=b", "", None, 42])
def test_ordinary_cells_are_untouched(value):
    assert _csv_cell(value) == value


# ── JWKS refresh on an unknown key id ─────────────────────────────────────────


class _Cache(JwksCache):
    def __init__(self):
        super().__init__("http://unused")
        self.refreshes = 0
        self.next_keys = {"keys": [{"kid": "old"}]}

    async def _refresh(self) -> None:
        self.refreshes += 1
        self._keys = self.next_keys
        self._fetched_at = tokens.time.monotonic()


async def test_unknown_kid_triggers_one_early_refresh(monkeypatch):
    cache = _Cache()
    assert await cache.get_keys_for("old") == {"keys": [{"kid": "old"}]}
    assert cache.refreshes == 1

    # Keycloak rotates its key; the cached set is still "fresh" by TTL.
    cache.next_keys = {"keys": [{"kid": "old"}, {"kid": "new"}]}
    monkeypatch.setattr(tokens, "_JWKS_MIN_REFRESH_SECONDS", 0)
    keys = await cache.get_keys_for("new")
    assert cache.refreshes == 2
    assert {"kid": "new"} in keys["keys"]

    # A known key id never refreshes early.
    await cache.get_keys_for("new")
    await cache.get_keys_for(None)
    assert cache.refreshes == 2


async def test_made_up_kids_cannot_force_a_refresh_storm():
    cache = _Cache()
    await cache.get_keys_for("old")
    for n in range(20):
        await cache.get_keys_for(f"bogus-{n}")
    assert cache.refreshes == 1  # the minimum interval has not passed


# ── Security headers ──────────────────────────────────────────────────────────


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ADP_AUTH_ENABLED", "false")
    from adp.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def test_csp_and_hsts_on_app_responses(monkeypatch):
    resp = _client(monkeypatch).get("/health")
    csp = resp.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    script_src = csp.split("script-src")[1].split(";")[0]
    assert script_src.strip() == "'self'"  # no inline or third-party scripts
    assert "frame-ancestors 'none'" in csp
    assert resp.headers["strict-transport-security"].startswith("max-age=")
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_csp_is_configurable_and_skipped_for_keycloak_pages(monkeypatch):
    client = _client(monkeypatch)
    # /auth/* relays Keycloak, which sets its own policy for its login theme.
    assert "content-security-policy" not in client.get("/auth/admin/x").headers

    monkeypatch.setenv("ADP_CONTENT_SECURITY_POLICY", "default-src 'none'")
    assert client.get("/health").headers["content-security-policy"] == "default-src 'none'"
    monkeypatch.setenv("ADP_CONTENT_SECURITY_POLICY", "")
    assert "content-security-policy" not in client.get("/health").headers
