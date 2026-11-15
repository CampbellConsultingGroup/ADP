"""Application capability models (937-application-capabilities, ADP-6et.1).

An application capability is a logical capability delivered by software ("Price Rule
Evaluation"). It sits between business capabilities (what the business does) and technical
capabilities (the platform underneath). One shared L1-L3 catalog; only L3s are mapped.

Kept out of ``adp.application.models`` (already ~900 lines) as its own module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

AppCapLevel = Literal[1, 2, 3]

# Derived on read, never stored (spec FR-017).
AppCapWarning = Literal["missing_technical_capability"]
MISSING_TECHNICAL_CAPABILITY: AppCapWarning = "missing_technical_capability"

# Rule messages (contracts/rest-api.md). Shown to users verbatim.
RULE_APP_CAP_L3 = "application capabilities are mapped at L3; L1 and L2 are for grouping"
RULE_BUSINESS_L3 = "business capabilities are mapped at L3"
RULE_TECH_L2_L3 = "map to a technical capability at L2 or L3"

LinkKind = Literal["business", "technical", "application"]


def _not_blank(v: str | None) -> str | None:
    if v is not None and not v.strip():
        raise ValueError("name must not be blank")
    return v.strip() if v is not None else v


class CapRef(BaseModel):
    """A capability reference with its level (used for every layer)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    level: int


class LinkedCapRef(CapRef):
    """A linked capability with its ancestor path (L1 first), for display."""

    path: list[CapRef] = []


class AppRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str


class ApplicationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str | None
    parent_id: str | None
    level: AppCapLevel
    created_at: datetime
    updated_at: datetime
    business_capability_count: int = 0
    technical_capability_count: int = 0
    realization_count: int = 0
    warnings: list[AppCapWarning] = []


class ApplicationCapabilityDetail(ApplicationCapability):
    path: list[CapRef] = []
    business_capabilities: list[LinkedCapRef] = []
    technical_capabilities: list[LinkedCapRef] = []
    realized_by: list[AppRef] = []


class ApplicationCapabilityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


class ApplicationCapabilityUpdate(BaseModel):
    """Parent and level are immutable after creation (spec FR-005)."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        return _not_blank(v)


class ApplicationCapabilityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ApplicationCapability]
    total: int


class AppCapSummary(BaseModel):
    """An application capability as seen from another layer (reverse lookups)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    level: AppCapLevel
    path: list[CapRef] = []
    warnings: list[AppCapWarning] = []
    realized_by: list[AppRef] = []


class BusinessCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_capability_id: str


class TechCapabilityLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tech_cap_id: str


class RealizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_id: str


# ── Errors ────────────────────────────────────────────────────────────────────


class AppCapError(Exception):
    """Base class; the router maps each subclass to one status code."""


class AppCapNotFoundError(AppCapError):
    """404: the application capability, or the far end of a link, does not exist."""


class AppCapDepthError(AppCapError):
    """422: the parent is already level 3."""


class AppCapHasChildrenError(AppCapError):
    """409: delete refused while children exist."""


class DuplicateSiblingNameError(AppCapError):
    """409: a sibling already has this name (case-insensitive)."""


class CapabilityLevelError(AppCapError):
    """422: a link would break a mapping-level rule. The message names the rule."""


class DuplicateAppCapLinkError(AppCapError):
    """409: the link already exists."""
