"""Pydantic v2 models for the Diagrams domain (ADP-SPEC-046, data-model.md §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

DiagramType = Literal["flowchart", "sequence", "erd", "uml", "architecture", "c4"]

_DSL_SOURCE_MAX_CHARS = 50_000
_TITLE_MAX_CHARS = 200


def _check_title(v: str) -> str:
    """Shared title validation for DiagramCreate/DiagramUpdate (ADP-6ir).

    Beyond the pre-existing not-blank check: rejects control characters and
    backslash, and caps length, mirroring ArchitectureDescription.title's
    own Field(min_length=1, max_length=200) convention (src/adp/models.py).
    A diagram title is a plain display string with no legitimate use for
    either -- this isn't "fixing a path-traversal vulnerability" (title is
    never used to construct a filesystem path anywhere in this module,
    confirmed by inspection) but it does eliminate a confirmed ZAP false
    positive (High/Low confidence, empty evidence) where the scanner's
    generic Path Traversal rule matched on a backslash-prefixed payload
    being accepted and echoed back verbatim in the create response.
    """
    if not v.strip():
        raise ValueError("title must not be blank")
    if len(v) > _TITLE_MAX_CHARS:
        raise ValueError(f"title must not exceed {_TITLE_MAX_CHARS} characters")
    if "\\" in v or ".." in v or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in v):
        raise ValueError(
            "title must not contain control characters, a backslash, or '..'"
        )
    return v


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
        return _check_title(v)

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
        return _check_title(v) if v is not None else v

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
