"""Tests for recommendation generation without knowledge base (ADP-SPEC-019 US1)."""

from __future__ import annotations

from adp.recommendation.models import SolutionOption


def test_generation_prompt_no_kb_does_not_require_citations():
    """With empty KB, the prompt must NOT mandate citations (T002)."""
    from adp.recommendation.prompts import generation_user_prompt

    prompt = generation_user_prompt("REQ-001: Scalability", "", 3, has_knowledge=False)
    assert "cite at least one knowledge item" not in prompt.lower()
    assert "MUST cite" not in prompt


def test_generation_prompt_with_kb_includes_knowledge():
    """With KB entries, the prompt includes the knowledge and grounding instruction."""
    from adp.recommendation.prompts import generation_user_prompt

    prompt = generation_user_prompt("REQ-001: Scalability", "KB-001: Microservices", 3, has_knowledge=True)  # noqa: E501
    assert "KB-001" in prompt


async def test_validate_citations_requirements_only_not_advisory():
    """Options with knowledge_source='requirements_only' must NOT be marked advisory (T003)."""
    from unittest.mock import AsyncMock, MagicMock

    from adp.recommendation.steps import validate_citations_step

    opt = SolutionOption(
        option_id="OPT-001", operation_id="OP-001",
        rank=1, title="Test Option", rationale="...",
    )
    opt.knowledge_source = "requirements_only"
    opt.grounded_on = []  # no citations — but should NOT be advisory

    mock_kr = MagicMock()
    mock_kr.resolve_citation = AsyncMock(return_value=None)

    state = {
        "operation_id": "OP-001",
        "validated_options": [],
        "ranked_options": [opt],
        "correlation_id": None,
    }
    from adp.recommendation.telemetry import RecommendationTelemetry
    result = await validate_citations_step(state, knowledge_retrieval=mock_kr, telemetry=RecommendationTelemetry())  # noqa: E501
    validated = result["validated_options"]
    assert len(validated) == 1
    assert validated[0].advisory is False, "requirements_only options must never be marked advisory"
