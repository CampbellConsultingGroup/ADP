"""Tests for individual critics — citations, structural check, advisory handling (US1/US3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from adp.knowledge.schema import CitationRef
from adp.models import ArchitectureDescription, Element, ElementKind, Requirement
from adp.validation.critics import structural_critic
from adp.validation.models import FindingSeverity
from adp.validation.telemetry import ValidationTelemetry
from tests.knowledge.conftest import make_item

_NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _mock_telemetry() -> MagicMock:
    t = MagicMock(spec=ValidationTelemetry)
    t.emit_span = MagicMock()
    return t


def _make_llm_response(score: float, findings: list[dict]) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps({"score": score, "findings": findings})}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }


def _make_kr(item_id: str = "STD-001", kind: str = "standard") -> MagicMock:
    item = MagicMock()
    item.kind = kind
    item.title = f"Item {item_id}"
    item.full_text = f"Content of {item_id}"

    entry = MagicMock()
    entry.item = item
    entry.citation = CitationRef(item_id=item_id, item_version="2.0.0")
    entry.relevance_score = 0.9

    kr = MagicMock()
    kr.hybrid_search = AsyncMock(
        return_value=MagicMock(items=[entry])
    )
    kr.resolve_citation = AsyncMock(return_value=make_item(item_id))
    return kr


def _make_design(orphan: bool = False, dangling: bool = False) -> ArchitectureDescription:
    req = Requirement(id="REQ-001", title="R", description="desc")
    elm1 = Element(
        id="ELM-001", name="A", kind=ElementKind.CONTAINER,
        satisfies=[] if orphan else ["REQ-001"]
    )
    elm2 = Element(id="ELM-002", name="B", kind=ElementKind.CONTAINER, satisfies=["REQ-001"])

    if dangling:
        # Bypass ADP-SPEC-001 referential integrity validation to test structural critic
        # (structural critic is designed to catch what should never reach the model in production)
        from adp.models import Relationship as _R
        rel = _R.model_construct(id="REL-001", source="ELM-001", target="ELM-999")
        design = ArchitectureDescription.model_construct(
            schema_version="1.0.0", id="DESIGN-001", title="Test",
            requirements=[req], elements=[elm1, elm2], relationships=[rel],
            options=[], findings=[], verdicts=[], audit_log=[],
            created_at=_NOW, updated_at=_NOW,
        )
        return design

    return ArchitectureDescription(
        schema_version="1.0.0", id="DESIGN-001", title="Test",
        requirements=[req], elements=[elm1, elm2], relationships=[],
        created_at=_NOW, updated_at=_NOW,
    )


# ── US3: Structural critic ────────────────────────────────────────────────────

def test_structural_critic_detects_orphan_element() -> None:
    """Orphan element (empty satisfies) → critical finding."""
    design = _make_design(orphan=True)
    output = structural_critic(design, "op-001", _mock_telemetry())
    critical = [f for f in output.findings if f.severity == FindingSeverity.CRITICAL]
    assert len(critical) >= 1
    orphan_findings = [
        f for f in critical
        if "orphan" in f.description.lower() or "satisfies" in f.description.lower()
    ]
    assert len(orphan_findings) >= 1
    assert orphan_findings[0].element_id == "ELM-001"


def test_structural_critic_detects_dangling_reference() -> None:
    """Dangling relationship target → critical finding."""
    design = _make_design(dangling=True)
    output = structural_critic(design, "op-001", _mock_telemetry())
    dangling = [
        f for f in output.findings
        if "dangling" in f.description.lower() or "ELM-999" in f.description
    ]
    assert len(dangling) >= 1
    assert dangling[0].severity == FindingSeverity.CRITICAL


def test_structural_critic_clean_design_returns_no_findings() -> None:
    """A structurally correct design produces no findings."""
    design = _make_design()
    output = structural_critic(design, "op-001", _mock_telemetry())
    assert output.findings == []
    assert output.critic_name == "structural"


def test_structural_critic_emits_span() -> None:
    """Structural critic always emits a telemetry span."""
    telemetry = _mock_telemetry()
    design = _make_design()
    structural_critic(design, "op-001", telemetry)
    telemetry.emit_span.assert_called_once()


# ── US1: LLM critic citation tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_standards_critic_produces_cited_findings() -> None:
    """standards_critic findings carry resolvable CitationRef."""
    from adp.validation.critics import standards_critic

    mock_llm = MagicMock()
    mock_llm.extract = AsyncMock(return_value=_make_llm_response(
        0.5,
        [{"element_id": "ELM-001", "description": "Missing TLS", "cited_id": "STD-001"}],
    ))
    mock_kr = _make_kr("STD-001", "standard")

    output = await standards_critic(
        _make_design(), mock_kr, mock_llm, _mock_telemetry(), "op-001"
    )

    assert len(output.findings) >= 1
    assert output.findings[0].citation is not None
    assert output.findings[0].citation.item_id == "STD-001"


@pytest.mark.asyncio
async def test_principles_critic_produces_cited_findings() -> None:
    from adp.validation.critics import principles_critic

    mock_llm = MagicMock()
    mock_llm.extract = AsyncMock(return_value=_make_llm_response(
        0.25,
        [{"element_id": "ELM-002", "description": "Violates principle",
          "cited_id": "PRIN-001"}],
    ))
    mock_kr = _make_kr("PRIN-001", "principle")

    output = await principles_critic(
        _make_design(), mock_kr, mock_llm, _mock_telemetry(), "op-001"
    )
    assert len(output.findings) >= 1
    assert output.findings[0].citation is not None


@pytest.mark.asyncio
async def test_pattern_fit_critic_produces_cited_findings() -> None:
    from adp.validation.critics import pattern_fit_critic

    mock_llm = MagicMock()
    mock_llm.extract = AsyncMock(return_value=_make_llm_response(
        0.5,
        [{"element_id": "ELM-001", "description": "Pattern mismatch", "cited_id": "PAT-001"}],
    ))
    mock_kr = _make_kr("PAT-001", "pattern")

    output = await pattern_fit_critic(
        _make_design(), mock_kr, mock_llm, _mock_telemetry(), "op-001"
    )
    assert len(output.findings) >= 1
    assert output.findings[0].citation is not None


@pytest.mark.asyncio
async def test_consistency_critic_produces_cited_findings() -> None:
    from adp.validation.critics import consistency_critic

    mock_llm = MagicMock()
    mock_llm.extract = AsyncMock(return_value=_make_llm_response(
        0.5,
        [{"element_id": None, "description": "Inconsistent with prior", "cited_id": "PS-001"}],
    ))
    mock_kr = _make_kr("PS-001", "prior_solution")

    output = await consistency_critic(
        _make_design(), mock_kr, mock_llm, _mock_telemetry(), "op-001"
    )
    assert len(output.findings) >= 1
    assert output.findings[0].citation is not None


@pytest.mark.asyncio
async def test_uncited_finding_is_advisory() -> None:
    """Finding whose cited_id is not in the knowledge list → advisory severity."""
    from adp.validation.critics import standards_critic

    mock_llm = MagicMock()
    mock_llm.extract = AsyncMock(return_value=_make_llm_response(
        0.0,
        [{"element_id": "ELM-001", "description": "Hallucinated citation", "cited_id": "FAKE-999"}],
    ))
    mock_kr = _make_kr("STD-001", "standard")  # FAKE-999 not in result

    output = await standards_critic(
        _make_design(), mock_kr, mock_llm, _mock_telemetry(), "op-001"
    )

    advisory_findings = [f for f in output.findings if f.severity == FindingSeverity.ADVISORY]
    assert len(advisory_findings) >= 1
    assert advisory_findings[0].citation is None
