"""Permission table, confirmation requirements, and enforcement functions.

The PERMISSION_GRANTS table is the single source of truth for role-based
authorization. Any change requires a PERMISSIONS_VERSION bump and a spec
amendment per ART-XV / ADP-SPEC-004.
"""

from __future__ import annotations

import logging

from adp.authz.roles import ActionType, PersonaRole

_logger = logging.getLogger("adp.authz")

# Changelog:
#   1.0.0 — initial matrix (ADP-SPEC-004).
#   1.1.0 — added WRITE_BUSINESS_ARCH, WRITE_APPLICATION (granted to the three
#           architect roles) and MANAGE_CONFIG (enterprise-only) so the newer
#           business-architecture, application-registry, and config routers are
#           covered by action-based enforcement (ADP-SPEC-004 amendment).
#   1.2.0 — added READ_APPLICATION_RISK / WRITE_APPLICATION_RISK (solution &
#           technical architects; enterprise via all-actions) to gate the
#           sensitive application risk & compliance register (ADP-SPEC-038 US3).
#           Reviewers do NOT hold these — risk data is not open to every reader.
#   1.3.0 — added READ_APPLICATION_COST / WRITE_APPLICATION_COST (same three
#           architect roles) to gate the sensitive TCO / cost register
#           (ADP-SPEC-038 US4). Reviewers do NOT hold these either.
#   1.4.0 — added READ_APPLICATION_GOVERNANCE / WRITE_APPLICATION_GOVERNANCE
#           (same three architect roles) to gate the sensitive contract/
#           governance register (ADP-SPEC-038 US7). Reviewers do NOT hold
#           these either.
#   1.5.0 — added CONFIRM_AGENT_SUGGESTION (solution & technical architects;
#           enterprise via all-actions) to gate accepting/rejecting an Agent
#           Review suggestion (ADP-SPEC-039), distinct from WRITE_BUSINESS_ARCH
#           (the underlying write) and from SUBMIT_AI_OPERATION (reused,
#           unchanged, for triggering the review). Reviewers do NOT hold it.
#   1.6.0 — added USE_CHAT_ASSISTANT, granted to every role including
#           Reviewer (ADP-SPEC-041) -- unlike CONFIRM_AGENT_SUGGESTION, this
#           gates a read-only feature, not a consequential write, so it is
#           NOT in REQUIRES_CONFIRMATION; sensitive application data is
#           filtered per-question inside the chat's tool layer instead.
#   1.7.0 — added PersonaRole.PLATFORM_ADMIN and ActionType.MANAGE_AGENT_PROMPTS
#           (ADP-SPEC-042). PLATFORM_ADMIN holds every action Enterprise
#           Architect held today, plus this new one (least-surprise for
#           existing ADPAdministrator group members). ENTERPRISE_ARCHITECT's
#           previously-unconditional "all actions" wildcard grant is
#           DELIBERATELY narrowed to exclude MANAGE_AGENT_PROMPTS -- per
#           Clarification Session 2026-07-24 Q1, no architect role, including
#           Enterprise Architect, may gain admin-screen access solely by
#           virtue of that role. This is the one place a prior "has every
#           action" invariant is intentionally weakened, not just extended.
#   1.8.0 — added WRITE_DIAGRAM (ADP-SPEC-046) to gate creating/editing/
#           deleting a non-C4 diagram, granted to the three architect roles
#           (same shape as WRITE_BUSINESS_ARCH/WRITE_APPLICATION); Reviewer
#           does not hold it. Enterprise Architect and Platform Admin receive
#           it automatically via their existing wildcard grants -- no change
#           needed to either of those two entries below.
#   1.9.0 — added ActionType.WRITE_COMPLIANCE (COMPLY-01), granted to
#           Solution/Technical Architect; Enterprise Architect and Platform
#           Admin receive it via their existing wildcard grants -- no change
#           to either entry. Reviewer does not hold it.
#   1.10.0 — added ActionType.MANAGE_SCORING_RUBRICS (ADP-68z, admin UI for
#           editing scoring rubric weights). Platform Admin receives it via
#           its existing wildcard grant -- no change to that entry. Mirrors
#           1.7.0's MANAGE_AGENT_PROMPTS precedent exactly: Enterprise
#           Architect's wildcard is narrowed to exclude this action too --
#           no architect role gains admin-screen access solely by virtue of
#           that role, this being another such screen.
PERMISSIONS_VERSION = "1.10.0"

# ── Permission table ─────────────────────────────────────────────────────────
# Maps each PersonaRole to the frozenset of ActionTypes it may perform.
# This is the machine-executable form of the spec's governance table.

