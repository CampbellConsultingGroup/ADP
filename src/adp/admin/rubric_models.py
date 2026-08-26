"""Pydantic v2 request/response models for the Admin Scoring Rubric Management API (ADP-68z).

See contracts/scoring-rubrics-api.md for the full contract. Mirrors adp.admin.models exactly,
substituting a validated dict[str, float] weight set for a free-text prompt string.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class RubricView(BaseModel):
    """One rubric's current effective weights (FR-004)."""

    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    display_name: str
    dimension_labels: dict[str, str]
    active_weights: dict[str, float]
    is_override: bool
    version: int


class RubricListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RubricView]


class RubricEditRequest(BaseModel):
    """Confirm body for a manual edit (FR-005, FR-012).

    Mirrors PromptEditRequest: confirmation_id is required and non-empty --
    ART-VIII, MANAGE_SCORING_RUBRICS is in REQUIRES_CONFIRMATION. Unlike a
    prompt's plain non-empty check, `weights` validity is rubric-specific
    (data-model.md §2) and is NOT re-validated here -- the service layer
    calls the rubric's own registered validate() before writing anything,
    since this model has no way to know which rubric_id it's for (that's
    a path parameter, not a body field).
    """

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float]
    expected_version: int
    confirmation_id: str

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty_confirmation(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty -- changing a live scoring rubric's "
                "weights is a consequential action per ART-VIII"
            )
        return v

    @field_validator("weights")
    @classmethod
    def _require_non_empty_weights(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("weights must not be empty")
        return v


class RubricRestoreRequest(BaseModel):
    """Confirm body for a restore (FR-006) -- same confirmation gate as an
    edit (mirrors PromptRestoreRequest / ADP-SPEC-042's own Clarification
    Session 2026-07-24: restore is not a lower-friction path)."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int
    confirmation_id: str

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty_confirmation(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty -- restoring a prior weight set "
                "is a consequential action per ART-VIII, identical to a manual edit"
            )
        return v


class RubricChangeResult(BaseModel):
    """Response for a successful confirm or restore -- the rubric's new state."""

    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    active_weights: dict[str, float]
    version: int


class RubricVersionConflictError(BaseModel):
    """409 body: the underlying weights changed since the caller loaded them (FR-005)."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    current_active_weights: dict[str, float]
    current_version: int


class RubricHistoryEntry(BaseModel):
    """One row of a rubric's change history (FR-006)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    rubric_id: str
    actor: str
    changed_at: datetime
    change_type: str
    prior_weights: dict[str, float]
    new_weights: dict[str, float]


class RubricHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RubricHistoryEntry]
