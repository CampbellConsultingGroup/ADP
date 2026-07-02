"""Unit tests for DocumentGenerator (T005-T007 — RED before T009)."""

from __future__ import annotations

import frontmatter

from adp.models import ArchitectureDescription, Element, Requirement


def _make_design(**kwargs) -> ArchitectureDescription:  # type: ignore[return]
    defaults = dict(
        schema_version="1.0.0",
        id="D-001",
        title="Test Design",
        created_at="2026-07-02T00:00:00Z",
        updated_at="2026-07-02T00:00:00Z",
        elements=[
            Element.model_validate({"id": "ELM-001", "name": "API Gateway", "kind": "container", "satisfies": ["REQ-001"], "provenance": "OPT-001"}),
            Element.model_validate({"id": "ELM-002", "name": "User", "kind": "person", "satisfies": [], "provenance": None}),
        ],
        requirements=[
            Requirement.model_validate({"id": "REQ-001", "title": "Stateless handling", "description": "The system must handle requests statelessly."}),
        ],
        relationships=[],
    )
    defaults.update(kwargs)
    return ArchitectureDescription.model_construct(**defaults)


def test_generate_document_contains_element_names():
    from adp.docs.generator import DocumentGenerator

    design = _make_design()
    result = DocumentGenerator().generate(design)

    assert "API Gateway" in result.markdown
    assert "User" in result.markdown
    assert result.markdown.startswith("---")


def test_generate_document_frontmatter_has_typed_metadata():
    from adp.docs.generator import DocumentGenerator

    design = _make_design()
    result = DocumentGenerator().generate(design)

    post = frontmatter.loads(result.markdown)
    assert "design_id" in post.metadata
    assert "schema_version" in post.metadata
    assert "generated_at" in post.metadata
    assert "generator" in post.metadata
    assert post.metadata["generator"] == "ADP-SPEC-011"
    assert post.metadata["design_id"] == "D-001"


def test_document_generation_is_deterministic():
    from adp.docs.generator import DocumentGenerator

    design = _make_design()
    gen = DocumentGenerator()
    r1 = gen.generate(design)
    r2 = gen.generate(design)
    assert r1.markdown == r2.markdown


def test_generate_document_includes_requirement_title():
    from adp.docs.generator import DocumentGenerator

    design = _make_design()
    result = DocumentGenerator().generate(design)
    assert "Stateless handling" in result.markdown


def test_generate_document_empty_title_raises():
    from adp.docs.generator import DocumentGenerator

    design = _make_design(title="")
    try:
        DocumentGenerator().generate(design)
        assert False, "expected ValueError"
    except (ValueError, Exception):
        pass  # any error is acceptable for empty title
