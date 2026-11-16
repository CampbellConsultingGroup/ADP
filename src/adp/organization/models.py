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


class LevelRuleError(OrganizationError):
    """941: a capability mapping at a level its role doesn't allow (422)."""


class UnknownReferenceError(OrganizationError):
    """941: an org unit or geography id in a request body that doesn't exist (422)."""


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


# ── Capability <-> org unit mappings (941-capability-org-mappings, ADP-55k.2) ──
#
# owner: L1/L2, at most one per capability, no geography. performer: L3, optional geography.
# contributor: L3, no geography. Effective owner, findings and footprints are derived on read and
# never stored (test_cap_org_analysis_not_stored.py).

CapabilityOrgRole = Literal["owner", "performer", "contributor"]


class CapabilityOrgMapping(_Model):
    id: str
    capability_id: str
    org_unit: Ref
    role: CapabilityOrgRole
    geography: Ref | None = None
    # FR-006, derived: the geography is neither one of the unit's operating geographies nor
    # inside one (only ever true for a performer whose unit has operating geographies).
    outside_operating_geographies: bool = False


class SetOwner(_Model):
    org_unit_id: str | None = None


class AddMapping(_Model):
    capability_id: str
    org_unit_id: str
    role: Literal["performer", "contributor"]
    geography_id: str | None = None

    @model_validator(mode="after")
    def _geography_only_on_performer(self) -> "AddMapping":
        if self.geography_id is not None and self.role != "performer":
            raise ValueError("Only performers can name a geography")
        return self


class CapabilityOrgView(_Model):
    capability_id: str
    level: int
    owner: Ref | None = None
    effective_owner: Ref | None = None
    owner_inherited_from: Ref | None = None  # the ancestor capability the owner comes from
    performers: list[CapabilityOrgMapping] = []
    contributors: list[CapabilityOrgMapping] = []


class CapabilityOrgMappingsResponse(_Model):
    items: list[CapabilityOrgView]


class FindingCapability(_Model):
    id: str
    name: str
    level: int
    path: list[Ref] = []


class SharedServicePerformer(_Model):
    org_unit: Ref
    org_unit_path: list[Ref] = []
    geographies: list[Ref] = []
    folded_into: Ref | None = None  # an ancestor unit that also performs this capability


class SharedServiceCandidate(_Model):
    capability: FindingCapability
    branches: int
    performers: list[SharedServicePerformer]


class FindingCounts(_Model):
    no_owner: int
    shared_service: int
    unmapped: int
    owned_no_performer: int
    l1_l2_total: int
    l3_total: int


class CapabilityOrgFindings(_Model):
    no_owner: list[FindingCapability]
    shared_service: list[SharedServiceCandidate]
    unmapped: list[FindingCapability]
    owned_no_performer: list[FindingCapability]
    counts: FindingCounts


class FootprintPerformer(_Model):
    org_unit: Ref
    geographies: list[Ref] = []


class FootprintL3(_Model):
    capability: Ref
    performed_by: list[FootprintPerformer]


class FootprintL2(_Model):
    capability: Ref
    l3_count: int
    l3s: list[FootprintL3]


class FootprintL1(_Model):
    capability: Ref
    l3_count: int
    l2s: list[FootprintL2]


class FootprintEntry(_Model):
    capability: FindingCapability
    org_unit: Ref


class OrgUnitFootprint(_Model):
    org_unit: Ref
    includes_descendants: bool = True
    performs: list[FootprintL1]
    l3_total: int
    owns: list[FootprintEntry]
    contributes: list[FootprintEntry]
