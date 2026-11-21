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
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OrgUnitKind = Literal["enterprise", "division", "function"]
GeographyKind = Literal["global", "region", "country"]
PlaceType = Literal["country", "subdivision", "authority", "residual"]

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


class ReadOnlyHierarchyError(OrganizationError):
    """946: the hierarchy has a system of record (the reference hierarchy, imported ones)."""


class HierarchyRuleError(OrganizationError):
    """946: a write would break a hierarchy rule (cycle, dates, wrong hierarchy)."""


class MembershipConflictError(OrganizationError):
    """946: a strict tree already has another parent for that member in that period, or the
    same membership already covers part of the period."""


class GeographyPermissionError(OrganizationError):
    """946 Q2: regulatory, data residency and tax hierarchies need write_compliance."""


class UnknownReferenceError(OrganizationError):
    """941: an org unit or geography id in a request body that doesn't exist (422)."""


class LinkRuleError(OrganizationError):
    """947: a geography link the relation matrix or the dates don't allow (422)."""


class DuplicateNameError(OrganizationError):
    """947: a legal entity name or LEI already in use (409)."""


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
    # 946 GEO-01: a place (a country) or a node of one hierarchy. ``level`` is for display (1
    # Global, 2 any other node, 3 a place); ``parent_id``/``path`` are the reference-hierarchy
    # (UN M49) parent and path as of today.
    entity: Literal["place", "node"] = "place"
    hierarchy_id: str | None = None
    hierarchy_name: str | None = None
    hierarchy_kind: str | None = None
    # 949 GEO-04: country | subdivision | authority | residual (places only), and the country a
    # subdivision or authority lies in. For those, ``parent_id`` is that country.
    place_type: PlaceType | None = None
    parent_place_id: str | None = None


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


# ── Hierarchies (946 GEO-01) ──────────────────────────────────────────────────

HierarchyKind = Literal[
    "reference", "regulatory", "data_residency", "infrastructure", "sales", "tax",
    "operational", "custom",
]
# Writes to these kinds need write_compliance as well (Q2): they will drive applicability.
COMPLIANCE_KINDS: frozenset[str] = frozenset({"regulatory", "data_residency", "tax"})
HierarchyShape = Literal["strict_tree", "dag"]


class GeoHierarchy(_Model):
    id: str
    name: str
    kind: HierarchyKind
    shape: HierarchyShape
    system_of_record: str | None = None
    description: str | None = None
    read_only: bool = False
    node_count: int = 0
    membership_count: int = 0
    created_at: datetime
    updated_at: datetime


class GeoHierarchyListResponse(_Model):
    items: list[GeoHierarchy]
    total: int


class GeoHierarchyCreate(_Model):
    name: str = Field(max_length=255)
    kind: Literal[
        "regulatory", "data_residency", "infrastructure", "sales", "tax", "operational", "custom"
    ]
    shape: HierarchyShape
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _name(v)  # type: ignore[return-value]


class GeoHierarchyUpdate(_Model):
    name: str | None = Field(default=None, max_length=255)
    shape: HierarchyShape | None = None
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        return _name(v)


class GeoNodeRef(_Model):
    id: str
    name: str


class GeoMembership(_Model):
    id: str
    hierarchy_id: str
    parent_id: str
    child_id: str
    child_entity: Literal["place", "node"]
    valid_from: date | None = None
    valid_to: date | None = None
    active: bool = True  # on the detail's as_of date


class GeoHierarchyDetail(GeoHierarchy):
    as_of: date
    nodes: list[GeoNodeRef] = []
    memberships: list[GeoMembership] = []


class GeoNodeCreate(_Model):
    name: str = Field(max_length=255)
    parent_id: str | None = None  # optional first membership, undated unless valid_from is set
    valid_from: date | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _name(v)  # type: ignore[return-value]


class AddMemberships(_Model):
    parent_id: str
    child_ids: list[str] = Field(min_length=1, max_length=400)
    valid_from: date | None = None
    valid_to: date | None = None


