"""Unit tests: LLMClient.chat_stream (ADP-SPEC-041) -- multi-turn, streaming,
tool-use-capable chat, built on the existing raw-httpx pattern (research D1).
"""

from __future__ import annotations

import json
import unittest.mock as mock

import httpx
import pytest

from adp.llm.client import LLMClient


def _sse(*events: tuple[str, dict]) -> str:
    """Build a text/event-stream body from (event_type, data) pairs."""
    lines: list[str] = []
    for event_type, data in events:
        lines.append(f"event: {event_type}")
        lines.append(f"data: {json.dumps(data)}")
        lines.append("")
    return "\n".join(lines)


_ANTHROPIC_SSE_BODY = _sse(
    ("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 42}}}),
    (
        "content_block_start",
        {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
    ),
    (
        "content_block_delta",
        {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
        },
    ),
    (
        "content_block_delta",
        {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": " world"},
        },
    ),
    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
    (
        "message_delta",
        {
            "type": "message_delta", "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 7},
        },
    ),
    ("message_stop", {"type": "message_stop"}),
)


def _mock_stream_client(sse_body: str, captured: list[httpx.Request]):
    """Builds a fake httpx.AsyncClient whose .stream() yields a real
    streaming Response backed by MockTransport, so client.stream(...)'s
    async context-manager + aiter_lines() behave exactly as in production."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=sse_body.encode(),
            headers={"content-type": "text/event-stream"},
            request=request,
        )

    _RealClient = httpx.AsyncClient

    def make_client(*args, **kwargs):  # type: ignore[return]
        kwargs["transport"] = httpx.MockTransport(handler)
        return _RealClient(*args, **kwargs)

    return make_client


@pytest.mark.asyncio
async def test_chat_stream_yields_incremental_text_deltas_and_done() -> None:
    captured: list[httpx.Request] = []
    client = LLMClient(base_url="https://api.anthropic.com", api_key="test-key", model="claude-x")

    with mock.patch(
        "adp.llm.client.httpx.AsyncClient",
        side_effect=_mock_stream_client(_ANTHROPIC_SSE_BODY, captured),
    ):
        events = [
            event
            async for event in client.chat_stream(
                messages=[{"role": "user", "content": "Hi"}],
                system="You are a helpful assistant.",
                correlation_id="corr-1",
            )
        ]

    text_deltas = [e for e in events if e["type"] == "text_delta"]
    assert [e["text"] for e in text_deltas] == ["Hello", " world"]

    done = events[-1]
    assert done["type"] == "done"
    assert done["stop_reason"] == "end_turn"
    assert done["usage"] == {"prompt_tokens": 42, "completion_tokens": 7}

    # Request body correctly serializes multi-turn history + stream flag.
    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["stream"] is True
    assert body["system"] == "You are a helpful assistant."
    assert body["messages"] == [{"role": "user", "content": "Hi"}]
    assert "tools" not in body  # no tools passed -> omitted, not an empty list


@pytest.mark.asyncio
async def test_chat_stream_serializes_multi_turn_history_and_tools() -> None:
    captured: list[httpx.Request] = []
    client = LLMClient(base_url="https://api.anthropic.com", api_key="test-key", model="claude-x")
    messages = [
        {"role": "user", "content": "What's the capital of France?"},
        {"role": "assistant", "content": "Paris."},
        {"role": "user", "content": "And Germany?"},
    ]
    tools = [{"name": "get_capital", "description": "Look up a capital city", "input_schema": {}}]

    with mock.patch(
        "adp.llm.client.httpx.AsyncClient",
        side_effect=_mock_stream_client(_ANTHROPIC_SSE_BODY, captured),
    ):
        async for _ in client.chat_stream(messages=messages, system="sys", tools=tools):
            pass

    body = json.loads(captured[0].content)
    assert body["messages"] == messages
    assert body["tools"] == tools


_ANTHROPIC_TOOL_USE_SSE_BODY = _sse(
    ("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 10}}}),
    (
        "content_block_start",
        {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "tool_use", "id": "tool_1", "name": "get_capability"},
        },
    ),
    (
        "content_block_delta",
        {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"capability_id": '},
        },
    ),
    (
        "content_block_delta",
        {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '"CAP-1"}'},
        },
    ),
    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
    (
        "message_delta",
        {
            "type": "message_delta", "delta": {"stop_reason": "tool_use"},
            "usage": {"output_tokens": 12},
        },
    ),
    ("message_stop", {"type": "message_stop"}),
)


@pytest.mark.asyncio
async def test_chat_stream_yields_tool_use_event_with_accumulated_input() -> None:
    captured: list[httpx.Request] = []
    client = LLMClient(base_url="https://api.anthropic.com", api_key="test-key", model="claude-x")

    with mock.patch(
        "adp.llm.client.httpx.AsyncClient",
        side_effect=_mock_stream_client(_ANTHROPIC_TOOL_USE_SSE_BODY, captured),
    ):
        events = [
            event
            async for event in client.chat_stream(
                messages=[{"role": "user", "content": "Tell me about CAP-1"}],
                system="sys",
                tools=[{"name": "get_capability"}],
            )
        ]

    tool_events = [e for e in events if e["type"] == "tool_use"]
    assert len(tool_events) == 1
    assert tool_events[0]["id"] == "tool_1"
    assert tool_events[0]["name"] == "get_capability"
    assert tool_events[0]["input"] == {"capability_id": "CAP-1"}
    assert events[-1]["stop_reason"] == "tool_use"
