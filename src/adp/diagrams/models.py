"""Pydantic v2 models for the Diagrams domain (ADP-SPEC-046, data-model.md §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

DiagramType = Literal["flowchart", "sequence", "erd", "uml", "architecture"]

_DSL_SOURCE_MAX_CHARS = 50_000


class Diagram(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    diagram_type: DiagramType
    dsl_source: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class DiagramCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    diagram_type: DiagramType
    # A brand-new diagram must be creatable before any content exists (spec
    # Edge Cases) -- defaulting to "" rather than requiring content upfront.
    dsl_source: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank")
        return v

    @field_validator("dsl_source")
    @classmethod
    def dsl_source_within_cap(cls, v: str) -> str:
        if len(v) > _DSL_SOURCE_MAX_CHARS:
            raise ValueError(f"dsl_source must not exceed {_DSL_SOURCE_MAX_CHARS} characters")
        return v


class DiagramUpdate(BaseModel):
    """Partial update -- title and/or dsl_source. diagram_type is immutable
    after creation (data-model.md §4): switching a flowchart into a sequence
    diagram mid-life is a "create a new diagram" action, not an update, so
    this model deliberately has no diagram_type field at all."""

    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    dsl_source: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("title must not be blank")
        return v

    @field_validator("dsl_source")
    @classmethod
    def dsl_source_within_cap(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _DSL_SOURCE_MAX_CHARS:
            raise ValueError(f"dsl_source must not exceed {_DSL_SOURCE_MAX_CHARS} characters")
        return v


class DiagramSummary(BaseModel):
    """List-view shape (FR-006): title/type/updated_at only, no dsl_source --
    mirrors the existing summary-vs-detail split (e.g. knowledge items'
    list endpoint omitting full_text)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    diagram_type: DiagramType
    updated_at: datetime


class DiagramListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[DiagramSummary]
    total: int
