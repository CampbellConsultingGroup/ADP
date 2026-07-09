"""Unit tests for ThemeLoader — US3 theme validation + US4 versioning (T023-T025, T028)."""

from __future__ import annotations

import re

import pytest

from adp.theme.loader import ThemeLoader
from adp.theme.models import ThemeValidationError


def _minimal_valid_theme() -> dict:  # type: ignore[type-arg]
    return {
        "version": "1.0.0",
        "locked": True,
        "styles": {
            "person":    {"fill": "#08427B", "stroke": "#073B6F", "color": "#ffffff", "shape": "actor", "font_size": 14, "font_weight": "normal"},  # noqa: E501
            "system":    {"fill": "#1168BD", "stroke": "#0E5FA3", "color": "#ffffff", "shape": "box", "font_size": 14, "font_weight": "bold"},  # noqa: E501
            "container": {"fill": "#438DD5", "stroke": "#3C7FC0", "color": "#ffffff", "shape": "box", "font_size": 13, "font_weight": "normal"},  # noqa: E501
            "component": {"fill": "#85BBE0", "stroke": "#78A8CC", "color": "#000000", "shape": "box", "font_size": 12, "font_weight": "normal"},  # noqa: E501
        },
        "relationship_style": {"stroke": "#707070", "stroke_width": 1.5, "arrow_end": "open"},
    }


# US3 tests ────────────────────────────────────────────────────────────────────

def test_valid_theme_passes_validation():
    theme = ThemeLoader().load_and_validate()
    assert theme.locked is True
    assert theme.version == "1.0.1"


def test_theme_locked_false_rejected():
    data = _minimal_valid_theme()
    data["locked"] = False  # type: ignore[assignment]
    with pytest.raises(ThemeValidationError) as exc_info:
        ThemeLoader().validate_raw(data)
    # jsonschema "const: true" produces "True was expected" in its message
    msg = str(exc_info.value).lower()
    assert "expected" in msg or "locked" in msg


def test_theme_missing_element_kind_rejected():
    """Validate that missing required top-level fields are caught at schema level."""
    data = _minimal_valid_theme()
    del data["relationship_style"]  # required by JSON Schema
    with pytest.raises(ThemeValidationError):
        ThemeLoader().validate_raw(data)


def test_theme_invalid_style_shape_rejected():
    """Element style shape must be one of the enum values."""
    data = _minimal_valid_theme()
    data["styles"]["container"]["shape"] = "triangle"  # not in enum
    with pytest.raises(ThemeValidationError):
        ThemeLoader().validate_raw(data)


def test_theme_missing_required_field_rejected():
    data = _minimal_valid_theme()
    del data["relationship_style"]
    with pytest.raises(ThemeValidationError):
        ThemeLoader().validate_raw(data)


def test_load_returns_locked_theme_object():
    theme = ThemeLoader().load()
    assert hasattr(theme, "styles")
    assert "container" in theme.styles
    assert theme.styles["container"].fill == "#2874A6"


# US4 tests ────────────────────────────────────────────────────────────────────

def test_theme_version_is_semantic_version():
    theme = ThemeLoader().load()
    assert re.match(r"^\d+\.\d+\.\d+$", theme.version), f"Not semver: {theme.version}"
    assert theme.version == "1.0.1"  # regression anchor
