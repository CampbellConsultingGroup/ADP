"""Pydantic v2 models for document generation (ADP-SPEC-011).

Only document-layer models live here. Export/import boundary models are in
adp.export.models to avoid circular imports.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from adp.theme.models import C4Level, RenderResult

C4Level = C4Level  # re-export for convenience


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    schema_version: str
    generated_at: str  # ISO 8601 UTC
    generator: Literal["ADP-SPEC-011"]
    level: C4Level | None = None


class GeneratedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    markdown: str
    metadata: DocumentMetadata


class TraceabilityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element_id: str
    element_name: str
    element_kind: str
    satisfied_requirements: list[str]
    provenance: str | None
    verdict_ids: list[str]  # always [] in v1 — see TraceabilityGenerator note
    is_orphan: bool


class TraceabilityMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    schema_version: str
    generated_at: str
    total_elements: int
    orphan_count: int
    entries: list[TraceabilityEntry]


class ViewBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    context: RenderResult
    container: RenderResult
    component: RenderResult
