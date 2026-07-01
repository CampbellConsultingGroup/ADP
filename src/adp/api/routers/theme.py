"""C4 theme router — development stub.

# TODO(ADP-SPEC-010): replace stub with real theme store
Returns the locked baseline C4 theme defined in contracts/theme-contract.md.
No database required; the theme JSON is a static constant for v1.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/theme", tags=["theme"])


class ElementStyle(BaseModel):
    fill: str
    stroke: str
    color: str
    shape: str
    font_size: int
    font_weight: str


class RelationshipStyle(BaseModel):
    stroke: str
    stroke_width: float
    arrow_end: str


class C4ThemeResponse(BaseModel):
    version: str
    locked: bool
    styles: dict[str, ElementStyle]
    relationship_style: RelationshipStyle


_BASELINE_THEME = C4ThemeResponse(
    version="1.0.0",
    locked=True,
    styles={
        "person": ElementStyle(
            fill="#08427B",
            stroke="#073B6F",
            color="#ffffff",
            shape="actor",
            font_size=14,
            font_weight="normal",
        ),
        "system": ElementStyle(
            fill="#1168BD",
            stroke="#0E5FA3",
            color="#ffffff",
            shape="box",
            font_size=14,
            font_weight="bold",
        ),
        "container": ElementStyle(
            fill="#438DD5",
            stroke="#3C7FC0",
            color="#ffffff",
            shape="box",
            font_size=13,
            font_weight="normal",
        ),
        "component": ElementStyle(
            fill="#85BBE0",
            stroke="#78A8CC",
            color="#000000",
            shape="box",
            font_size=12,
            font_weight="normal",
        ),
    },
    relationship_style=RelationshipStyle(
        stroke="#707070",
        stroke_width=1.5,
        arrow_end="open",
    ),
)


@router.get("/c4", response_model=C4ThemeResponse)
async def get_c4_theme() -> C4ThemeResponse:
    """Return the locked baseline C4 visual theme."""
    return _BASELINE_THEME
