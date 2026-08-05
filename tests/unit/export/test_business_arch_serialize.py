"""Unit tests: pure serialization functions for business architecture export
(ADP-SPEC-044 T003). No I/O, no `exported_at` stamping -- that's added at
write time (T006/T010), not by these functions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from adp.business.models import BusinessCapability, BusinessDomain, ValueStream, ValueStreamStage
from adp.export.business_arch import (
    _serialize_capability,
    _serialize_domain,
    _serialize_stage,
    _serialize_value_stream,
)

_NOW = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


def _cap(**overrides) -> BusinessCapability:
    base = dict(
        id="cap-1", name="Risk Assessment", description="Evaluate risk", level=2,
        parent_id="cap-parent", position=0, created_at=_NOW, updated_at=_NOW,
        domain_id="domain-1", strategic_relevance=1, maturity_level=3,
    )
    base.update(overrides)
    return BusinessCapability(**base)


def test_serialize_capability_includes_all_fields() -> None:
    result = _serialize_capability(_cap())
    assert result == {
        "id": "cap-1", "name": "Risk Assessment", "description": "Evaluate risk",
        "level": 2, "parent_id": "cap-parent", "position": 0,
        "domain_id": "domain-1", "strategic_relevance": 1, "maturity_level": 3,
    }


def test_serialize_capability_unclassified_fields_are_explicit_null() -> None:
    result = _serialize_capability(
        _cap(domain_id=None, strategic_relevance=None, maturity_level=None)
    )
    assert result["domain_id"] is None
    assert result["strategic_relevance"] is None
    assert result["maturity_level"] is None
    # Explicit keys, not omitted.
    assert "domain_id" in result
    assert "strategic_relevance" in result
    assert "maturity_level" in result


def test_serialize_domain() -> None:
    domain = BusinessDomain(
        id="domain-1", name="Underwriting", scope_statement="...",
        classification="strategic", org_unit="Insurance Ops", risk_flags=[],
        created_at=_NOW, updated_at=_NOW,
    )
    result = _serialize_domain(domain)
    assert result == {
        "id": "domain-1", "name": "Underwriting", "scope_statement": "...",
        "classification": "strategic", "org_unit": "Insurance Ops", "risk_flags": [],
    }


def test_serialize_value_stream() -> None:
    vs = ValueStream(
        id="vs-1", name="Order-to-Cash", description="...", stakeholder="VP Sales",
        position=0, created_at=_NOW, updated_at=_NOW,
    )
    result = _serialize_value_stream(vs)
    assert result == {
        "id": "vs-1", "name": "Order-to-Cash", "description": "...",
        "stakeholder": "VP Sales", "position": 0,
    }


def test_serialize_stage_includes_linked_capability_ids_sorted() -> None:
    stage = ValueStreamStage(
        id="stage-1", value_stream_id="vs-1", name="Quote", description=None, position=0,
    )
    result = _serialize_stage(stage, linked_capability_ids=["cap-2", "cap-1"])
    assert result == {
        "id": "stage-1", "value_stream_id": "vs-1", "name": "Quote",
        "description": None, "position": 0,
        "linked_capability_ids": ["cap-1", "cap-2"],
    }


def test_serialize_stage_empty_links_is_empty_list_not_omitted() -> None:
    stage = ValueStreamStage(
        id="stage-1", value_stream_id="vs-1", name="Quote", description=None, position=0,
    )
    result = _serialize_stage(stage, linked_capability_ids=[])
    assert result["linked_capability_ids"] == []
    assert "linked_capability_ids" in result


def test_serialization_is_deterministic_across_calls() -> None:
    """Same input -> byte-identical JSON text (sorted keys), required for
    content-based change detection (research.md Decision 2) to work at all."""
    cap = _cap()
    text1 = json.dumps(_serialize_capability(cap), sort_keys=True)
    text2 = json.dumps(_serialize_capability(cap), sort_keys=True)
    assert text1 == text2
