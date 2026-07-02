"""Unit tests for the Structurizr DSL generator (T009 — RED before T013)."""

from __future__ import annotations

import pytest

from adp.models import ArchitectureDescription, Element, ElementKind


def _make_design(elements: list[dict]) -> ArchitectureDescription:  # type: ignore[type-arg]
    return ArchitectureDescription.model_construct(
        schema_version="1.0.0",
        id="D-001",
        title="Test Design",
        version=1,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
        elements=[Element.model_validate(e) for e in elements],
        relationships=[],
        requirements=[],
        audit_log=[],
    )


@pytest.fixture()
def mock_theme():
    from adp.theme.loader import ThemeLoader
    return ThemeLoader().load()


def test_design_to_dsl_contains_element_names(mock_theme):
    from adp.renderer.dsl import design_to_dsl

    design = _make_design([
        {"id": "ELM-001", "name": "Web App", "kind": "system", "satisfies": [], "provenance": None},
        {"id": "ELM-002", "name": "API Gateway", "kind": "container", "satisfies": [], "provenance": None},
    ])
    dsl = design_to_dsl(design, mock_theme, "container")

    assert "Web App" in dsl
    assert "API Gateway" in dsl
    assert "workspace" in dsl
    assert "#2874A6" in dsl  # container fill from theme — dynamic, not hardcoded


def test_design_to_dsl_is_deterministic(mock_theme):
    from adp.renderer.dsl import design_to_dsl

    design = _make_design([
        {"id": "ELM-001", "name": "Svc A", "kind": "container", "satisfies": [], "provenance": None},
        {"id": "ELM-002", "name": "Svc B", "kind": "container", "satisfies": [], "provenance": None},
    ])
    assert design_to_dsl(design, mock_theme, "container") == design_to_dsl(design, mock_theme, "container")


def test_design_to_dsl_filters_by_level(mock_theme):
    from adp.renderer.dsl import design_to_dsl

    design = _make_design([
        {"id": "ELM-001", "name": "Person A", "kind": "person", "satisfies": [], "provenance": None},
        {"id": "ELM-002", "name": "Container X", "kind": "container", "satisfies": [], "provenance": None},
    ])
    context_dsl = design_to_dsl(design, mock_theme, "context")
    container_dsl = design_to_dsl(design, mock_theme, "container")

    assert "Person A" in context_dsl
    assert "Container X" not in context_dsl
    assert "Container X" in container_dsl
