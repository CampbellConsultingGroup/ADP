"""Layout position router — ADP-SPEC-003 extension.

Stores canvas element positions (x/y) per design and C4 level. Layout is
NOT part of the canonical model (ADP-SPEC-001); positions are a UI concern
stored separately. Changing positions does NOT bump the design version.

v1: in-process dict (transient). A process restart clears positions and the
canvas falls back to auto-layout. Persistent storage is v2.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/designs", tags=["layouts"])

C4Level = Literal["context", "container", "component"]

# In-process layout store (v1). Key: (design_id, level).
_layout_store: dict[tuple[str, str], dict[str, dict[str, float]]] = {}

# Roles permitted to write layout (same auth pattern as ADP-SPEC-003).
_WRITE_ROLES = {"architect", "enterprise_architect"}


class Position(BaseModel):
    x: float
    y: float


class LayoutResponse(BaseModel):
    design_id: str
    level: C4Level
    positions: dict[str, Position]


class SaveLayoutRequest(BaseModel):
    positions: dict[str, Position]


def _get_token_role(authorization: str | None = None) -> str:
    """Extract role from Bearer token (stub — delegates to ADP-SPEC-004 in full stack)."""
    # In tests this is overridden via dependency_overrides.
    # In production this would call the OIDC/JWT validation middleware.
    return "architect"  # pragma: no cover


RoleHeader = Annotated[str, Depends(_get_token_role)]


@router.get("/{design_id}/layout/{level}", response_model=LayoutResponse)
async def get_layout(design_id: str, level: C4Level) -> LayoutResponse:
    """Return element positions for a design at a specific C4 level.

    Returns empty positions if none have been saved yet; the canvas
    falls back to auto-layout in that case.
    """
    key = (design_id, level)
    raw = _layout_store.get(key, {})
    positions = {eid: Position(**pos) for eid, pos in raw.items()}
    return LayoutResponse(design_id=design_id, level=level, positions=positions)


@router.put(
    "/{design_id}/layout/{level}",
    response_model=LayoutResponse,
    status_code=status.HTTP_200_OK,
)
async def save_layout(
    design_id: str,
    level: C4Level,
    body: SaveLayoutRequest,
    role: RoleHeader,
) -> LayoutResponse:
    """Replace element positions for a design at a specific C4 level.

    Requires architect or enterprise_architect role. Replaces the entire
    layout for the given level.
    """
    if role not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{role}' cannot save layout; requires architect.",
        )
    _layout_store[(design_id, level)] = {
        eid: {"x": pos.x, "y": pos.y} for eid, pos in body.positions.items()
    }
    return LayoutResponse(design_id=design_id, level=level, positions=body.positions)
