"""Configurable LLM client for requirement extraction (ADP-SPEC-006).

Calls any OpenAI-compatible /v1/chat/completions endpoint.
The API key is NEVER logged, stored, or included in telemetry spans.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

_logger = logging.getLogger("adp.intake")

_SYSTEM_PROMPT = """\
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
If no requirements are found, return {"requirements": []}.\
"""


class LLMClient:
    """Async HTTP client for OpenAI-compatible LLM endpoints."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key  # NEVER logged
        self._model = model

    async def extract(
        self,
        source_text: str,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Send extraction request; return the raw parsed JSON response dict."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Extract all requirements from the following text:"
                    f"\n\n---\n{source_text}\n---"
                )},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 4096,
        }

        _logger.info(
            json.dumps({
                "operation": "intake.llm_request",
                "model": self._model,
                "source_char_count": len(source_text),
                "correlation_id": correlation_id,
            })
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=120.0,
            )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
