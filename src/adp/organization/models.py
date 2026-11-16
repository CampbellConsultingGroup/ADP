"""Org Units and Geography models (940-org-units-geography, ADP-55k.1).

Two governed reference trees, each at most 3 levels, under Business Architecture:

    Org Unit:  enterprise (1) -> division / business unit (2) -> function / department (3)
    Geography: global (1)     -> region (2)                   -> country (3)

Region is a separate axis from the org tree (epic ADP-55k decision D2): an org unit operates in
any number of geographies and may have one primary geography. Named "Org Unit" because compliance
already uses "organization" to mean estate-wide scope (control_organization_mapping).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

OrgUnitKind = Literal["enterprise", "division", "function"]
GeographyKind = Literal["global", "region", "country"]

ORG_UNIT_KINDS: dict[int, OrgUnitKind] = {1: "enterprise", 2: "division", 3: "function"}
GEOGRAPHY_KINDS: dict[int, GeographyKind] = {1: "global", 2: "region", 3: "country"}

ISO2 = re.compile(r"^[A-Z]{2}$")


# ── Errors ────────────────────────────────────────────────────────────────────


class OrganizationError(Exception):
    """Base class; the router maps each subclass to an HTTP status."""


class OrgNotFoundError(OrganizationError):
    pass


class DepthError(OrganizationError):
    pass


class HasChildrenError(OrganizationError):
    pass


class DuplicateSiblingError(OrganizationError):
    pass


class DuplicateCodeError(OrganizationError):
    pass


class DuplicateLinkError(OrganizationError):
    pass


class InvalidCodeError(OrganizationError):
    pass


# ── Shared ────────────────────────────────────────────────────────────────────


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ref(_Model):
    id: str
    name: str
    level: int


def _name(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        raise ValueError("name must not be blank")
    return v


# ── Org units ─────────────────────────────────────────────────────────────────


class OrgUnit(_Model):
    id: str
    name: str
    description: str | None
    parent_id: str | None
    level: int
    kind: OrgUnitKind
    primary_geography_id: str | None
    geography_ids: list[str] = []
    path: list[Ref] = []
    application_count: int = 0
    created_at: datetime
    updated_at: datetime


class OrgUnitDetail(OrgUnit):
    applications: list[Ref] = []
    geographies: list[Ref] = []


class OrgUnitCreate(_Model):
    name: str
    description: str | None = None
    parent_id: str | None = None
    primary_geography_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)


class OrgUnitUpdate(_Model):
    """Parent and level are fixed after creation. An explicit null primary geography clears it."""

    name: str | None = None
    description: str | None = None
    primary_geography_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)


class OrgUnitListResponse(_Model):
    items: list[OrgUnit]
    total: int


class GeographyLinkCreate(_Model):
    geography_id: str


# ── Geography ─────────────────────────────────────────────────────────────────


class Geography(_Model):
    id: str
    name: str
    code: str | None
    m49: str | None
    parent_id: str | None
    level: int
    kind: GeographyKind
    path: list[Ref] = []
    org_unit_count: int = 0


class GeographyCreate(_Model):
    name: str
    code: str | None = None
    m49: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None


class GeographyUpdate(_Model):
    name: str | None = None
    code: str | None = None
    m49: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else None


class GeographyListResponse(_Model):
    items: list[Geography]
    total: int


# ── Review queue ──────────────────────────────────────────────────────────────


class UnmatchedValue(_Model):
    value: str
    application_count: int
    sample_applications: list[Ref] = []


class UnmatchedListResponse(_Model):
    items: list[UnmatchedValue]
    total: int


class ResolveCreate(_Model):
    name: str
    description: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)


class ResolveUnmatched(_Model):
    """Map one exact free-text value to an org unit: an existing one, or one created here."""

    value: str
    org_unit_id: str | None = None
    create: ResolveCreate | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> ResolveUnmatched:
        if (self.org_unit_id is None) == (self.create is None):
            raise ValueError("Give exactly one of org_unit_id or create")
        return self


class ResolveResult(_Model):
    org_unit: OrgUnit
    updated_count: int
