"""Tests for intake framing (business problem + desired outcome) flowing into
recommendation generation (ADP-zg3.3)."""

from __future__ import annotations

from types import SimpleNamespace

from adp.eval.fakes import NoOpTelemetry
from adp.recommendation.prompts import generation_user_prompt
from adp.recommendation.steps import generate_step

# ── prompt builder ────────────────────────────────────────────────────────────

def test_generation_prompt_includes_framing_when_present():
    prompt = generation_user_prompt(
        "- [REQ-1] fast checkout", "(kb)", 3,
        business_problem="Peak checkout latency loses sales.",
        desired_outcome="Sub-second checkout at 10k users.",
    )
    assert "BUSINESS PROBLEM:" in prompt
    assert "Peak checkout latency loses sales." in prompt
    assert "DESIRED OUTCOME:" in prompt
    assert "Sub-second checkout at 10k users." in prompt


def test_generation_prompt_omits_framing_when_absent():
    prompt = generation_user_prompt("- [REQ-1] fast checkout", "(kb)", 3)
    assert "BUSINESS PROBLEM:" not in prompt
    assert "DESIRED OUTCOME:" not in prompt


# ── generate_step threads state framing into the prompt ───────────────────────

class _CapturingLLM:
    _model = "test-model"

    def __init__(self) -> None:
        self.user_prompt = ""

    async def chat(self, system: str, user: str, correlation_id: str | None = None) -> dict:
        self.user_prompt = user
        return {
            "choices": [{"message": {"content": '{"options": []}'}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


async def test_generate_step_passes_design_framing_to_prompt():
    llm = _CapturingLLM()
    state = {
        "operation_id": "op",
        "requirements": [SimpleNamespace(id="REQ-1", description="fast checkout")],
        "retrieved_knowledge": [],
        "reuse_candidates": [],
        "business_problem": "Peak checkout latency loses sales.",
        "desired_outcome": "Sub-second checkout at 10k users.",
    }
    await generate_step(state, llm=llm, telemetry=NoOpTelemetry())
    assert "BUSINESS PROBLEM:" in llm.user_prompt
    assert "Peak checkout latency loses sales." in llm.user_prompt
    assert "DESIRED OUTCOME:" in llm.user_prompt
