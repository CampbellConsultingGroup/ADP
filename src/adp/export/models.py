"""Pydantic v2 models for the export/import API boundary (ADP-SPEC-011).

Kept separate from adp.docs.models to avoid circular imports between
adp.docs and adp.export packages.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class ExportRequest(BaseModel):
    """Request body for POST /api/v1/designs/{id}/export.

    ART-VIII: confirmation_id must be a non-empty string. An empty or absent
    confirmation_id is rejected at the Pydantic validation layer — before
    the export handler runs — making it impossible to skip the confirmation gate.
    """

    model_config = ConfigDict(extra="forbid")

    confirmation_id: str
    export_root: str

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty — export is a consequential action "
                "per ART-VIII and requires an attributable confirmation"
            )
        return v


class ExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    model_version: int
    export_path: str
    artifacts: list[str]
    audit_entry_id: str


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_json: str


class ImportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    design_id: str
    schema_version: str
    element_count: int
    relationship_count: int
    validation_warnings: list[str]
