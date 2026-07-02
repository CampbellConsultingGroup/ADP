"""RenderOrchestrator: drives the full render pipeline for a design."""

from __future__ import annotations

import base64

from adp.renderer.dsl import design_to_dsl
from adp.renderer.png import svg_to_png
from adp.renderer.svg import design_to_svg
from adp.theme.loader import ThemeLoader
from adp.theme.models import C4Level, RenderResult


class RenderOrchestrator:
    """Orchestrates the full render pipeline: model → DSL + SVG + PNG."""

    def __init__(
        self,
        design_store: object,
        theme_loader: ThemeLoader | None = None,
    ) -> None:
        self._store = design_store
        self._theme_loader = theme_loader or ThemeLoader()

    def render(self, design_id: str, level: C4Level) -> RenderResult:
        """Render a design at the given C4 level.

        Returns RenderResult with DSL, SVG, and base64-encoded PNG.
        Raises ThemeValidationError if the theme is invalid.
        Raises KeyError/AttributeError if design_id is not found.
        """
        theme = self._theme_loader.load_and_validate()

        design = self._store.get(design_id)  # type: ignore[attr-defined]
        if design is None:
            raise KeyError(f"Design {design_id!r} not found")

        dsl = design_to_dsl(design, theme, level)
        svg = design_to_svg(design, theme, level)
        png = svg_to_png(svg)
        png_b64 = base64.b64encode(png).decode("utf-8")

        return RenderResult(
            design_id=design_id,
            level=level,
            dsl=dsl,
            svg=svg,
            png_base64=png_b64,
        )
