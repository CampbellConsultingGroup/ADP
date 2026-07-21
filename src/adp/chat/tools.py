"""Read-only tool registry for the AI Chat Assistant (ADP-SPEC-041 US2).

Every handler is a thin wrapper around an existing store/aggregate function
already used by a REST endpoint -- no new business logic, no write path
(SC-002; mechanically verified in tests/unit/chat/test_tools_boundary.py,
mirroring ADP-SPEC-039's test_toolkit_boundary.py).

A gated handler (the three sensitive application categories) takes the
caller's role and returns {"permitted": False} -- never an error, never a
silently-empty result -- when is_permitted() fails (research D5): the
enforcement point is this code path, not a prompt instruction, so no
cleverly-worded question can talk the assistant out of it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType, PersonaRole


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[dict[str, Any]]]


_CAPABILITY_ID_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"capability_id": {"type": "string", "description": "Business capability id"}},
    "required": ["capability_id"],
}

_APPLICATION_ID_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"application_id": {"type": "string", "description": "Application id"}},
    "required": ["application_id"],
}

_NO_ARGS_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}}


async def get_capability(
    args: dict[str, Any], role: PersonaRole, *, biz_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    from adp.business import store as bstore

    cap = await bstore.get_capability(args["capability_id"], biz_session)
    if cap is None:
        return {"found": False}
    return {"found": True, "capability": cap.model_dump(mode="json")}


async def get_application(
    args: dict[str, Any], role: PersonaRole, *, app_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    from adp.application import store as astore

    app = await astore.get_application(args["application_id"], app_session)
    if app is None:
        return {"found": False}
    return {"found": True, "application": app.model_dump(mode="json")}


async def get_application_risk(
    args: dict[str, Any], role: PersonaRole, *, app_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    if not is_permitted(role, ActionType.READ_APPLICATION_RISK):
        return {"permitted": False}
    from adp.application import store as astore

    risk = await astore.get_application_risk(args["application_id"], app_session)
    if risk is None:
        return {"permitted": True, "found": False}
    return {"permitted": True, "found": True, "risk": risk.model_dump(mode="json")}


async def get_application_cost(
    args: dict[str, Any], role: PersonaRole, *, app_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    if not is_permitted(role, ActionType.READ_APPLICATION_COST):
        return {"permitted": False}
    from adp.application import store as astore

    cost = await astore.get_application_cost(args["application_id"], app_session)
    if cost is None:
        return {"permitted": True, "found": False}
    return {"permitted": True, "found": True, "cost": cost.model_dump(mode="json")}


async def get_application_governance(
    args: dict[str, Any], role: PersonaRole, *, app_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    if not is_permitted(role, ActionType.READ_APPLICATION_GOVERNANCE):
        return {"permitted": False}
    from adp.application import store as astore

    governance = await astore.get_application_governance(args["application_id"], app_session)
    if governance is None:
        return {"permitted": True, "found": False}
    return {"permitted": True, "found": True, "governance": governance.model_dump(mode="json")}


async def portfolio_summary(
    args: dict[str, Any], role: PersonaRole, *, kb_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    from adp.api.routers.portfolio import get_portfolio_summary

    summary = await get_portfolio_summary(session=kb_session)
    return summary.model_dump(mode="json")


async def governance_status(
    args: dict[str, Any], role: PersonaRole, *, kb_session: AsyncSession, **_: Any
) -> dict[str, Any]:
    from adp.api.routers.governance import get_governance_status

    status = await get_governance_status(session=kb_session)
    return status.model_dump(mode="json")


TOOL_REGISTRY: list[ToolDefinition] = [
    ToolDefinition(
        name="get_capability",
        description=(
            "Look up a single business capability by id: name, description, "
            "level, and maturity."
        ),
        input_schema=_CAPABILITY_ID_SCHEMA,
        handler=get_capability,
    ),
    ToolDefinition(
        name="get_application",
        description=(
            "Look up a single application's non-sensitive profile by id: name, "
            "description, vendor, owners, lifecycle status."
        ),
        input_schema=_APPLICATION_ID_SCHEMA,
        handler=get_application,
    ),
    ToolDefinition(
        name="get_application_risk",
        description=(
            "Look up an application's risk & compliance data by id. Requires the "
            "caller to hold risk-read access; returns {'permitted': false} otherwise."
        ),
        input_schema=_APPLICATION_ID_SCHEMA,
        handler=get_application_risk,
    ),
    ToolDefinition(
        name="get_application_cost",
        description=(
            "Look up an application's cost/TCO data by id. Requires the caller "
            "to hold cost-read access; returns {'permitted': false} otherwise."
        ),
        input_schema=_APPLICATION_ID_SCHEMA,
        handler=get_application_cost,
    ),
    ToolDefinition(
        name="get_application_governance",
        description=(
            "Look up an application's governance/contract data by id. Requires "
            "the caller to hold governance-read access; returns "
            "{'permitted': false} otherwise."
        ),
        input_schema=_APPLICATION_ID_SCHEMA,
        handler=get_application_governance,
    ),
    ToolDefinition(
        name="portfolio_summary",
        description=(
            "Get a portfolio-wide health summary: design counts by lifecycle "
            "status and overdue-review count."
        ),
        input_schema=_NO_ARGS_SCHEMA,
        handler=portfolio_summary,
    ),
    ToolDefinition(
        name="governance_status",
        description=(
            "Get per-design governance status: last activity, audit count, "
            "accepted recommendations, reasoning record counts."
        ),
        input_schema=_NO_ARGS_SCHEMA,
        handler=governance_status,
    ),
]

_BY_NAME: dict[str, ToolDefinition] = {t.name: t for t in TOOL_REGISTRY}


def anthropic_tool_specs() -> list[dict[str, Any]]:
    """TOOL_REGISTRY rendered as the Anthropic Messages API `tools` param shape."""
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOL_REGISTRY
    ]


async def dispatch_tool(
    name: str,
    args: dict[str, Any],
    role: PersonaRole,
    *,
    sessions: dict[str, AsyncSession],
) -> dict[str, Any]:
    """Look up `name` in TOOL_REGISTRY and invoke its handler.

    `sessions` carries every session a handler might need (biz_session,
    app_session, kb_session); each handler declares only the kwarg(s) it
    uses and swallows the rest via **_, so one dispatch site works for every
    tool regardless of which session(s) it actually touches.
    """
    tool = _BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool {name!r}"}
    return await tool.handler(args, role, **sessions)
