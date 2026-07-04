"""Tests for LLMClient — correct request format and API key safety (US1 / QG-08)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from adp.intake.llm import LLMClient

_MOCK_RESPONSE = {
    "choices": [{"message": {"content": '{"requirements": []}'}}],
    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
}


def _mock_transport(response_body: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=response_body,
            request=request,
        )
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_llm_client_sends_correct_request() -> None:
    """LLMClient sends POST to /v1/chat/completions with correct params."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_MOCK_RESPONSE, request=request)

    client = LLMClient(
        base_url="https://api.example.com",
        api_key="test-key-abc123",
        model="gpt-4o",
    )

    # Patch httpx.AsyncClient to inject mock transport; use real class to avoid recursion
    _RealClient = httpx.AsyncClient
    import unittest.mock as mock

    def make_client(*args, **kwargs):  # type: ignore[return]
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealClient(*args, **kwargs)

    with mock.patch("adp.llm.client.httpx.AsyncClient", side_effect=make_client):
        await client.extract("The system must authenticate all requests.", "corr-001")

    assert len(captured) == 1
    req = captured[0]
    assert req.url.path == "/v1/chat/completions"
    body = json.loads(req.content)
    assert body["model"] == "gpt-4o"
    assert body["temperature"] == 0.1
    assert body["max_tokens"] == 4096
    assert any(m["role"] == "system" for m in body["messages"])
    assert any("authenticate all requests" in m["content"] for m in body["messages"])


@pytest.mark.asyncio
async def test_api_key_not_in_log_output(caplog: pytest.LogCaptureFixture) -> None:
    """API key MUST NEVER appear in log output (QG-08 / ART-V)."""
    secret_key = "super-secret-key-xyz789"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_MOCK_RESPONSE, request=request)

    client = LLMClient("https://api.example.com", secret_key, "gpt-4o")

    _RealClient2 = httpx.AsyncClient
    import unittest.mock as mock

    def make_client2(*args, **kwargs):  # type: ignore[return]
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealClient2(*args, **kwargs)

    with mock.patch("adp.llm.client.httpx.AsyncClient", side_effect=make_client2), \
         caplog.at_level(logging.DEBUG, logger="adp.intake"):
        await client.extract("Some text.", None)

    full_log = "\n".join(r.message for r in caplog.records)
    assert secret_key not in full_log, "API key leaked into log output!"
