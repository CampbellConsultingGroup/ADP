"""Boundary models for the AI Chat Assistant (ADP-SPEC-041).

Unlike the Agent Review toolkit, this module deliberately sits outside
adp.agents' zero-domain-import contract -- see agent_review.py/plan.md's
research D3. It reuses adp.agents.models.GroundingCitation as-is (that
reuse direction is fine; only adp.agents itself must avoid importing a
single domain module).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from adp.agents.models import GroundingCitation


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatCitation(GroundingCitation):
    """A GroundingCitation plus whether it re-verified successfully (FR-006).

    Unlike Agent Review's advisory/accept-block pair, there is no write to
    block here -- an unverified citation is simply flagged inline.
    """

    verified: bool


class ChatMessage(BaseModel):
    """One message in a conversation (FR-008)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    conversation_id: str
    role: ChatRole
    content: str
    citations: list[ChatCitation] = []
    created_at: datetime


class ChatConversationSummary(BaseModel):
    """List-response item (FR-009's own-conversations-only listing)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatConversationDetail(ChatConversationSummary):
    """Full conversation, all messages, oldest first."""

    messages: list[ChatMessage] = []


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    # ADP-914.8: optional diagram context (title/type/current DSL), supplied
    # by the frontend when this endpoint is called from the diagram editor.
    # Never persisted (research.md Decision 2) -- consumed only by
    # orchestrator.run_turn for that one turn's system-prompt assembly.
    diagram_context: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be blank")
        return v
