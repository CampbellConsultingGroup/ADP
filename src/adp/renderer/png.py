"""SVG → PNG conversion via cairosvg (no Java required)."""

from __future__ import annotations


def svg_to_png(svg_str: str) -> bytes:
    """Convert an SVG string to PNG bytes using cairosvg.

    Raises RuntimeError if cairosvg raises (e.g., libcairo not installed).
    """
    try:
        import cairosvg  # lazy import — optional system dep
        result = cairosvg.svg2png(bytestring=svg_str.encode("utf-8"))
        if result is None:
            raise RuntimeError("cairosvg.svg2png returned None")
        return result  # type: ignore[return-value]
    except Exception as exc:
        raise RuntimeError(f"PNG conversion failed: {exc}") from exc
