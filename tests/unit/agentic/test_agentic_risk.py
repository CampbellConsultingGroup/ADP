"""Pure tests for the agentic risk band (944-agent-traceability, ADP-12x, US3, FR-013..FR-016).

Rule (confirmed in /speckit-clarify): sensitive = confidential | restricted.
  high   = autonomy >= 3 and (approval == none or sensitive)
  medium = otherwise, autonomy >= 2 or sensitive
  low    = everything else
"""

from __future__ import annotations

import itertools

import pytest

from adp.agentic.risk import agent_risk, solution_risk

APPROVALS = ["none", "on_write", "on_irreversible", "always"]
CLASSES = [None, "public", "internal", "confidential", "restricted"]


def _expected(autonomy: int, approval: str, cls: str | None) -> str:
    sensitive = cls in ("confidential", "restricted")
    if autonomy >= 3 and (approval == "none" or sensitive):
        return "high"
    if autonomy >= 2 or sensitive:
        return "medium"
    return "low"


@pytest.mark.parametrize(
    "autonomy,approval,cls", list(itertools.product(range(5), APPROVALS, CLASSES))
)
def test_band_matrix(autonomy, approval, cls):
    risk = agent_risk(autonomy, approval, cls)
    assert risk.band == _expected(autonomy, approval, cls)
    assert risk.not_considered == ["tool_side_effects"]
    assert risk.missing == (["data_classification"] if cls is None else [])


def _codes(risk) -> list[str]:
    return [f.code for f in risk.factors]


def test_high_factors_name_what_set_the_band():
    risk = agent_risk(4, "none", "restricted")
    assert _codes(risk) == ["autonomy", "no_human_approval", "sensitive_data"]
    assert [f.label for f in risk.factors] == [
        "autonomy 4", "no human approval", "restricted data"
    ]
    assert _codes(agent_risk(3, "always", "confidential")) == ["autonomy", "sensitive_data"]
    assert _codes(agent_risk(3, "none", "internal")) == ["autonomy", "no_human_approval"]


def test_medium_and_low_factors():
    assert _codes(agent_risk(2, "always", "public")) == ["autonomy"]
    assert _codes(agent_risk(1, "always", "restricted")) == ["sensitive_data"]
    assert _codes(agent_risk(3, "always", None)) == ["autonomy"]
    assert _codes(agent_risk(1, "none", "internal")) == []


def _member(agent_id: str, band_args: tuple, lifecycle: str = "active"):
    return (agent_id, agent_id.upper(), lifecycle, agent_risk(*band_args))


def test_solution_band_is_highest_non_retired():
    out = solution_risk(
        [
            _member("a", (1, "always", "public")),
            _member("b", (4, "none", None)),
            _member("c", (4, "none", None), lifecycle="planned"),
            _member("d", (4, "none", "restricted"), lifecycle="retired"),
            _member("e", (2, "always", None), lifecycle="sunset"),
        ]
    )
    assert out.band == "high"
    assert [(a.id, a.name) for a in out.agents] == [("b", "B"), ("c", "C")]
    assert out.not_considered == ["tool_side_effects"]


def test_solution_retired_agent_excluded_lowers_band():
    out = solution_risk(
        [_member("a", (2, "always", None)), _member("b", (4, "none", None), "retired")]
    )
    assert out.band == "medium"
    assert [a.id for a in out.agents] == ["a"]


@pytest.mark.parametrize("members", [[], [_member("x", (4, "none", None), "retired")]])
def test_solution_no_agents(members):
    out = solution_risk(members)
    assert out.band is None
    assert out.agents == []
