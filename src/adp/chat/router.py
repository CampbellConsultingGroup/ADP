"""AI Chat Assistant API — ADP-SPEC-041.

POST /api/v1/chat/conversations                    — create a conversation
POST /api/v1/chat/conversations/{id}/messages       — send a message, SSE reply
GET  /api/v1/chat/conversations                     — list own conversations (US3)
GET  /api/v1/chat/conversations/{id}                — resume a conversation (US3)

ART-V: every route requires an authenticated actor (or the dev X-Actor header);
conversations/messages are actor-scoped by construction in adp.chat.store
(FR-009) -- a conversation that doesn't exist or isn't owned by the caller is
never distinguished, always a 404 (SC-003).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.chat import orchestrator
from adp.chat import store as chat_store
from adp.chat.models import (
    ChatConversationDetail,
    ChatConversationSummary,
    SendMessageRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── Shared helpers (mirrors adp.business.router's _get_actor exactly) ────────

def _get_actor(request: Request) -> str:
    from adp.auth.models import UNAUTHENTICATED_USER
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return user.username
    return request.headers.get("X-Actor", "architect")


async def _get_chat_session():
    factory = chat_store._get_session_factory()
    async with factory() as session:
        yield session


async def _get_chat_session_factory():
    return chat_store._get_session_factory()


async def _get_biz_session_factory():
    from adp.business import store as bstore
    return bstore._get_session_factory()


async def _get_application_session_factory():
    from adp.application import store as astore
    return astore._get_session_factory()


async def _get_kb_session_factory():
    from adp.api.deps import _get_kb_session_factory as get_factory
    return get_factory()


def _make_chat_llm_client():
    """Create an LLMClient for the chat assistant, or the shared stub when no
    API key is configured (mirrors business/router.py's
    _make_agent_review_llm_client)."""
    from adp.agents.llm_stub import StubLLMClient
    from adp.api.routers.config import get_api_key, get_extraction_model
    from adp.llm.client import LLMClient

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = get_api_key()
    if not api_key:
        return StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    return LLMClient(base_url=endpoint, api_key=api_key, model=get_extraction_model())


# ── Conversations ─────────────────────────────────────────────────────────────

@router.post(
    "/conversations", response_model=ChatConversationSummary, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    request: Request, session: AsyncSession = Depends(_get_chat_session)
):
    actor = _get_actor(request)
    conv = await chat_store.create_conversation(actor, session)
    await session.commit()
    logger.info("chat.conversation.create id=%s actor=%s", conv.id, actor)
    return conv


@router.get("/conversations", response_model=list[ChatConversationSummary])
async def list_conversations(
    request: Request, session: AsyncSession = Depends(_get_chat_session)
):
    actor = _get_actor(request)
    return await chat_store.list_conversations(actor, session)


@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetail)
async def get_conversation(
    conversation_id: str,
    request: Request,
    session: AsyncSession = Depends(_get_chat_session),
):
    actor = _get_actor(request)
    detail = await chat_store.get_conversation(conversation_id, actor, session)
    if detail is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id!r} not found"
        )
    return detail


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    chat_session_factory=Depends(_get_chat_session_factory),
    biz_session_factory=Depends(_get_biz_session_factory),
    app_session_factory=Depends(_get_application_session_factory),
    kb_session_factory=Depends(_get_kb_session_factory),
):
    """Streams the assistant's reply as SSE (`text/event-stream`).

    Ownership is checked up front against a short-lived session (404 before
    any streaming starts if the conversation doesn't exist or isn't the
    caller's, per FR-009/SC-003). The actual turn opens its own fresh
    sessions inside the generator -- a request-scoped `Depends` session
    would close as soon as this function returns, before the
    StreamingResponse body is actually consumed by the ASGI server, so
    orchestrator.run_turn needs sessions it can hold open across the whole
    generator's lifetime (mirrors the background-task session pattern in
    business/router.py's submit_capability_agent_review).

    `role` comes from the injected `get_current_user` dependency (not a
    manual `request.state.user` read like `_get_actor`) so tests can
    simulate any PersonaRole via `app.dependency_overrides[get_current_user]`
    -- the same seam tests/authz/test_enforcement.py already uses -- to
    exercise the tool layer's sensitive-category gating (research D5)
    without needing a real auth-enabled JWT flow.
    """
    actor = _get_actor(request)
    role = user.role
    async with chat_session_factory() as lookup_session:
        existing = await chat_store.get_conversation(conversation_id, actor, lookup_session)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Conversation {conversation_id!r} not found"
        )

    llm_client = _make_chat_llm_client()
    history = existing.messages

    async def _event_stream() -> AsyncIterator[str]:
        async with (
            chat_session_factory() as chat_session,
            biz_session_factory() as biz_session,
            app_session_factory() as app_session,
            kb_session_factory() as kb_session,
        ):
            async for event in orchestrator.run_turn(
                conversation_id=conversation_id,
                history=history,
                user_content=body.content,
                chat_session=chat_session,
                biz_session=biz_session,
                app_session=app_session,
                kb_session=kb_session,
                role=role,
                llm_client=llm_client,
            ):
                yield f"data: {json.dumps(event)}\n\n"

    logger.info(
        "chat.conversation.message id=%s actor=%s", conversation_id, actor
    )
    return StreamingResponse(_event_stream(), media_type="text/event-stream")
