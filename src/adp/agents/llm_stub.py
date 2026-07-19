"""Shared no-API-key fallback LLM client for the Agent Review toolkit (ADP-SPEC-039).

Replaces the ad hoc `_StubLLMClient` classes duplicated in
`adp.api.routers.intake` and `adp.api.routers.recommend` -- both are updated
to import this instead of redefining it locally.
"""

from __future__ import annotations

from typing import Any

from adp.llm.client import LLMClient


class StubLLMClient(LLMClient):
    """Returns an empty choice list for both extract() and chat().

    Used when no LLM API key is configured (local/dev). An empty result is
    a legitimate "nothing generated" outcome, distinct from an operation
    that fails because a configured LLM call errored (FR-021, ADP-SPEC-039).
    """

    async def extract(
        self, source_text: str, correlation_id: str | None = None
    ) -> dict[str, Any]:  # type: ignore[override]
        return {"choices": [], "usage": {}}

    async def chat(
        self, system: str, user: str, correlation_id: str | None = None
    ) -> dict[str, Any]:  # type: ignore[override]
        return {"choices": [], "usage": {}}
