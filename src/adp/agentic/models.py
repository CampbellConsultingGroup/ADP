"""Pydantic models for the agent registry (933-agent-registry, ADP-hii).

An agentic solution is an existing Application with application_type 'agentic'; agents live in a
solution-independent registry and join solutions many-to-many (docs/agentic-solutions-plan.md).
Value sets are redefined here rather than imported from adp.application so this package imports no
other domain package (research.md D2/D10).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

AutonomyLevel = Annotated[int, Field(ge=0, le=4)]
HumanApproval = Literal["none", "on_write", "on_irreversible", "always"]
AgentLifecycle = Literal["planned", "active", "sunset", "retired"]
DataClassification = Literal["public", "internal", "confidential", "restricted"]
SolutionRole = Literal["orchestrator", "worker", "reviewer", "router"]
CostPerRun = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=4)]
RunsPerMonth = Annotated[int, Field(ge=0)]

# Fields whose values are gated by READ/WRITE_APPLICATION_COST (Clarification Q2).
COST_FIELDS: frozenset[str] = frozenset({"est_cost_per_run", "runs_per_month"})


def _validate_http_url(v: str | None) -> str | None:
    """Only http/https Agent Card URLs are accepted: the value is rendered as a link for every
    reader (the compliance source_url precedent, 923 security review)."""
    if v is None or not v.strip():
        return None
    scheme = urlparse(v.strip()).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("a2a_card_url must be an http:// or https:// URL")
    return v.strip()


def _validate_name(v: str | None) -> str | None:
    if v is None:
        return v
    stripped = v.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


# ── Errors ────────────────────────────────────────────────────────────────────


class AgentNotFoundError(Exception):
    """Raised when an agent id does not exist."""


class SolutionNotFoundError(Exception):
    """Raised when an application id does not exist."""


class NotAgenticSolutionError(Exception):
    """Raised when adding an agent to an application whose type is not 'agentic' (Q1)."""


class DuplicateSolutionAgentError(Exception):
    """Raised when the agent is already a member of the solution."""


class MembershipNotFoundError(Exception):
    """Raised when the agent is not a member of the solution."""


class OrderMismatchError(Exception):
    """Raised when a reorder's id list is not exactly the solution's current members."""


# ── Agents ────────────────────────────────────────────────────────────────────


class _AgentFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    owner: str | None = Field(default=None, max_length=255)
    model_provider: str | None = Field(default=None, max_length=100)
    model_id: str | None = Field(default=None, max_length=200)
    model_version: str | None = Field(default=None, max_length=100)
    framework: str | None = Field(default=None, max_length=100)
    prompt_ref: str | None = Field(default=None, max_length=200)
    data_classification_max: DataClassification | None = None
    a2a_card_url: str | None = None
    est_cost_per_run: CostPerRun | None = None
    runs_per_month: RunsPerMonth | None = None
    external_registry_ref: str | None = Field(default=None, max_length=255)

    @field_validator("a2a_card_url")
    @classmethod
    def _a2a_card_url_http(cls, v: str | None) -> str | None:
        return _validate_http_url(v)


class AgentCreate(_AgentFields):
    name: str = Field(max_length=255)
    lifecycle_status: AgentLifecycle = "active"
    autonomy_level: AutonomyLevel
    human_approval: HumanApproval

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        return _validate_name(v) or v


class AgentUpdate(_AgentFields):
    """PATCH semantics: omitted fields are unchanged; an explicit null clears an optional field."""

    name: str | None = Field(default=None, max_length=255)
    lifecycle_status: AgentLifecycle | None = None
    autonomy_level: AutonomyLevel | None = None
    human_approval: HumanApproval | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        return _validate_name(v)


class Agent(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner: str | None = None
    lifecycle_status: AgentLifecycle
    model_provider: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    framework: str | None = None
    prompt_ref: str | None = None
    autonomy_level: int
    human_approval: HumanApproval
    data_classification_max: DataClassification | None = None
    a2a_card_url: str | None = None
    est_cost_per_run: Decimal | None = None
    runs_per_month: int | None = None
    cost_visible: bool = True
    external_registry_ref: str | None = None
    solution_count: int = 0
    created_at: datetime
    updated_at: datetime


class AgentSolution(BaseModel):
    app_id: str
    app_name: str
    role: SolutionRole
    position: int


class AgentDetail(Agent):
    solutions: list[AgentSolution] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    items: list[Agent]
    total: int


# ── Solution membership ───────────────────────────────────────────────────────


class SolutionAgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str
    role: SolutionRole


class SolutionAgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: SolutionRole


class SolutionAgentOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_ids: list[str]


class SolutionAgent(BaseModel):
    agent: Agent
    role: SolutionRole
    position: int


class SolutionAgentListResponse(BaseModel):
    items: list[SolutionAgent]
    total: int
