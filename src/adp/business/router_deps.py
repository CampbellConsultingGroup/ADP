"""Dependencies shared by the Business Architecture routers (ADP-blp.27).

``adp.business.router`` re-exports every name here, so a test overrides
``brouter._get_session`` (and the others) as before.
"""

from __future__ import annotations

import logging
import os

from fastapi import Request

from adp.api.common import session_dependency
from adp.auth.actor import actor_of
from adp.business import store as bstore

# One logger name for every business route, whichever module it is in.
logger = logging.getLogger("adp.business.router")


def _get_actor(request: Request) -> str:
    return actor_of(request)


_get_session = session_dependency("adp.business.store")


_get_application_session = session_dependency("adp.application.store")


# A compliance-scoped session (COMPLY-02 research.md D7), used only by the reverse-lookup GET
# /capabilities/{id}/compliance-mappings endpoint below.
_get_compliance_session = session_dependency("adp.compliance.store")


async def _get_biz_session_factory():
    """Returns the session FACTORY (not a session) so a background task can
    open its own fresh session after the request-scoped one above has closed.
    A distinct dependency (not calling bstore._get_session_factory() directly
    inside the background closure) so tests can override it to a SQLite
    factory -- overriding _get_session alone would not reach the background
    task, since it isn't a request-scoped dependency."""
    return bstore._get_session_factory()


async def _get_application_session_factory():
    from adp.application import store as astore
    return astore._get_session_factory()


async def _get_op_store():
    from adp.api.deps import get_operation_store
    return await get_operation_store()


def _make_agent_review_llm_client():
    """Create an LLMClient for the Agent Review toolkit, or the shared stub
    when no API key is configured (mirrors _make_orchestrator in intake.py)."""
    from adp.agents.llm_stub import StubLLMClient
    from adp.api.routers.config import get_api_key, get_extraction_model
    from adp.llm.client import LLMClient

    endpoint = os.environ.get("ADP_LLM_ENDPOINT", "https://api.anthropic.com")
    api_key = get_api_key()
    if not api_key:
        return StubLLMClient(base_url="http://stub", api_key="stub", model="stub")
    return LLMClient(base_url=endpoint, api_key=api_key, model=get_extraction_model())
