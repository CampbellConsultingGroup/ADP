"""RenderOrchestrator: drives the full render pipeline for a design."""

from __future__ import annotations

import base64
import inspect

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

    async def _get_design(self, design_id: str) -> object:
        """Fetch design, awaiting if the store's get() is a coroutine."""
        try:
            result = self._store.get(design_id)  # type: ignore[attr-defined]
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:
            if "NotFound" in type(exc).__name__ or "not found" in str(exc).lower():
                raise KeyError(f"Design {design_id!r} not found") from exc
            raise

    def render(self, design_id: str, level: C4Level) -> RenderResult:
        """Sync render — only works when store.get() is synchronous (tests/mocks)."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self.arender(design_id, level))

    async def arender(self, design_id: str, level: C4Level) -> RenderResult:
        """Async render — preferred path when store.get() is a coroutine (DesignStore)."""
        theme = self._theme_loader.load_and_validate()

        design = await self._get_design(design_id)
        if design is None:
            raise KeyError(f"Design {design_id!r} not found")

        dsl = design_to_dsl(design, theme, level)  # type: ignore[arg-type]
        svg = design_to_svg(design, theme, level)  # type: ignore[arg-type]
        png = svg_to_png(svg)
        png_b64 = base64.b64encode(png).decode("utf-8")

        return RenderResult(
            design_id=design_id,
            level=level,
            dsl=dsl,
            svg=svg,
            png_base64=png_b64,
        )
