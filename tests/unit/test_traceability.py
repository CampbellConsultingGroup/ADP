"""Unit tests for TraceabilityGenerator (T014-T016 — RED before T018)."""

from __future__ import annotations

from adp.models import ArchitectureDescription, Element


def _make_design(elements: list[dict]) -> ArchitectureDescription:  # type: ignore[return]
    return ArchitectureDescription.model_construct(
        schema_version="1.0.0",
        id="D-001",
        title="Test Design",
        created_at="2026-07-02T00:00:00Z",
        updated_at="2026-07-02T00:00:00Z",
        elements=[Element.model_validate(e) for e in elements],
        requirements=[],
        relationships=[],
    )


def test_matrix_contains_all_elements():
    from adp.docs.traceability import TraceabilityGenerator

    design = _make_design([
        {"id": "ELM-001", "name": "A", "kind": "container", "satisfies": ["REQ-001"], "provenance": None},  # noqa: E501
        {"id": "ELM-002", "name": "B", "kind": "person", "satisfies": [], "provenance": None},
        {"id": "ELM-003", "name": "C", "kind": "system", "satisfies": [], "provenance": None},
    ])
    result = TraceabilityGenerator().generate(design)

    assert result.total_elements == 3
    assert len(result.entries) == 3
    ids = {e.element_id for e in result.entries}
    assert ids == {"ELM-001", "ELM-002", "ELM-003"}


def test_orphan_elements_flagged():
    from adp.docs.traceability import TraceabilityGenerator

    design = _make_design([
        {"id": "ELM-001", "name": "A", "kind": "container", "satisfies": ["REQ-001"], "provenance": None},  # noqa: E501
        {"id": "ELM-002", "name": "B", "kind": "person", "satisfies": [], "provenance": None},
    ])
    result = TraceabilityGenerator().generate(design)

    assert result.orphan_count == 1
    by_id = {e.element_id: e for e in result.entries}
    assert by_id["ELM-001"].is_orphan is False
    assert by_id["ELM-002"].is_orphan is True


def test_matrix_is_deterministic():
    from adp.docs.traceability import TraceabilityGenerator

    design = _make_design([
        {"id": "ELM-002", "name": "B", "kind": "person", "satisfies": [], "provenance": None},
        {"id": "ELM-001", "name": "A", "kind": "container", "satisfies": ["REQ-001"], "provenance": None},  # noqa: E501
    ])
    gen = TraceabilityGenerator()
    r1 = gen.generate(design)
    r2 = gen.generate(design)
    assert [e.element_id for e in r1.entries] == [e.element_id for e in r2.entries]
    # entries sorted by element_id
    assert r1.entries[0].element_id == "ELM-001"
    assert r1.entries[1].element_id == "ELM-002"


def test_provenance_captured():
    from adp.docs.traceability import TraceabilityGenerator

    design = _make_design([
        {"id": "ELM-001", "name": "A", "kind": "container", "satisfies": ["REQ-001"], "provenance": "OPT-001"},  # noqa: E501
    ])
    result = TraceabilityGenerator().generate(design)
    assert result.entries[0].provenance == "OPT-001"
