"""Unit tests for WCAG contrast ratio and SC-005 regression guard (T029, T031)."""

from __future__ import annotations

import pytest

from adp.theme.contrast import compute_contrast_ratio
from adp.theme.loader import ThemeLoader


# T031 — known-value tests for the WCAG formula

def test_compute_contrast_ratio_black_on_white():
    ratio = compute_contrast_ratio("#ffffff", "#000000")
    assert abs(ratio - 21.0) < 0.1, f"Expected ~21:1, got {ratio:.2f}"


def test_compute_contrast_ratio_person_element():
    """White on #08427B — should be ~10.9:1."""
    ratio = compute_contrast_ratio("#ffffff", "#08427B")
    assert 10.0 <= ratio <= 12.0, f"Expected 10-12:1, got {ratio:.2f}"


def test_compute_contrast_ratio_container_element():
    """White on #2874A6 — updated container fill; should be ~5.0-5.2:1."""
    ratio = compute_contrast_ratio("#ffffff", "#2874A6")
    assert 4.5 <= ratio <= 5.5, f"Expected 4.5-5.5:1, got {ratio:.2f}"


def test_compute_contrast_ratio_symmetric():
    """Contrast ratio is symmetric — order of fg/bg doesn't matter."""
    r1 = compute_contrast_ratio("#ffffff", "#000000")
    r2 = compute_contrast_ratio("#000000", "#ffffff")
    assert abs(r1 - r2) < 0.001


# T029 — SC-005 CI regression guard

def test_theme_wcag_aa_contrast_sc005():
    """All element kinds in the locked theme must meet WCAG AA (≥ 4.5:1)."""
    theme = ThemeLoader().load()
    for kind, style in theme.styles.items():
        ratio = compute_contrast_ratio(style.color, style.fill)
        assert ratio >= 4.5, (
            f"{kind}: contrast ratio {ratio:.2f}:1 is below WCAG AA minimum 4.5:1 "
            f"(text={style.color!r} on fill={style.fill!r})"
        )
