"""Configurable LLM client — supports Anthropic and OpenAI-compatible endpoints.

Detects provider from base_url:
  - "anthropic.com" → uses Anthropic Messages API (/v1/messages, x-api-key header)
  - anything else   → uses OpenAI-compatible Chat Completions API (/v1/chat/completions)

The API key is NEVER logged, stored, or included in telemetry spans.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

_logger = logging.getLogger("adp.intake")

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
        """Send extraction request; normalize response to OpenAI-compatible shape."""
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

        # Normalize Anthropic response → OpenAI-compatible shape for LLMResponseParser
        text_content = ""
        for block in raw.get("content", []):
            if block.get("type") == "text":
                text_content = block["text"]
                break

        # Strip markdown code fences Claude sometimes wraps JSON in (```json...```)
        stripped = text_content.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            text_content = "\n".join(lines[1:end]).strip()

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
