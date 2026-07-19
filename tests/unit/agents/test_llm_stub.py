"""Unit tests for the Agent Review toolkit's shared no-API-key stub LLM client
(ADP-SPEC-039). Replaces the ad hoc _StubLLMClient duplicated in intake.py/recommend.py.
"""

from __future__ import annotations

from adp.agents.llm_stub import StubLLMClient
from adp.llm.client import LLMClient


def test_stub_is_an_llm_client():
    stub = StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    assert isinstance(stub, LLMClient)


async def test_stub_chat_returns_empty_choices():
    stub = StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    result = await stub.chat(system="system prompt", user="user prompt")
    assert result == {"choices": [], "usage": {}}


async def test_stub_extract_returns_empty_choices():
    stub = StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    result = await stub.extract("some source text")
    assert result == {"choices": [], "usage": {}}
