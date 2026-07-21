"""Configurable LLM client — supports Anthropic and OpenAI-compatible endpoints.

Canonical location: adp.llm.client (moved from adp.intake.llm in ADP-SPEC-023).
adp.intake.llm re-exports LLMClient for backward compatibility.

Detects provider from base_url:
  - "anthropic.com" → uses Anthropic Messages API (/v1/messages, x-api-key header)
  - anything else   → uses OpenAI-compatible Chat Completions API (/v1/chat/completions)

The API key is NEVER logged, stored, or included in telemetry spans.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

_logger = logging.getLogger("adp.llm")

_EXTRACTION_SYSTEM_PROMPT = """\
You are a requirements analyst. Extract all business requirements from the provided text.

For each requirement you identify, return a JSON object with these exact fields:
- "statement": A clear, testable requirement statement (rewritten in imperative form if needed)
- "kind": One of "functional", "non_functional", "constraint", or "driver"
- "source_excerpt": The exact verbatim phrase or sentence from the source text that this \
requirement derives from (must be a substring of the input)
- "confidence": A float 0.0-1.0 indicating your confidence this is a genuine requirement
- "referenced_principles": A list of named principles, standards, or capabilities explicitly \
mentioned in the source text related to this requirement (empty list if none)

Return ONLY a JSON object with a single key "requirements" containing a list of requirement objects.
Do not include any text outside the JSON.
If no requirements are found, return {"requirements": []}."""


def _is_anthropic(base_url: str) -> bool:
    return "anthropic.com" in base_url.lower()


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers Claude sometimes adds."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.split("\n")
    inner_start = 1
    inner_end = len(lines) if lines[-1].strip() != "```" else len(lines) - 1
    return "\n".join(lines[inner_start:inner_end]).strip()


class LLMClient:
    """Async HTTP client for LLM endpoints — Anthropic or OpenAI-compatible."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key  # NEVER logged
        self._model = model
        self._is_anthropic = _is_anthropic(base_url)

    async def extract(
        self,
        source_text: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send extraction request using the built-in extraction system prompt."""
        _logger.info(
            json.dumps({
                "operation": "intake.llm_request",
                "model": self._model,
                "provider": "anthropic" if self._is_anthropic else "openai_compatible",
                "source_char_count": len(source_text),
                "correlation_id": correlation_id,
            })
        )
        if self._is_anthropic:
            return await self._call_anthropic(source_text)
        return await self._call_openai_compatible(source_text)

    async def chat(
        self,
        system: str,
        user: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a general chat request with caller-supplied system and user messages.

        Returns an OpenAI-compatible response dict so callers don't need to branch on provider.
        """
        _logger.info(
            json.dumps({
                "operation": "llm.chat_request",
                "model": self._model,
                "provider": "anthropic" if self._is_anthropic else "openai_compatible",
                "user_char_count": len(user),
                "correlation_id": correlation_id,
            })
        )
        if self._is_anthropic:
            return await self._call_anthropic_chat(system, user)
        return await self._call_openai_compatible_chat(system, user)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None = None,
        correlation_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Multi-turn, streaming, tool-use-capable chat (ADP-SPEC-041).

        `messages` follows the Anthropic Messages API content-block shape
        directly (each item is {"role": ..., "content": ...}, where content
        may be a plain string or a list of content blocks including
        tool_use/tool_result blocks for a multi-turn tool-calling loop) --
        deliberately not abstracted into a provider-neutral shape, since
        there is exactly one caller (adp.chat) so far; the OpenAI-compatible
        branch below translates from this same shape.

        Yields normalized event dicts, regardless of provider (mirrors how
        chat()/extract() already normalize their non-streaming responses to
        one shape):
          {"type": "text_delta", "text": str}
          {"type": "tool_use", "id": str, "name": str, "input": dict}
          {"type": "done", "stop_reason": str,
           "usage": {"prompt_tokens": int, "completion_tokens": int}}
        """
        _logger.info(
            json.dumps({
                "operation": "llm.chat_stream_request",
                "model": self._model,
                "provider": "anthropic" if self._is_anthropic else "openai_compatible",
                "message_count": len(messages),
                "tool_count": len(tools) if tools else 0,
                "correlation_id": correlation_id,
            })
        )
        if self._is_anthropic:
            async for event in self._stream_anthropic_chat(messages, system, tools):
                yield event
        else:
            async for event in self._stream_openai_compatible_chat(messages, system, tools):
                yield event

    async def _stream_anthropic_chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        input_tokens = 0
        output_tokens = 0
        stop_reason = "end_turn"
        # Anthropic streams a tool's input as incremental JSON string
        # fragments (input_json_delta) keyed by content-block index; a
        # tool_use event is only yielded once its block closes and the
        # accumulated fragment parses.
        tool_use_blocks: dict[int, dict[str, str]] = {}
        tool_json_fragments: dict[int, str] = {}

        async with httpx.AsyncClient() as client, client.stream(
            "POST", f"{self._base_url}/v1/messages",
            headers=headers, json=body, timeout=180.0,
        ) as response:
            response.raise_for_status()
            event_type: str | None = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                data = json.loads(line[len("data:"):].strip())

                if event_type == "message_start":
                    usage = data.get("message", {}).get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)
                elif event_type == "content_block_start":
                    block = data.get("content_block", {})
                    if block.get("type") == "tool_use":
                        idx = data["index"]
                        tool_use_blocks[idx] = {"id": block["id"], "name": block["name"]}
                        tool_json_fragments[idx] = ""
                elif event_type == "content_block_delta":
                    delta = data.get("delta", {})
                    idx = data["index"]
                    if delta.get("type") == "text_delta":
                        yield {"type": "text_delta", "text": delta["text"]}
                    elif delta.get("type") == "input_json_delta":
                        tool_json_fragments[idx] = (
                            tool_json_fragments.get(idx, "") + delta.get("partial_json", "")
                        )
                elif event_type == "content_block_stop":
                    idx = data["index"]
                    if idx in tool_use_blocks:
                        try:
                            parsed_input = json.loads(tool_json_fragments.get(idx) or "{}")
                        except json.JSONDecodeError:
                            parsed_input = {}
                        yield {
                            "type": "tool_use",
                            "id": tool_use_blocks[idx]["id"],
                            "name": tool_use_blocks[idx]["name"],
                            "input": parsed_input,
                        }
                elif event_type == "message_delta":
                    delta = data.get("delta", {})
                    if "stop_reason" in delta:
                        stop_reason = delta["stop_reason"]
                    usage = data.get("usage", {})
                    if "output_tokens" in usage:
                        output_tokens = usage["output_tokens"]

        yield {
            "type": "done",
            "stop_reason": stop_reason,
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
        }

    async def _stream_openai_compatible_chat(
        self,
        messages: list[dict[str, Any]],
        system: str,
        tools: list[dict[str, Any]] | None,
    ) -> AsyncIterator[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        # OpenAI streams a tool call's name/arguments incrementally across
        # several deltas, keyed by the call's position in the response.
        tool_calls: dict[int, dict[str, str]] = {}
        stop_reason = "stop"

        async with httpx.AsyncClient() as client, client.stream(
            "POST", f"{self._base_url}/v1/chat/completions",
            headers=headers, json=body, timeout=180.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                choice = (chunk.get("choices") or [{}])[0]
                delta = choice.get("delta", {})
                if delta.get("content"):
                    yield {"type": "text_delta", "text": delta["content"]}
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    entry = tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        entry["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        entry["name"] = fn["name"]
                    if fn.get("arguments"):
                        entry["arguments"] += fn["arguments"]
                if choice.get("finish_reason"):
                    stop_reason = choice["finish_reason"]

        for entry in tool_calls.values():
            try:
                parsed_input = json.loads(entry["arguments"] or "{}")
            except json.JSONDecodeError:
                parsed_input = {}
            yield {
                "type": "tool_use",
                "id": entry["id"],
                "name": entry["name"],
                "input": parsed_input,
            }

        yield {
            "type": "done",
            "stop_reason": stop_reason,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }

    async def _call_anthropic_chat(self, system: str, user: str) -> dict[str, Any]:
        """Call Anthropic Messages API with caller-supplied system/user prompts."""
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": 16000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/messages",
                headers=headers,
                json=body,
                timeout=180.0,
            )
        response.raise_for_status()
        raw = response.json()

        stop_reason = raw.get("stop_reason")
        if stop_reason and stop_reason != "end_turn":
            _logger.warning("llm.chat stop_reason=%s (possible truncation)", stop_reason)

        text_content = ""
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text_content = block["text"]
                break

        text_content = _strip_code_fence(text_content)

        usage = raw.get("usage", {})
        return {
            "choices": [{"message": {"content": text_content}}],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        }

    async def _call_openai_compatible_chat(self, system: str, user: str) -> dict[str, Any]:
        """Call OpenAI-compatible /v1/chat/completions with caller-supplied system/user prompts."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=120.0,
            )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    async def _call_anthropic(self, source_text: str) -> dict[str, Any]:
        """Call Anthropic Messages API; normalize response to OpenAI shape for parser."""
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self._model,
            "max_tokens": 4096,
            "system": _EXTRACTION_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Extract all requirements from the following text. "
                        "Respond ONLY with a JSON object containing a 'requirements' key."
                        f"\n\n---\n{source_text}\n---"
                    ),
                },
            ],
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/messages",
                headers=headers,
                json=body,
                timeout=120.0,
            )
        response.raise_for_status()
        raw = response.json()

        text_content = ""
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text_content = block["text"]
                break

        text_content = _strip_code_fence(text_content)

        usage = raw.get("usage", {})
        return {
            "choices": [{"message": {"content": text_content}}],
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        }

    async def _call_openai_compatible(self, source_text: str) -> dict[str, Any]:
        """Call OpenAI-compatible /v1/chat/completions endpoint."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extract all requirements from the following text:"
                        f"\n\n---\n{source_text}\n---"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=120.0,
            )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
