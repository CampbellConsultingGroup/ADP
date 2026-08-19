"""Request-time authorization: map each mutating route to a required ActionType
and enforce it against the caller's role (ADP-SPEC-004).

This is the single place that wires the ``PERMISSION_GRANTS`` table
(:mod:`adp.authz.permissions`) into the HTTP layer. It is installed as an
application-level FastAPI dependency in :func:`adp.api.app.create_app`, so it
runs for every matched route without touching individual router modules.

Design:
  * Safe methods (GET/HEAD/OPTIONS) are never enforced — reads are open, and
    every role holds READ_DESIGN anyway.
  * The required action for a mutating route is resolved from an explicit
    ``(method, path-template)`` map for the design/intake/recommend/config
    routers, plus prefix rules for the registry routers where every mutation
    shares one action.
  * A mutating route that resolves to no action is *not* silently trusted: it is
    allowed at runtime (fail-open, so a new route never 500s) but the
    completeness test (``tests/authz/test_enforcement.py``) fails CI until it is
    mapped here. That keeps the policy exhaustive without runtime fragility.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import is_permitted
from adp.authz.roles import ActionType

_logger = logging.getLogger("adp.authz")

SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

# ── Explicit route → action map ──────────────────────────────────────────────
# Keyed by (HTTP method, full path template as registered on the app). Covers
# the design-scoped routers where mutations map to several distinct actions.
_EXPLICIT_ROUTE_ACTIONS: dict[tuple[str, str], ActionType] = {
    # Design authoring (canonical-model writes)
    ("POST", "/api/v1/designs"): ActionType.WRITE_DESIGN,
    ("POST", "/api/v1/designs/import"): ActionType.WRITE_DESIGN,
    ("POST", "/api/v1/designs/{design_id}/requirements"): ActionType.WRITE_DESIGN,
    ("PUT", "/api/v1/designs/{design_id}/elements/{element_id}/tags"): ActionType.WRITE_DESIGN,
    ("PUT", "/api/v1/designs/{design_id}/layout/{level}"): ActionType.WRITE_DESIGN,
    # ADP-SPEC-054: granular element/relationship CRUD, replacing the broken whole-design PUT.
    ("POST", "/api/v1/designs/{design_id}/elements"): ActionType.WRITE_DESIGN,
    ("PATCH", "/api/v1/designs/{design_id}/elements/{element_id}"): ActionType.WRITE_DESIGN,
    ("DELETE", "/api/v1/designs/{design_id}/elements/{element_id}"): ActionType.WRITE_DESIGN,
    ("POST", "/api/v1/designs/{design_id}/relationships"): ActionType.WRITE_DESIGN,
    (
        "DELETE",
        "/api/v1/designs/{design_id}/relationships/{relationship_id}",
    ): ActionType.WRITE_DESIGN,
    ("PATCH", "/api/v1/designs/{design_id}/lifecycle"): ActionType.WRITE_DESIGN,
    (
        "POST",
        "/api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/confirm",
    ): ActionType.WRITE_DESIGN,
    (
        "POST",
        "/api/v1/designs/{design_id}/intake/{operation_id}/proposals/{proposal_id}/reject",
    ): ActionType.WRITE_DESIGN,
    # AI operations (submit an intake/recommendation/validation run)
    ("POST", "/api/v1/designs/{design_id}/intake"): ActionType.SUBMIT_AI_OPERATION,
    ("POST", "/api/v1/designs/{design_id}/recommend"): ActionType.SUBMIT_AI_OPERATION,
    # ADP-3ei: LLM-as-Judge (008) is wired to an API route for the first time here.
    # Reuses SUBMIT_AI_OPERATION/CONFIRM_RECOMMENDATION rather than introducing a
    # new ActionType — overriding a FAIL verdict is the same class of consequential
    # AI decision as accepting/rejecting a recommendation.
    ("POST", "/api/v1/designs/{design_id}/validate"): ActionType.SUBMIT_AI_OPERATION,
    (
        "POST",
        "/api/v1/designs/{design_id}/validate/{operation_id}/override",
    ): ActionType.CONFIRM_RECOMMENDATION,
    # Deciding on a recommended option is a consequential confirmation
    (
        "POST",
        "/api/v1/designs/{design_id}/recommend/{operation_id}/options/{option_id}/accept",
    ): ActionType.CONFIRM_RECOMMENDATION,
    (
        "POST",
        "/api/v1/designs/{design_id}/recommend/{operation_id}/options/{option_id}/reject",
    ): ActionType.CONFIRM_RECOMMENDATION,
    # Export bundle
    ("POST", "/api/v1/designs/{design_id}/export"): ActionType.EXPORT_DESIGN,
    # Render produces a view (PNG) of the model — a read, not a mutation
    ("POST", "/api/v1/designs/{design_id}/render"): ActionType.READ_DESIGN,
    # APM risk & compliance write (sensitive) — overrides the /applications prefix
    ("PUT", "/api/v1/applications/{app_id}/risk"): ActionType.WRITE_APPLICATION_RISK,
    # APM cost/TCO write (sensitive) — overrides the /applications prefix
    ("PUT", "/api/v1/applications/{app_id}/cost"): ActionType.WRITE_APPLICATION_COST,
    # APM governance/contract write (sensitive) — overrides the /applications prefix
    ("PUT", "/api/v1/applications/{app_id}/governance"): ActionType.WRITE_APPLICATION_GOVERNANCE,
    # LLM provider configuration is an admin action
    ("PUT", "/api/v1/config/llm"): ActionType.MANAGE_CONFIG,
    # ADP-SPEC-039: triggering an Agent Review reuses SUBMIT_AI_OPERATION
    # (research.md D3) -- overrides the /business prefix's WRITE_BUSINESS_ARCH.
    (
        "POST",
        "/api/v1/business/capabilities/{cap_id}/agent-review",
    ): ActionType.SUBMIT_AI_OPERATION,
    # Accepting/rejecting a suggestion is a consequential confirmation, distinct
    # from WRITE_BUSINESS_ARCH (the action gating the underlying write itself).
    (
        "POST",
        "/api/v1/business/capabilities/{cap_id}/agent-review/{operation_id}"
        "/suggestions/{suggestion_id}/accept",
    ): ActionType.CONFIRM_AGENT_SUGGESTION,
    (
        "POST",
        "/api/v1/business/capabilities/{cap_id}/agent-review/{operation_id}"
        "/suggestions/{suggestion_id}/reject",
    ): ActionType.CONFIRM_AGENT_SUGGESTION,
    # ADP-SPEC-040: portfolio-scope Agent Review -- distinct route shape (no
    # {cap_id} segment), same two actions as the per-capability endpoints.
    (
        "POST",
        "/api/v1/business/capabilities/agent-review",
    ): ActionType.SUBMIT_AI_OPERATION,
    (
        "POST",
        "/api/v1/business/capabilities/agent-review/{operation_id}"
        "/suggestions/{suggestion_id}/accept",
    ): ActionType.CONFIRM_AGENT_SUGGESTION,
    (
        "POST",
        "/api/v1/business/capabilities/agent-review/{operation_id}"
        "/suggestions/{suggestion_id}/reject",
    ): ActionType.CONFIRM_AGENT_SUGGESTION,
    # ADP-SPEC-041: starting/using the AI Chat Assistant is a broad feature
    # gate, not a data-sensitivity check (research D6) -- both mutating chat
    # routes map to the same USE_CHAT_ASSISTANT action; GET list/detail are
    # safe methods and never enforced here.
    ("POST", "/api/v1/chat/conversations"): ActionType.USE_CHAT_ASSISTANT,
    (
        "POST",
        "/api/v1/chat/conversations/{conversation_id}/messages",
    ): ActionType.USE_CHAT_ASSISTANT,
}

# ── Prefix rules ─────────────────────────────────────────────────────────────
# For routers whose every mutation maps to a single action. Order matters only
# if prefixes overlap; these are disjoint. Checked after the explicit map.
_PREFIX_ROUTE_ACTIONS: tuple[tuple[str, ActionType], ...] = (
    # ADP-SPEC-042: one rule covers every method under this prefix, since
    # FR-009 gates the whole admin surface -- reads included, not just writes.
    ("/api/v1/admin/agent-prompts", ActionType.MANAGE_AGENT_PROMPTS),
    ("/api/v1/knowledge", ActionType.AMEND_STANDARD),
    ("/api/v1/business/", ActionType.WRITE_BUSINESS_ARCH),
    ("/api/v1/applications", ActionType.WRITE_APPLICATION),
    ("/api/v1/technical-capabilities", ActionType.WRITE_APPLICATION),
    ("/api/v1/integrations", ActionType.WRITE_APPLICATION),
    ("/api/v1/transformation-initiatives", ActionType.WRITE_APPLICATION),
    # ADP-SPEC-046: one rule covers every mutating method under this prefix
    # (create/update/delete/export) -- reads are ungated (nothing about a
    # diagram's content is sensitive the way READ_APPLICATION_RISK etc. are).
    ("/api/v1/diagrams", ActionType.WRITE_DIAGRAM),
    # ADP-d8u.1: reads are ungated (matches /api/v1/business/'s own convention
    # for capabilities/value streams/domains); write endpoints reuse
    # WRITE_BUSINESS_ARCH (research.md Decision 3), no new ActionType.
    ("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH),
    # COMPLY-01: reads (framework/control list, detail) are ungated, matching
    # every other registry domain's convention; every mutation (frameworks and
    # controls alike) requires the new dedicated WRITE_COMPLIANCE action
    # (Clarification Session 2026-08-17 Q1; research.md D4).
    ("/api/v1/compliance/", ActionType.WRITE_COMPLIANCE),
)


def required_action_for(method: str, path_template: str) -> ActionType | None:
    """Return the ActionType a mutating route requires, or None.

    None means either a safe method (never enforced) or an unmapped mutating
    route (a policy gap the completeness test is responsible for catching).
    """
    if method in SAFE_METHODS:
        return None
    explicit = _EXPLICIT_ROUTE_ACTIONS.get((method, path_template))
    if explicit is not None:
        return explicit
    for prefix, action in _PREFIX_ROUTE_ACTIONS:
        if path_template.startswith(prefix):
            return action
    return None


async def enforce_route_permission(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """App-level dependency: 403 when the caller's role may not perform the
    action mapped to the matched route.

    No-op for safe methods. When auth is disabled the caller is
    UNAUTHENTICATED_USER (ENTERPRISE_ARCHITECT), which holds every action, so
    local dev and the auth-disabled E2E suite are unaffected.
    """
    if request.method in SAFE_METHODS:
        return

    route = request.scope.get("route")
    path_template = getattr(route, "path", None)
    if path_template is None:
        # No matched route (should not happen once a dependency runs); allow.
        return

    action = required_action_for(request.method, path_template)
    if action is None:
        # Mutating route with no mapped action. Fail open at runtime; the
        # completeness test fails CI until this is mapped.
        _logger.warning(
            "authz_unmapped_route method=%s path=%s — allowing (map it in enforcement.py)",
            request.method,
            path_template,
        )
        return

    if not is_permitted(user.role, action):
        _logger.warning(
            "permission_denied role=%s action=%s method=%s path=%s",
            user.role,
            action,
            request.method,
            path_template,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Role '{user.role.value}' is not permitted to {action.value}.",
        )


def require_action_dep(action: ActionType):
    """Build a FastAPI dependency that 403s unless the caller holds ``action``.

    Use this to gate sensitive *reads*: the app-level enforcer intentionally
    exempts safe methods (GET/HEAD/OPTIONS), so read authorization must be
    attached per-route via ``dependencies=[Depends(require_action_dep(...))]``.
    Under auth-disabled dev/test the caller is ENTERPRISE_ARCHITECT (holds every
    action), so those environments are unaffected.
    """

    async def _dep(user: AuthenticatedUser = Depends(get_current_user)) -> None:
        if not is_permitted(user.role, action):
            _logger.warning(
                "permission_denied role=%s action=%s (sensitive read)", user.role, action
            )
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role.value}' is not permitted to {action.value}.",
            )

    return _dep
