"""Agentic risk band (944-agent-traceability, ADP-12x, US3). Pure functions, no I/O.

Derived on read from an agent's own fields and never stored (spec.md FR-016, SC-006), following
compute_compliance_status and 938's risk band. The rule (FR-013, confirmed in clarification):

  sensitive = data classification confidential or restricted
  high      = autonomy >= 3 and (human approval "none" or sensitive)
  medium    = otherwise, autonomy >= 2 or sensitive
  low       = everything else

Tool side effects are not considered yet: tools arrive with P2 (ADP-a00), which adds an
"irreversible tool without a human gate" factor without changing these result shapes (N1).
"""

from __future__ import annotations

from collections.abc import Iterable

from adp.agentic.models import (
    AgenticRisk,
    NotConsidered,
    RiskAgentRef,
    RiskBand,
    RiskFactor,
    SolutionAgenticRisk,
)

_SENSITIVE = frozenset({"confidential", "restricted"})
_RANK: dict[RiskBand, int] = {"low": 0, "medium": 1, "high": 2}
_NOT_CONSIDERED: tuple[NotConsidered, ...] = ("tool_side_effects",)


def agent_risk(
    autonomy_level: int, human_approval: str, data_classification_max: str | None
) -> AgenticRisk:
    sensitive = data_classification_max in _SENSITIVE
    no_approval = human_approval == "none"
    autonomy = RiskFactor(code="autonomy", label=f"autonomy {autonomy_level}")
    data = RiskFactor(code="sensitive_data", label=f"{data_classification_max} data")

    factors: list[RiskFactor]
    band: RiskBand
    if autonomy_level >= 3 and (no_approval or sensitive):
        band = "high"
        factors = [autonomy]
        if no_approval:
            factors.append(RiskFactor(code="no_human_approval", label="no human approval"))
        if sensitive:
            factors.append(data)
    elif autonomy_level >= 2 or sensitive:
        band = "medium"
        factors = ([autonomy] if autonomy_level >= 2 else []) + ([data] if sensitive else [])
    else:
        band = "low"
        factors = []

    return AgenticRisk(
        band=band,
        factors=factors,
        missing=["data_classification"] if data_classification_max is None else [],
        not_considered=list(_NOT_CONSIDERED),
    )


def solution_risk(
    members: Iterable[tuple[str, str, str, AgenticRisk]],
) -> SolutionAgenticRisk:
    """members: (agent_id, agent_name, lifecycle_status, agentic_risk). Retired agents are left
    out; planned and sunset agents count. No counted agent gives band None ("No agents")."""
    counted = [m for m in members if m[2] != "retired"]
    if not counted:
        return SolutionAgenticRisk(band=None, not_considered=list(_NOT_CONSIDERED))
    top = max(_RANK[m[3].band] for m in counted)
    band = next(b for b, r in _RANK.items() if r == top)
    return SolutionAgenticRisk(
        band=band,
        agents=[RiskAgentRef(id=m[0], name=m[1]) for m in counted if _RANK[m[3].band] == top],
        not_considered=list(_NOT_CONSIDERED),
    )
