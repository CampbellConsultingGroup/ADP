"""Per-turn orchestration for the AI Chat Assistant (ADP-SPEC-041).

run_turn assembles context, streams a reply via LLMClient.chat_stream,
dispatches any tool calls the model requests (US2), grounds citations, and
persists both the user's message and the completed assistant message.
Mirrors adp.business.agent_review's span/failure-handling shape
(ADP-SPEC-039), adapted for a streaming, multi-turn, read-only feature.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from adp.admin import prompt_registry
from adp.agents.grounding import verify_references
from adp.agents.models import GroundingCitation
from adp.authz.roles import PersonaRole
from adp.chat import retrieval
from adp.chat import store as chat_store
from adp.chat.models import ChatCitation, ChatMessage, ChatRole
from adp.chat.tools import anthropic_tool_specs, dispatch_tool
from adp.telemetry.spans import ai_step_span

logger = logging.getLogger("adp.chat.orchestrator")

# Hard cap on tool-call round-trips within a single turn -- a safety net
# against a pathological loop (model keeps requesting tools indefinitely),
# not a limit expected to bind in ordinary use.
_MAX_TOOL_ROUNDS = 5

_SYSTEM_PROMPT = (
    "You are a helpful assistant for a business architect or business person "
    "exploring their organization's business capabilities, applications, and "
    "portfolio. Answer strictly from the context provided below and any tool "
    "results; if you don't have grounded information to answer a question, "
    "say so rather than guessing. If a tool reports {'permitted': false}, "
    "tell the user you don't have access to that category rather than "
    "guessing at or omitting it silently. When your answer refers to a "
    "specific entity from the context or a tool result, cite its id inline "
    "immediately after mentioning it, in the exact form "
    "[business_capability:<id>], [technical_capability:<id>], "
    "[application:<id>], [value_stream:<id>], or [business_domain:<id>]. "
    "Never invent an id that wasn't given to you."
)

_CITATION_PATTERN = re.compile(
    r"\[(business_capability|technical_capability|application|value_stream|business_domain):"
    r"([\w-]+)\]"
)


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


# Bounded sliding window (US4, research D8): each turn sends the LLM only
# the most recent _CONTEXT_WINDOW_SIZE messages, regardless of how long the
# full stored/displayed history is -- bounds token cost/latency growth on a
# long conversation without ever discarding anything from what's persisted
# or shown to the user (that's the full, untruncated `history` the router
# fetches via chat_store.get_conversation).
_CONTEXT_WINDOW_SIZE = 10


def _windowed_history(history: list[ChatMessage]) -> list[ChatMessage]:
    if len(history) <= _CONTEXT_WINDOW_SIZE:
        return history
    return history[-_CONTEXT_WINDOW_SIZE:]


def _messages_for_llm(
    history: list[ChatMessage], new_user_content: str
) -> list[dict[str, Any]]:
    """Converts a (already-windowed) slice of persisted ChatMessage history
    + the new turn into the Anthropic Messages API shape LLMClient.chat_stream
    expects."""
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
    kb_session: AsyncSession,
    role: PersonaRole,
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

    Separate chat_session/biz_session/app_session/kb_session (rather than
    one shared session) mirrors agent_review.py's precedent exactly: in
    production all four point at the same physical database, but tests give
    each domain its own SQLite engine, and adp.search's hybrid_search
    additionally requires a real pgvector-backed Postgres session
    (biz_session, matching the existing /api/v1/search router's precedent)
    that SQLite cannot provide at all -- so retrieval is mocked at the call
    site in tests rather than exercised against a fake in-memory index.
    `kb_session` is for the two aggregate tools (portfolio_summary,
    governance_status) that read the canonical design store, a fourth
    distinct database from chat/business/application (adp.api.deps'
    shared "kb" session, ADP-SPEC-023).

    `role` is the asking user's PersonaRole, threaded through to
    adp.chat.tools.dispatch_tool so a sensitive-category tool
    (get_application_{risk,cost,governance}) can check the caller's own
    permission before returning that category's data (research D5) -- the
    enforcement point is the tool's code path, never a prompt instruction.
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
        # ADP-SPEC-042: resolve via the admin-editable registry (falls back to
        # _SYSTEM_PROMPT above when no override exists).
        effective_prompt = (await prompt_registry.get_effective_prompt("chat_assistant")).text
        system_prompt = f"{effective_prompt}\n\nContext:\n{context_block}"

        messages = _messages_for_llm(_windowed_history(history), user_content)
        tool_sessions = {
            "biz_session": biz_session, "app_session": app_session, "kb_session": kb_session,
        }

        full_text = ""
        input_tokens = 0
        output_tokens = 0
        try:
            for _round in range(_MAX_TOOL_ROUNDS):
                round_text = ""
                stop_reason = "end_turn"
                pending_tool_calls: list[dict[str, Any]] = []
                async for event in llm_client.chat_stream(
                    messages=messages, system=system_prompt, tools=anthropic_tool_specs(),
                ):
                    if event["type"] == "text_delta":
                        round_text += event["text"]
                        full_text += event["text"]
                        yield {"type": "text_delta", "text": event["text"]}
                    elif event["type"] == "tool_use":
                        pending_tool_calls.append(event)
                    elif event["type"] == "done":
                        stop_reason = event["stop_reason"]
                        input_tokens += event["usage"].get("prompt_tokens", 0)
                        output_tokens += event["usage"].get("completion_tokens", 0)

                if stop_reason != "tool_use" or not pending_tool_calls:
                    break

                # Assistant turn: any text spoken before the call(s), plus the
                # tool_use block(s) themselves -- Anthropic's content-block
                # shape, appended verbatim to `messages` for the next round.
                assistant_content: list[dict[str, Any]] = []
                if round_text:
                    assistant_content.append({"type": "text", "text": round_text})
                for call in pending_tool_calls:
                    assistant_content.append({
                        "type": "tool_use", "id": call["id"],
                        "name": call["name"], "input": call["input"],
                    })
                messages.append({"role": "assistant", "content": assistant_content})

                tool_result_content = [
                    {
                        "type": "tool_result",
                        "tool_use_id": call["id"],
                        "content": json.dumps(
                            await dispatch_tool(
                                call["name"], call["input"], role, sessions=tool_sessions
                            )
                        ),
                    }
                    for call in pending_tool_calls
                ]
                messages.append({"role": "user", "content": tool_result_content})
            else:
                logger.warning(
                    "chat.run_turn: hit max tool rounds (%d) for conversation %s",
                    _MAX_TOOL_ROUNDS, conversation_id,
                )
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

        async def _application_exists(entity_id: str) -> bool:
            from adp.application import store as astore
            app = await astore.get_application(entity_id, app_session)
            return app is not None

        async def _value_stream_exists(entity_id: str) -> bool:
            from adp.business import store as bstore
            vs = await bstore.get_value_stream(entity_id, biz_session)
            return vs is not None

        async def _business_domain_exists(entity_id: str) -> bool:
            from adp.business import store as bstore
            domain = await bstore.get_domain(entity_id, biz_session)
            return domain is not None

        grounding = await verify_references(
            raw_citations,
            lookups={
                "business_capability": _capability_exists,
                "technical_capability": _tech_capability_exists,
                "application": _application_exists,
                "value_stream": _value_stream_exists,
                "business_domain": _business_domain_exists,
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
