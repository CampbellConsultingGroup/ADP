"""Pydantic v2 request/response models for the Admin Agent Prompt Management
API (ADP-SPEC-042). See contracts/agent-prompts-api.md for the full contract.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class AgentPromptView(BaseModel):
    """One agent's current effective prompt (FR-001, FR-002)."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    display_name: str
    active_text: str
    is_override: bool
    version: int


class AgentPromptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentPromptView]


class PromptEditRequest(BaseModel):
    """Confirm body for a manual edit (FR-003, FR-004, FR-010, FR-012).

    Mirrors SuggestionAcceptRequest (adp/business/models.py): confirmation_id
    is required and non-empty -- ART-VIII, MANAGE_AGENT_PROMPTS is in
    REQUIRES_CONFIRMATION.
    """

    model_config = ConfigDict(extra="forbid")

    new_text: str
    expected_version: int
    confirmation_id: str

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty_confirmation(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty -- changing an agent's live "
                "system prompt is a consequential action per ART-VIII"
            )
        return v

    @field_validator("new_text")
    @classmethod
    def _require_non_empty_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "new_text must be non-empty -- an agent must never run with no "
                "instructions (FR-004)"
            )
        return v


class PromptRestoreRequest(BaseModel):
    """Confirm body for a restore (FR-008) -- same confirmation gate as an
    edit (Clarification Session 2026-07-24: restore is not a lower-friction
    path)."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int
    confirmation_id: str

    @field_validator("confirmation_id")
    @classmethod
    def _require_non_empty_confirmation(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(
                "confirmation_id must be non-empty -- restoring a prior prompt "
                "version is a consequential action per ART-VIII, identical to "
                "a manual edit"
            )
        return v


class PromptChangeResult(BaseModel):
    """Response for a successful confirm or restore -- the agent's new state."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    active_text: str
    version: int


class VersionConflictError(BaseModel):
    """409 body: the underlying prompt changed since the caller loaded it (FR-012)."""

    model_config = ConfigDict(extra="forbid")

    detail: str
    current_active_text: str
    current_version: int


class PromptHistoryEntry(BaseModel):
    """One row of an agent's change history (FR-006, FR-007)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    agent_id: str
    actor: str
    changed_at: datetime
    change_type: str
    prior_text: str
    new_text: str


class PromptHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PromptHistoryEntry]
