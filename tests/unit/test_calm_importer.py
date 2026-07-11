"""Unit tests for the CALM pattern importer (ADP-SPEC-022 T002-T009)."""

from __future__ import annotations

import pytest

from adp.calm.importer import (
    _extract_pattern_name,
    _slugify,
    parse_calm_document,
)
from adp.knowledge.schema import KnowledgeType


def _calm(nodes=None, relationships=None, **extras) -> dict:
    doc: dict = {}
    if nodes is not None:
        doc["nodes"] = nodes
    if relationships is not None:
        doc["relationships"] = relationships
    doc.update(extras)
    return doc


def _node(uid: str, node_type: str = "service", name: str = "My Service", description: str = "A service") -> dict:  # noqa: E501
    return {"unique-id": uid, "node-type": node_type, "name": name, "description": description}


def _rel(uid: str, source: str, dest: str, protocol: str = "HTTPS") -> dict:
    return {
        "unique-id": uid,
        "relationship-type": "connects",
        "connects": {"source-node": source, "destination-node": dest, "protocol": protocol},
    }


# ── T002: name extraction from $id ───────────────────────────────────────────

def test_parse_calm_document_extracts_name_from_id():
    data = _calm(
        nodes=[_node("N-001")],
        relationships=[],
        **{"$id": "https://example.com/patterns/api-gateway-pattern"},
    )
    item, _ = parse_calm_document(data)
    assert "api-gateway-pattern" in item.title.lower() or "api gateway" in item.title.lower()


def test_extract_pattern_name_prefers_explicit_name_over_dollar_id():
    # Precedence is title > name > $id: an explicit name field beats the URL slug.
    data = {"$id": "https://example.com/my-cool-pattern", "name": "Other Name"}
    assert _extract_pattern_name(data, "fallback") == "Other Name"


def test_extract_pattern_name_prefers_title_over_name():
    data = {"title": "Titled Pattern", "name": "Other Name"}
    assert _extract_pattern_name(data, "fallback") == "Titled Pattern"


def test_extract_pattern_name_uses_dollar_id_when_no_title_or_name():
    data = {"$id": "https://example.com/my-cool-pattern"}
    # $id segment "my-cool-pattern" is title-cased to "My Cool Pattern"
    assert _extract_pattern_name(data, "fallback") == "My Cool Pattern"


def test_extract_pattern_name_falls_back_to_name_field():
    data = {"name": "Circuit Breaker Pattern"}
    assert _extract_pattern_name(data, "fallback") == "Circuit Breaker Pattern"


def test_extract_pattern_name_falls_back_to_first_node_name():
    data = {"nodes": [{"name": "API Gateway", "unique-id": "N-001"}]}
    assert _extract_pattern_name(data, "fallback") == "API Gateway"


def test_extract_pattern_name_uses_fallback_when_nothing_available():
    assert _extract_pattern_name({}, "Imported CALM Pattern") == "Imported CALM Pattern"


# ── T003: full_text includes node names and types ────────────────────────────

def test_parse_calm_document_generates_full_text_with_nodes():
    data = _calm(nodes=[
        _node("N-001", "actor", "Alice", "End user"),
        _node("N-002", "system", "Payment API", "Handles payments"),
    ])
    _, full_text = parse_calm_document(data)
    assert "Alice" in full_text
    assert "Payment API" in full_text
    assert "actor" in full_text
    assert "system" in full_text


# ── T004: full_text includes relationship source/destination ─────────────────

def test_parse_calm_document_generates_full_text_with_relationships():
    data = _calm(
        nodes=[_node("N-001"), _node("N-002")],
        relationships=[_rel("REL-001", "N-001", "N-002", "HTTPS")],
    )
    _, full_text = parse_calm_document(data)
    assert "N-001" in full_text
    assert "N-002" in full_text


# ── T005: kind is reference_architecture ────────────────────────────────────

def test_parse_calm_document_sets_kind_reference_architecture():
    data = _calm(nodes=[_node("N-001")])
    item, _ = parse_calm_document(data)
    assert item.kind == KnowledgeType.REFERENCE_ARCHITECTURE


# ── T006: metadata includes counts ───────────────────────────────────────────

def test_parse_calm_document_metadata_includes_counts():
    data = _calm(
        nodes=[_node("N-001"), _node("N-002")],
        relationships=[_rel("REL-001", "N-001", "N-002")],
    )
    item, _ = parse_calm_document(data)
    assert item.metadata["calm_node_count"] == 2
    assert item.metadata["calm_relationship_count"] == 1


# ── T007: non-dict input raises ValueError ───────────────────────────────────

def test_parse_calm_document_invalid_json_raises():
    with pytest.raises(ValueError, match="CALM document must be a dict"):
        parse_calm_document("not a dict")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        parse_calm_document(None)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        parse_calm_document([1, 2, 3])  # type: ignore[arg-type]


# ── T008: no nodes key still succeeds ────────────────────────────────────────

def test_parse_calm_document_no_nodes_still_succeeds():
    data = {"$id": "https://example.com/empty-pattern"}
    item, full_text = parse_calm_document(data)
    assert item is not None
    assert item.kind == KnowledgeType.REFERENCE_ARCHITECTURE
    assert item.metadata["calm_node_count"] == 0
    assert item.metadata["calm_relationship_count"] == 0


# ── T009: item ID is stable (deterministic) ──────────────────────────────────

def test_parse_calm_document_upsert_id_is_stable():
    data = _calm(nodes=[_node("N-001")], **{"$id": "https://example.com/stable-pattern"})
    item1, _ = parse_calm_document(data)
    item2, _ = parse_calm_document(data)
    assert item1.id == item2.id
    assert item1.id.startswith("calm-")


# ── Slugify helper ────────────────────────────────────────────────────────────

def test_slugify_lowercases_and_replaces_spaces():
    assert _slugify("API Gateway Pattern") == "api-gateway-pattern"


def test_slugify_truncates_to_60():
    long = "a" * 100
    assert len(_slugify(long)) <= 60


def test_slugify_strips_leading_trailing_dashes():
    assert not _slugify("  hello  ").startswith("-")
    assert not _slugify("  hello  ").endswith("-")


# ── Full text truncation ──────────────────────────────────────────────────────

def test_generate_full_text_truncates_at_10000_chars():
    nodes = [_node(f"N-{i:03d}", description="x" * 500) for i in range(30)]
    data = _calm(nodes=nodes)
    _, full_text = parse_calm_document(data)
    assert len(full_text) <= 10_000
