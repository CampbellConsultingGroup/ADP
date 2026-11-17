"""ADP-blp.22: shared HTTP client, retry on overload, no retry on a client error."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

from adp.llm import client as llm

URL = "http://llm/v1/x"


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(llm, "_RETRY_BASE_DELAY", 0.0)


def _patched(handler):
    real = httpx.AsyncClient

    def make_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return mock.patch("adp.llm.client.httpx.AsyncClient", side_effect=make_client)


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


@pytest.mark.parametrize("status", [429, 500, 503, 529])
async def test_retries_then_succeeds(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status) if len(calls) < 3 else _ok()

    with _patched(handler):
        response = await llm._post_with_retry(URL, headers={}, body={}, read_timeout=5)
    assert response.status_code == 200
    assert len(calls) == 3


async def test_gives_up_after_max_retries():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(529)

    with _patched(handler):
        response = await llm._post_with_retry(URL, headers={}, body={}, read_timeout=5)
    assert response.status_code == 529  # the caller's raise_for_status() reports it
    assert len(calls) == llm._MAX_RETRIES + 1


@pytest.mark.parametrize("status", [400, 401, 404, 422])
async def test_client_errors_are_not_retried(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    with _patched(handler):
        response = await llm._post_with_retry(URL, headers={}, body={}, read_timeout=5)
    assert response.status_code == status
    assert len(calls) == 1


async def test_connect_error_retried_but_read_timeout_is_not():
    calls = []

    def flaky(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("refused")
        return _ok()

    with _patched(flaky):
        assert (
            await llm._post_with_retry(URL, headers={}, body={}, read_timeout=5)
        ).status_code == 200
    assert len(calls) == 2

    slow_calls = []

    def slow(request):
        slow_calls.append(request)
        raise httpx.ReadTimeout("slow")

    with _patched(slow), pytest.raises(httpx.ReadTimeout):
        await llm._post_with_retry(URL, headers={}, body={}, read_timeout=5)
    assert len(slow_calls) == 1  # the request may be running: never repeat it


async def test_retry_after_header_is_honoured_and_capped():
    assert llm._retry_delay(0, httpx.Response(429, headers={"retry-after": "3"})) == 3.0
    assert llm._retry_delay(0, httpx.Response(429, headers={"retry-after": "600"})) == 15.0


async def test_one_client_is_reused_and_closed():
    first = llm._shared_client()
    assert llm._shared_client() is first
    await llm.aclose_shared_clients()
    assert first.is_closed
    assert llm._shared_client() is not first
    await llm.aclose_shared_clients()
