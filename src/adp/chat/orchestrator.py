"""Per-turn orchestration for the AI Chat Assistant (ADP-SPEC-041).

run_turn assembles context, streams a reply via LLMClient.chat_stream,
grounds citations, and persists both the user's message and the completed
assistant message. Mirrors adp.business.agent_review's span/failure-handling
shape (ADP-SPEC-039), adapted for a streaming, multi-turn, read-only feature.

US1 scope: no tool-calling yet (llm_client.chat_stream is always called with
tools=None here); US2 (research plan, T031) extends this same function with
a tool-use loop once adp.chat.tools exists.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from adp.agents.grounding import verify_references
from adp.agents.models import GroundingCitation
from adp.chat import retrieval
from adp.chat import store as chat_store
from adp.chat.models import ChatCitation, ChatMessage, ChatRole
from adp.telemetry.spans import ai_step_span

logger = logging.getLogger("adp.chat.orchestrator")

_SYSTEM_PROMPT = (
    "You are a helpful assistant for a business architect or business person "
    "exploring their organization's business capabilities, applications, and "
    "portfolio. Answer strictly from the context provided below; if you don't "
    "have grounded information to answer a question, say so rather than "
    "guessing. When your answer refers to a specific capability or technical "
    "capability from the context, cite its id inline in the exact form "
    "[business_capability:<id>] or [technical_capability:<id>] immediately "
    "after mentioning it. Never invent an id that wasn't given to you."
)

_CITATION_PATTERN = re.compile(r"\[(business_capability|technical_capability):([\w-]+)\]")


def _extract_inline_citations(text: str) -> tuple[str, list[GroundingCitation]]:
    """Strips [entity_type:entity_id] markers from the display text and
    returns them as citations to ground separately -- the reply the user
    sees never contains the raw bracket markup."""
    citations = [
        GroundingCitation(entity_type=m.group(1), entity_id=m.group(2))
        for m in _CITATION_PATTERN.finditer(text)
    ]
    cleaned = _CITATION_PATTERN.sub("", text)
    return cleaned, citations


def _messages_for_llm(
    history: list[ChatMessage], new_user_content: str
) -> list[dict[str, Any]]:
    """Converts persisted ChatMessage history + the new turn into the
    Anthropic Messages API shape LLMClient.chat_stream expects."""
    messages = [{"role": m.role.value, "content": m.content} for m in history]
    messages.append({"role": ChatRole.USER.value, "content": new_user_content})
    return messages


async def run_turn(
    *,
    conversation_id: str,
    history: list[ChatMessage],
    user_content: str,
    chat_session: AsyncSession,
    biz_session: AsyncSession,
    app_session: AsyncSession,
    llm_client: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Yields SSE-ready event dicts ({"type": "text_delta"|"error", ...}) for
    the router to forward, and persists both the user message and the
    completed assistant message as a side effect. Never raises to the
    caller -- an LLM-call failure yields an "error" event instead (FR-021's
    equivalent for a streaming feature: distinguishable from a normal reply,
    never silently swallowed).

    `history` is the conversation's messages *before* this turn, already
    fetched (and actor-ownership-checked) by the router -- run_turn has no
    actor-scoping concern of its own; it trusts the caller validated access.

    Separate chat_session/biz_session/app_session (rather than one shared
    session) mirrors agent_review.py's precedent exactly: in production all
    three point at the same physical database, but tests give each domain
    its own SQLite engine, and adp.search's hybrid_search additionally
    requires a real pgvector-backed Postgres session (biz_session, matching
    the existing /api/v1/search router's precedent) that SQLite cannot
    provide at all -- so retrieval is mocked at the call site in tests
    rather than exercised against a fake in-memory index.
    """
    with ai_step_span("chat_turn", operation_id=conversation_id) as span:
        span.set_attribute("adp.conversation_id", conversation_id)

        await chat_store.append_message(conversation_id, ChatRole.USER, user_content, chat_session)
        if not history:
            await chat_store.set_title_if_default(
                user_content[:80], conversation_id, chat_session
            )
        await chat_session.commit()

        try:
            hits = await retrieval.retrieve_context(user_content, biz_session)
        except Exception:  # pragma: no cover -- defensive; retrieval must never break a turn
            logger.exception("chat.retrieval failed for conversation %s", conversation_id)
            hits = []

        context_block = "\n".join(
            f"- ({h.entity_type}:{h.entity_id}) {h.text}" for h in hits
        ) or "(no directly relevant context found)"
        system_prompt = f"{_SYSTEM_PROMPT}\n\nContext:\n{context_block}"

        messages = _messages_for_llm(history, user_content)

        full_text = ""
        input_tokens = 0
        output_tokens = 0
        try:
            async for event in llm_client.chat_stream(messages=messages, system=system_prompt):
                if event["type"] == "text_delta":
                    full_text += event["text"]
                    yield {"type": "text_delta", "text": event["text"]}
                elif event["type"] == "done":
                    input_tokens = event["usage"].get("prompt_tokens", 0)
                    output_tokens = event["usage"].get("completion_tokens", 0)
        except Exception as exc:
            logger.exception("chat.run_turn failed for conversation %s", conversation_id)
            yield {"type": "error", "detail": str(exc)[:500]}
            return

        span.set_attribute("adp.input_tokens", input_tokens)
        span.set_attribute("adp.output_tokens", output_tokens)

        cleaned_text, raw_citations = _extract_inline_citations(full_text)

        async def _capability_exists(entity_id: str) -> bool:
            from adp.business import store as bstore
            cap = await bstore.get_capability(entity_id, biz_session)
            return cap is not None

        async def _tech_capability_exists(entity_id: str) -> bool:
            from adp.application import store as astore
            tech_cap = await astore.get_technical_capability(entity_id, app_session)
            return tech_cap is not None

        grounding = await verify_references(
            raw_citations,
            lookups={
                "business_capability": _capability_exists,
                "technical_capability": _tech_capability_exists,
            },
        )
        resolved_ids = {(c.entity_type, c.entity_id) for c in grounding.resolved}
        chat_citations = [
            ChatCitation(
                entity_type=c.entity_type, entity_id=c.entity_id,
                verified=(c.entity_type, c.entity_id) in resolved_ids,
            )
            for c in raw_citations
        ]

        assistant_message = await chat_store.append_message(
            conversation_id, ChatRole.ASSISTANT, cleaned_text, chat_session,
            citations=chat_citations,
        )
        await chat_session.commit()

        yield {
            "type": "done",
            "message_id": assistant_message.id,
            "citations": [c.model_dump(mode="json") for c in chat_citations],
        }
