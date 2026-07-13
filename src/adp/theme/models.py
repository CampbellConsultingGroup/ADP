"""Pydantic v2 models for the locked C4 visual theme and render API boundary."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

C4Level = Literal["context", "container", "component"]


class ThemeValidationError(ValueError):
    """Raised when c4-theme.json fails schema validation."""

    def __init__(self, message: str, failing_constraint: str = "unknown") -> None:
        super().__init__(message)
        self.failing_constraint = failing_constraint


_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ElementStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fill: str
    stroke: str
    color: str
    shape: Literal["box", "actor", "cylinder", "hexagon"]
    font_size: int
    font_weight: Literal["normal", "bold"]

    @field_validator("fill", "stroke", "color")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError(f"Color must be a 7-character hex string like #RRGGBB, got {v!r}")
        return v

    @field_validator("font_size")
    @classmethod
    def _validate_font_size(cls, v: int) -> int:
        if not (8 <= v <= 24):
            raise ValueError(f"font_size must be between 8 and 24, got {v}")
        return v


class RelationshipStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stroke: str
    stroke_width: float
    arrow_end: Literal["open", "filled", "none"]

    @field_validator("stroke")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not _HEX_RE.match(v):
            raise ValueError(f"Color must be a 7-character hex string, got {v!r}")
        return v

    @field_validator("stroke_width")
    @classmethod
    def _validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("stroke_width must be > 0")
        return v


class LockedTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    locked: Literal[True]  # ART-XII: type-level enforcement; Pydantic rejects locked=false
    styles: dict[str, ElementStyle]
    relationship_style: RelationshipStyle

    @field_validator("version")
    @classmethod
    def _validate_semver(cls, v: str) -> str:
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(f"version must be MAJOR.MINOR.PATCH, got {v!r}")
        return v


class RenderRequest(BaseModel):
    # ART-XII / FR-002: no style override fields accepted;
    # any unknown field causes 422 before renderer is called.
    model_config = ConfigDict(extra="forbid")

    level: C4Level


class RenderResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    level: C4Level
    dsl: str
    svg: str
    png_base64: str
