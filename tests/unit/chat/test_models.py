"""Unit tests: adp.chat boundary models (ADP-SPEC-041)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from adp.chat.models import (
    ChatCitation,
    ChatConversationDetail,
    ChatConversationSummary,
    ChatMessage,
    ChatRole,
    SendMessageRequest,
)


def test_chat_message_round_trips():
    now = datetime.now(timezone.utc)
    msg = ChatMessage(
        id="M-1", conversation_id="C-1", role=ChatRole.ASSISTANT,
        content="The Merchandising capability has no domain assigned.",
        citations=[
            ChatCitation(entity_type="business_capability", entity_id="CAP-1", verified=True)
        ],
        created_at=now,
    )
    dumped = msg.model_dump(mode="json")
    restored = ChatMessage.model_validate(dumped)
    assert restored == msg


def test_chat_message_rejects_unknown_fields():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ChatMessage(
            id="M-1", conversation_id="C-1", role=ChatRole.USER, content="hi",
            created_at=now, extra_field="not allowed",  # type: ignore[call-arg]
        )


def test_chat_conversation_detail_round_trips():
    now = datetime.now(timezone.utc)
    detail = ChatConversationDetail(
        id="C-1", title="Merchandising questions", created_at=now, updated_at=now,
        messages=[
            ChatMessage(
                id="M-1", conversation_id="C-1", role=ChatRole.USER,
                content="hi", created_at=now,
            ),
        ],
    )
    restored = ChatConversationDetail.model_validate(detail.model_dump(mode="json"))
    assert restored == detail


def test_chat_conversation_summary_rejects_unknown_fields():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ChatConversationSummary(
            id="C-1", title="x", created_at=now, updated_at=now,
            messages=[],  # type: ignore[call-arg]
        )


def test_send_message_request_rejects_blank_content():
    with pytest.raises(ValidationError):
        SendMessageRequest(content="   ")


def test_send_message_request_accepts_real_content():
    req = SendMessageRequest(content="Which capabilities are unclassified?")
    assert req.content == "Which capabilities are unclassified?"