PERMISSION_GRANTS: dict[PersonaRole, frozenset[ActionType]] = {
    # All actions EXCEPT MANAGE_AGENT_PROMPTS (v1.7.0) and MANAGE_SCORING_RUBRICS
    # (v1.10.0) -- see changelog above.
    PersonaRole.ENTERPRISE_ARCHITECT: frozenset(ActionType) - {
        ActionType.MANAGE_AGENT_PROMPTS, ActionType.MANAGE_SCORING_RUBRICS,
    },
    # Everything Enterprise Architect has, plus MANAGE_AGENT_PROMPTS (v1.7.0).
    PersonaRole.PLATFORM_ADMIN: frozenset(ActionType),
    PersonaRole.SOLUTION_ARCHITECT: frozenset({
        ActionType.READ_DESIGN,
        ActionType.WRITE_DESIGN,
        ActionType.SUBMIT_AI_OPERATION,
        ActionType.CONFIRM_RECOMMENDATION,
        ActionType.OVERRIDE_VERDICT,
        ActionType.ADD_FINDING,
        ActionType.EXPORT_DESIGN,
        ActionType.WRITE_BUSINESS_ARCH,
        ActionType.WRITE_APPLICATION,
        ActionType.READ_APPLICATION_RISK,
        ActionType.WRITE_APPLICATION_RISK,
        ActionType.READ_APPLICATION_COST,
        ActionType.WRITE_APPLICATION_COST,
        ActionType.READ_APPLICATION_GOVERNANCE,
        ActionType.WRITE_APPLICATION_GOVERNANCE,
        ActionType.CONFIRM_AGENT_SUGGESTION,
        ActionType.USE_CHAT_ASSISTANT,
        ActionType.WRITE_DIAGRAM,
        ActionType.WRITE_COMPLIANCE,
    }),
    PersonaRole.TECHNICAL_ARCHITECT: frozenset({
        ActionType.READ_DESIGN,
        ActionType.WRITE_DESIGN,
        ActionType.SUBMIT_AI_OPERATION,
        ActionType.CONFIRM_RECOMMENDATION,
        ActionType.ADD_FINDING,
        ActionType.WRITE_BUSINESS_ARCH,
        ActionType.WRITE_APPLICATION,
        ActionType.READ_APPLICATION_RISK,
        ActionType.WRITE_APPLICATION_RISK,
        ActionType.READ_APPLICATION_COST,
        ActionType.WRITE_APPLICATION_COST,
        ActionType.READ_APPLICATION_GOVERNANCE,
        ActionType.WRITE_APPLICATION_GOVERNANCE,
        ActionType.CONFIRM_AGENT_SUGGESTION,
        ActionType.USE_CHAT_ASSISTANT,
        ActionType.WRITE_DIAGRAM,
        ActionType.WRITE_COMPLIANCE,
    }),
    PersonaRole.REVIEWER: frozenset({
        ActionType.READ_DESIGN,
        ActionType.OVERRIDE_VERDICT,
        ActionType.ADD_FINDING,
        ActionType.USE_CHAT_ASSISTANT,
    }),
}

# ── Confirmation requirements ────────────────────────────────────────────────
# Actions that require a per-action confirmation payload (ART-VIII / QG-14).
# One approval MUST NOT generalize to any subsequent action.

REQUIRES_CONFIRMATION: frozenset[ActionType] = frozenset({
    ActionType.CONFIRM_RECOMMENDATION,
    ActionType.OVERRIDE_VERDICT,
    ActionType.AMEND_STANDARD,
    ActionType.MANAGE_ROLES,
    ActionType.EXPORT_DESIGN,
    ActionType.CONFIRM_AGENT_SUGGESTION,
    ActionType.MANAGE_AGENT_PROMPTS,
    ActionType.MANAGE_SCORING_RUBRICS,
})


# ── Typed exception ──────────────────────────────────────────────────────────

class PermissionDeniedError(Exception):
    """Raised when a role is not permitted to perform an action.

    Decoupled from HTTP — API layers catch this and convert to 403.
    """

    def __init__(self, role: PersonaRole, action: ActionType, message: str) -> None:
        self.role = role
        self.action = action
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return self.message


# ── Enforcement functions ────────────────────────────────────────────────────

def is_permitted(role: PersonaRole, action: ActionType) -> bool:
    """Return True if role may perform action; False otherwise. Never raises."""
    return action in PERMISSION_GRANTS.get(role, frozenset())


def requires_confirmation(action: ActionType) -> bool:
    """Return True if action requires a per-action confirmation payload."""
    return action in REQUIRES_CONFIRMATION


def require_action(role: PersonaRole, action: ActionType) -> None:
    """Raise PermissionDeniedError if role is not permitted to perform action.

    Also emits a WARNING log for observability (spec US2 scenario 1).
    Does NOT check confirmation — that is a separate caller concern.
    """
    if not is_permitted(role, action):
        msg = f"{role} is not permitted to {action}"
        _logger.warning("permission_denied role=%s action=%s", role, action)
        raise PermissionDeniedError(role, action, msg)
