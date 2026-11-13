"""Unit tests for adp.agentic.models validation (933-agent-registry, ADP-hii)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from adp.agentic.models import AgentCreate, AgentUpdate, SolutionAgentCreate

_REQUIRED = {"name": "Triage", "autonomy_level": 2, "human_approval": "on_write"}


def test_minimal_agent_defaults_to_active():
    agent = AgentCreate(**_REQUIRED)
    assert agent.lifecycle_status == "active"
    assert agent.est_cost_per_run is None


@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_autonomy_scale_accepts_0_to_4(level):
    assert AgentCreate(**{**_REQUIRED, "autonomy_level": level}).autonomy_level == level


@pytest.mark.parametrize(
    "override",
    [
        {"autonomy_level": 5},
        {"autonomy_level": -1},
        {"human_approval": "sometimes"},
        {"lifecycle_status": "deprecated"},
        {"data_classification_max": "secret"},
        {"name": "   "},
        {"est_cost_per_run": -0.01},
        {"runs_per_month": -1},
        {"prompt_ref": "x" * 201},
        {"unexpected": 1},
    ],
)
def test_invalid_values_rejected(override):
    with pytest.raises(ValidationError):
        AgentCreate(**{**_REQUIRED, **override})


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "ftp://host/card"])
def test_a2a_card_url_rejects_non_http_schemes(url):
    with pytest.raises(ValidationError):
        AgentCreate(**_REQUIRED, a2a_card_url=url)


def test_a2a_card_url_accepts_https_and_blank_becomes_none():
    ok = AgentCreate(**_REQUIRED, a2a_card_url=" https://x.example/.well-known/agent-card.json ")
    assert ok.a2a_card_url == "https://x.example/.well-known/agent-card.json"
    assert AgentCreate(**_REQUIRED, a2a_card_url="  ").a2a_card_url is None


def test_name_is_stripped_and_cost_is_decimal():
    agent = AgentCreate(**{**_REQUIRED, "name": "  Triage  "}, est_cost_per_run="0.042")
    assert agent.name == "Triage"
    assert agent.est_cost_per_run == Decimal("0.042")


def test_update_tracks_explicit_fields_only():
    body = AgentUpdate(owner=None, autonomy_level=3)
    assert body.model_fields_set == {"owner", "autonomy_level"}
    with pytest.raises(ValidationError):
        AgentUpdate(name="  ")


def test_membership_role_is_a_closed_set():
    assert SolutionAgentCreate(agent_id="a", role="orchestrator").role == "orchestrator"
    with pytest.raises(ValidationError):
        SolutionAgentCreate(agent_id="a", role="boss")
