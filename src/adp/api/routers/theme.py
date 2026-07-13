"""C4 theme router — reads from the locked theme artifact via ThemeLoader.

ADP-SPEC-010 implemented; this router now delegates to adp.theme.loader
rather than returning a hardcoded constant. The ThemeLoader reads
src/adp/theme/c4-theme.json, validates it against c4-theme.schema.json,
and returns the authoritative LockedTheme.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from adp.theme.loader import ThemeLoader
from adp.theme.models import LockedTheme, ThemeValidationError

router = APIRouter(prefix="/api/v1/theme", tags=["theme"])

_loader = ThemeLoader()


@router.get("/c4", response_model=LockedTheme)
async def get_c4_theme() -> LockedTheme:
    """Return the locked C4 visual theme (ADP-SPEC-010 / ART-XII).

    Reads from src/adp/theme/c4-theme.json and validates against the schema.
    Returns 422 if the theme file is missing or invalid (should not happen in
    a correctly deployed instance).
    """
    try:
        return _loader.load_and_validate()
    except ThemeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Theme validation failed: {exc}",
        ) from exc
