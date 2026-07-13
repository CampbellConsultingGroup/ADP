"""WCAG 2.1 relative luminance and contrast ratio — pure Python, no external deps."""

from __future__ import annotations


def _linearize(c: float) -> float:
    """Convert sRGB channel (0-1) to linear light value per WCAG 2.1."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Compute WCAG 2.1 relative luminance for a #RRGGBB hex color."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255
    g = int(h[2:4], 16) / 255
    b = int(h[4:6], 16) / 255
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def compute_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return the WCAG 2.1 contrast ratio between two #RRGGBB hex colors.

    A ratio of 4.5:1 or higher satisfies WCAG AA for normal text (SC-005).
    Maximum possible ratio is 21:1 (black on white).
    """
    l1 = _relative_luminance(fg_hex)
    l2 = _relative_luminance(bg_hex)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
