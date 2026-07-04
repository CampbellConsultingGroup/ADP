"""Unit tests for SVG generator and US2 override-rejection (T010, T011, T020, T021 — RED)."""

from __future__ import annotations

import inspect

import pytest

from adp.models import ArchitectureDescription, Element


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
def theme():
    from adp.theme.loader import ThemeLoader
    return ThemeLoader().load()


def test_design_to_svg_contains_theme_fill_color(theme):
    from adp.renderer.svg import design_to_svg

    design = _make_design([
        {"id": "ELM-001", "name": "API Gateway", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
    ])
    svg = design_to_svg(design, theme, "container")

    assert "#2874A6" in svg
    assert "<svg" in svg
    assert "</svg>" in svg


def test_two_designs_render_identical_element_colors(theme):
    """SC-001: same element kind → identical fill in both renderings."""
    from adp.renderer.svg import design_to_svg

    design1 = _make_design([
        {"id": "ELM-001", "name": "Alpha Gateway", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
    ])
    design2 = _make_design([
        {"id": "ELM-002", "name": "Beta Gateway", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
    ])
    svg1 = design_to_svg(design1, theme, "container")
    svg2 = design_to_svg(design2, theme, "container")

    assert "#2874A6" in svg1
    assert "#2874A6" in svg2


def test_svg_generator_has_no_override_parameters(theme):
    """ART-XII: design_to_svg must have zero style override params in its signature."""
    from adp.renderer.svg import design_to_svg

    param_names = set(inspect.signature(design_to_svg).parameters.keys())
    forbidden = {"style", "color", "fill", "stroke", "override", "custom_theme"}
    overlap = param_names & forbidden
    assert not overlap, f"design_to_svg must not accept override params: {overlap}"


def test_same_kind_same_output_regardless_of_content(theme):
    """SC-004: style is locked to kind — different element names, same fill."""
    from adp.renderer.svg import design_to_svg

    design_a = _make_design([
        {"id": "ELM-001", "name": "Service Alpha", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
    ])
    design_b = _make_design([
        {"id": "ELM-002", "name": "Service Beta", "kind": "container", "satisfies": [], "provenance": None},  # noqa: E501
    ])
    svg_a = design_to_svg(design_a, theme, "container")
    svg_b = design_to_svg(design_b, theme, "container")

    assert "#2874A6" in svg_a
    assert "#2874A6" in svg_b


def test_svg_all_four_element_kinds_use_theme_colors(theme):
    """Each element kind produces its locked theme fill in the SVG."""
    from adp.renderer.svg import design_to_svg

    expected = {
        "person":    ("#08427B", "context"),
        "system":    ("#1168BD", "context"),
        "container": ("#2874A6", "container"),
        "component": ("#85BBE0", "component"),
    }
    for kind, (fill, level) in expected.items():
        design = _make_design([
            {"id": "ELM-001", "name": f"Test {kind}", "kind": kind, "satisfies": [], "provenance": None},  # noqa: E501
        ])
        svg = design_to_svg(design, theme, level)
        assert fill in svg, f"Expected fill {fill} for kind {kind!r} not found in SVG"