class GeoMembershipUpdate(_Model):
    # Omitted = unchanged; explicit null = open.
    valid_from: date | None = None
    valid_to: date | None = None


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


# ── Regional assessments (942-regional-assessments, ADP-55k.3) ─────────────────
#
# A capability x region/country maturity score (same 1-5 scale as the capability's own
# maturity_level, which stays the enterprise baseline) and/or a variant note. Applicability,
# heat map cells and deltas are derived on read (test_regional_not_stored.py).

RegionalMaturity = Literal[1, 2, 3, 4, 5]
NOTE_MAX = 1000


class GeoRef(_Model):
    id: str
    name: str
    level: int
    code: str | None = None


class RegionalAssessment(_Model):
    id: str
    capability_id: str
    geography: GeoRef
    maturity_level: int | None = None
    note: str | None = None
    updated_at: datetime


class SetRegionalAssessment(_Model):
    maturity_level: RegionalMaturity | None = None
    note: str | None = Field(default=None, max_length=NOTE_MAX)

    @field_validator("note")
    @classmethod
    def _blank_note_is_none(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _score_or_note(self) -> "SetRegionalAssessment":
        if self.maturity_level is None and self.note is None:
            raise ValueError("Record a maturity score, a note, or both")
        return self


class RegionalAssessmentListResponse(_Model):
    items: list[RegionalAssessment]
    total: int


class SetRegionScope(_Model):
    region_specific: bool
    geography_ids: list[str] = []

    @model_validator(mode="after")
    def _scope_matches_flag(self) -> "SetRegionScope":
        if self.region_specific and not self.geography_ids:
            raise ValueError("A region-specific capability must name at least one geography")
        if not self.region_specific and self.geography_ids:
            raise ValueError("Geographies can only be set on a region-specific capability")
        self.geography_ids = list(dict.fromkeys(self.geography_ids))
        return self


class RegionScope(_Model):
    capability_id: str
    region_specific: bool
    geographies: list[GeoRef] = []
    scope_needs_update: bool = False


HeatmapCellState = Literal["assessed", "not_assessed", "not_applicable"]


class HeatmapCell(_Model):
    geography_id: str
    state: HeatmapCellState
    maturity_level: int | None = None
    note: str | None = None
    delta: int | None = None


class HeatmapCapability(_Model):
    id: str
    name: str
    level: int
    parent_id: str | None = None


class HeatmapRow(_Model):
    capability: HeatmapCapability
    baseline: int | None = None
    region_specific: bool = False
    scope_needs_update: bool = False
    cells: list[HeatmapCell]


class RegionalHeatmap(_Model):
    columns: list[GeoRef]
    rows: list[HeatmapRow]
    max_columns: int


# ── Legal entities and typed geography links (947 GEO-02, ADP-bo1.2) ──────────

GeoLinkSubject = Literal["application", "legal_entity", "org_unit"]
LEI = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def lei_is_valid(lei: str) -> bool:
    """ISO 17442: 20 characters, the last two are ISO 7064 mod 97-10 check digits."""
    if not LEI.match(lei):
        return False
    digits = "".join(str(int(c, 36)) for c in lei)
    return int(digits) % 97 == 1


class RelationRule(_Model):
    relation: str
    label: str
    place_only: bool = False
    single_active: bool = False


class GeoLinkRelations(_Model):
    """The relation matrix (FR-006): which relations each subject may use."""

    subjects: dict[str, list[RelationRule]]


class LinkGeography(_Model):
    id: str
    name: str
    code: str | None = None
    entity: str
    hierarchy_name: str | None = None
    hierarchy_kind: str | None = None


class GeoLink(_Model):
    id: str
    subject_type: GeoLinkSubject
    subject_id: str
    relation: str
    geography: LinkGeography
    valid_from: date | None = None
    valid_to: date | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class GeoLinkListResponse(_Model):
    as_of: date
    items: list[GeoLink]


class _Dates(_Model):
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> "_Dates":
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("The end date must be after the start date")
        return self


class GeoLinkCreate(_Dates):
    relation: str = Field(min_length=1, max_length=40)
    geography_id: str


class GeoLinkUpdate(_Dates):
    """Only the dates change (FR-005); both are replaced as sent (null = open)."""


class LegalEntity(_Model):
    id: str
    name: str
    registration_number: str | None = None
    lei: str | None = None
    description: str | None = None
    parent_id: str | None = None
    path: list[Ref] = []
    org_unit_ids: list[str] = []
    application_count: int = 0
    child_count: int = 0
    created_at: datetime
    updated_at: datetime


class LegalEntityDetail(LegalEntity):
    org_units: list[Ref] = []
    applications: list[Ref] = []
    children: list[Ref] = []


class LegalEntityListResponse(_Model):
    items: list[LegalEntity]
    total: int


def _lei(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().upper()
    if not v:
        return None
    if not lei_is_valid(v):
        raise ValueError("LEI must be 20 letters or digits with valid check digits (ISO 17442)")
    return v


def _blank_none(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class LegalEntityCreate(_Model):
    name: str = Field(max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    lei: str | None = None
    description: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        return _name(v) or v

    @field_validator("lei")
    @classmethod
    def _check_lei(cls, v: str | None) -> str | None:
        return _lei(v)

    @field_validator("registration_number", "description")
    @classmethod
    def _blank(cls, v: str | None) -> str | None:
        return _blank_none(v)


class LegalEntityUpdate(_Model):
    """Fields sent are changed; an explicit null clears an optional one."""

    name: str | None = Field(default=None, max_length=255)
    registration_number: str | None = Field(default=None, max_length=100)
    lei: str | None = None
    description: str | None = None
    parent_id: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str | None) -> str | None:
        if v is None:
            raise ValueError("name can't be cleared")
        return _name(v)

    @field_validator("lei")
    @classmethod
    def _check_lei(cls, v: str | None) -> str | None:
        return _lei(v)

    @field_validator("registration_number", "description")
    @classmethod
    def _blank(cls, v: str | None) -> str | None:
        return _blank_none(v)


class LinkOrgUnit(_Model):
    org_unit_id: str


class LinkLegalEntity(_Model):
    legal_entity_id: str


# ── 949 GEO-04: subdivisions, footprint, place matrix ─────────────────────────


class SubdivisionEntry(_Model):
    code: str
    name: str
    type: str
    added: bool


class SubdivisionCatalog(_Model):
    country_id: str
    country_name: str
    items: list[SubdivisionEntry]


class AddSubdivision(_Model):
    code: str = Field(min_length=4, max_length=8, description="An ISO 3166-2 code, e.g. US-CA")


class PlaceRef(_Model):
    id: str
    name: str
    code: str | None = None
    place_type: PlaceType | None = None
    parent_place_id: str | None = None


class HierarchyPlacement(_Model):
    """The nodes of one hierarchy that contain a place on the date, most specific first."""

    hierarchy_id: str
    hierarchy_name: str
    hierarchy_kind: str
    nodes: list[GeoNodeRef]


class FootprintLink(_Model):
    relation: str
    relation_label: str
    geography: LinkGeography
    via_legal_entity: GeoNodeRef | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class FootprintPlace(_Model):
    place: PlaceRef
    links: list[FootprintLink]
    placements: list[HierarchyPlacement]


class GeoFootprint(_Model):
    as_of: date
    application_id: str
    places: list[FootprintPlace]
    unresolved: list[FootprintLink] = Field(
        default_factory=list,
        description="Active links to a node that has no places on the date",
    )


class MatrixHierarchy(_Model):
    id: str
    name: str
    kind: str


class MatrixRow(_Model):
    place: PlaceRef
    cells: dict[str, list[GeoNodeRef]]


class PlaceMatrix(_Model):
    as_of: date
    hierarchies: list[MatrixHierarchy]
    rows: list[MatrixRow]
