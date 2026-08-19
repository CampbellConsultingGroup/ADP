"""Strategy execution layer -- initiatives and objective dependencies (ADP-d8u.6).

A new submodule inside adp.strategy, not a further extension of models.py/
store.py/router.py (which 915-objective-progress-tracking already extended
once this session) and not a new sibling package -- resolved by direct
measurement (research.md Decision 1, plan.md Ground-Truth Correction 1):
src/adp/strategy/{models,store,router}.py totals 1,434 lines, well under the
~2,847-line threshold that triggered the adp.business -> adp.strategy split.

router.py imports from this module and registers its endpoints on the same,
already-existing `router` object -- no new URL prefix, no new
adp.authz.enforcement rule; every route here still falls under the existing
("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH) prefix rule.

DuplicateLinkError/LinkNotFoundError are reused from adp.strategy.store
(already public there) rather than redefined -- only CycleError is new here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from adp.compliance.models import ComplianceStatus, MappingTargetType
from adp.strategy.store import (
    DuplicateLinkError,
    LinkNotFoundError,
    _control_application_mapping_mirror,
    _control_capability_mapping_mirror,
    _control_design_mapping_mirror,
    _control_organization_mapping_mirror,
    _control_pattern_mapping_mirror,
    _metadata,
    _now,
    _rowcount,
)

logger = logging.getLogger(__name__)

# Reuses store.py's _metadata (not a fresh sa.MetaData()) so that every
# existing test fixture's `sstore._metadata.create_all` already picks up
# these tables too -- required, since linking an initiative to an objective
# needs both _objectives (store.py) and _initiatives (here) in the same
# in-memory-SQLite test database.

InitiativeStatus = Literal["planned", "in_progress", "blocked", "complete", "cancelled"]


class CycleError(Exception):
    """Raised when a dependency link would create a cycle -- direct, chained,
    or self-referential (FR-007). The router maps this to 400."""


class ControlMappingNotFoundError(Exception):
    """925-strategy-compliance-linkage (COMPLY-05): raised when no ControlMapping row exists yet
    for the given (control_id, target_type, target_id) -- an Initiative links to an
    already-*assessed* mapping, it does not create one (data-model.md). Router maps to 404."""

    def __init__(
        self, control_id: str, target_type: "MappingTargetType", target_id: str | None
    ) -> None:
        self.control_id = control_id
        self.target_type = target_type
        self.target_id = target_id
        super().__init__(
            f"No ControlMapping for control {control_id!r}, target_type {target_type!r}, "
            f"target_id {target_id!r}"
        )


# ── Pydantic models ──────────────────────────────────────────────────────────


class ControlMappingRef(BaseModel):
    """925-strategy-compliance-linkage (COMPLY-05): one InitiativeControlMapping target, plus the
    *live* status/evidence read straight off the linked ControlMapping row via mirror-table JOIN
    (research.md D3) -- never a value captured at link-creation time and never re-synced."""

    model_config = ConfigDict(extra="forbid")

    control_id: str
    target_type: MappingTargetType
    target_id: str | None  # None only when target_type == ORGANIZATION
    compliance_status: ComplianceStatus
    evidence_ref: str | None
    assessed_at: date | None


class StrategyInitiative(BaseModel):
    """Read model. objective_ids is a denormalized list, mirroring
    StrategicObjective.capability_ids's own established convention."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None = None
    owner: str | None = None
    status: InitiativeStatus
    objective_ids: list[str] = []
    control_mappings: list[ControlMappingRef] = []
    created_at: datetime
    updated_at: datetime


class StrategyInitiativeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    owner: str | None = None
    status: InitiativeStatus = "planned"

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v


class StrategyInitiativeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    owner: str | None = None
    status: InitiativeStatus | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v


class StrategyInitiativeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[StrategyInitiative]
    total: int


class ObjectiveDependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    depends_on_objective_id: str


class ObjectiveDependenciesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    depends_on: list[str] = []
    blocks: list[str] = []


# ── sa.Table defs ─────────────────────────────────────────────────────────────

_initiatives = sa.Table(
    "strategy_initiatives",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("owner", sa.Text(), nullable=True),
    sa.Column("status", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

# Composite PK omitted here, matching store.py's own established join-table
# convention (_objective_capabilities/_progress) -- PK/FK constraints live
# only in the migration; the SQLite unit-test fixture adds a manual
# CREATE UNIQUE INDEX instead.
_initiative_objective_links = sa.Table(
    "strategy_initiative_objective_links",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# 925-strategy-compliance-linkage (COMPLY-05): five parallel tables, one per ControlMapping target
# shape (research.md D1) -- mirrors COMPLY-02's own five-control_*_mapping-tables resolution one
# level up, since ControlMapping itself has no single addressable row/id to reference. Composite
# PK/FK (incl. the composite FK against the corresponding control_*_mapping table) omitted here,
# same convention as every other join table in this package -- migration 034 owns those.
_initiative_control_capability_mapping = sa.Table(
    "initiative_control_capability_mapping",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("control_id", sa.String(36), nullable=False),
    sa.Column("capability_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_initiative_control_application_mapping = sa.Table(
    "initiative_control_application_mapping",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("control_id", sa.String(36), nullable=False),
    sa.Column("application_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_initiative_control_design_mapping = sa.Table(
    "initiative_control_design_mapping",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("control_id", sa.String(36), nullable=False),
    sa.Column("design_id", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_initiative_control_pattern_mapping = sa.Table(
    "initiative_control_pattern_mapping",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("control_id", sa.String(36), nullable=False),
    sa.Column("pattern_id", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

_initiative_control_organization_mapping = sa.Table(
    "initiative_control_organization_mapping",
    _metadata,
    sa.Column("initiative_id", sa.String(36), nullable=False),
    sa.Column("control_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

# Dispatch tables keyed by MappingTargetType -- (link table, target-id column name or None for
# organization) and (mirror table from adp.strategy.store, target-id column name or None).
_LINK_TABLE_BY_TARGET_TYPE: dict[MappingTargetType, tuple[sa.Table, str | None]] = {
    MappingTargetType.CAPABILITY: (_initiative_control_capability_mapping, "capability_id"),
    MappingTargetType.APPLICATION: (_initiative_control_application_mapping, "application_id"),
    MappingTargetType.DESIGN: (_initiative_control_design_mapping, "design_id"),
    MappingTargetType.PATTERN: (_initiative_control_pattern_mapping, "pattern_id"),
    MappingTargetType.ORGANIZATION: (_initiative_control_organization_mapping, None),
}

_MIRROR_BY_TARGET_TYPE: dict[MappingTargetType, tuple[sa.Table, str | None]] = {
    MappingTargetType.CAPABILITY: (_control_capability_mapping_mirror, "capability_id"),
    MappingTargetType.APPLICATION: (_control_application_mapping_mirror, "application_id"),
    MappingTargetType.DESIGN: (_control_design_mapping_mirror, "design_id"),
    MappingTargetType.PATTERN: (_control_pattern_mapping_mirror, "pattern_id"),
    MappingTargetType.ORGANIZATION: (_control_organization_mapping_mirror, None),
}

_objective_dependencies = sa.Table(
    "strategic_objective_dependencies",
    _metadata,
    sa.Column("objective_id", sa.String(36), nullable=False),
    sa.Column("depends_on_objective_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


# ── Initiative CRUD ──────────────────────────────────────────────────────────


async def _linked_objective_ids(initiative_id: str, session: AsyncSession) -> list[str]:
    result = await session.execute(
        sa.select(_initiative_objective_links.c.objective_id)
        .where(_initiative_objective_links.c.initiative_id == initiative_id)
        .order_by(_initiative_objective_links.c.objective_id)
    )
    return [row.objective_id for row in result]


async def create_initiative(
    body: StrategyInitiativeCreate, session: AsyncSession
) -> StrategyInitiative:
    initiative_id = str(uuid.uuid4())
    now = _now()
    await session.execute(
        _initiatives.insert().values(
            id=initiative_id,
            name=body.name,
            description=body.description,
            owner=body.owner,
            status=body.status,
            created_at=now,
            updated_at=now,
        )
    )
    initiative = await get_initiative(initiative_id, session)
    assert initiative is not None  # just inserted
    return initiative


async def get_initiative(initiative_id: str, session: AsyncSession) -> StrategyInitiative | None:
    result = await session.execute(
        sa.select(_initiatives).where(_initiatives.c.id == initiative_id)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return StrategyInitiative(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        owner=row["owner"],
        status=row["status"],
        objective_ids=await _linked_objective_ids(initiative_id, session),
        control_mappings=await _linked_control_mappings(initiative_id, session),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_initiatives(session: AsyncSession) -> StrategyInitiativeListResponse:
    result = await session.execute(sa.select(_initiatives.c.id).order_by(_initiatives.c.name))
    items = []
    for row in result:
        initiative = await get_initiative(row.id, session)
        assert initiative is not None
        items.append(initiative)
    return StrategyInitiativeListResponse(items=items, total=len(items))


async def update_initiative(
    initiative_id: str, body: StrategyInitiativeUpdate, session: AsyncSession
) -> StrategyInitiative | None:
    values: dict[str, Any] = {}
    for field in ("name", "description", "owner", "status"):
        value = getattr(body, field)
        if value is not None:
            values[field] = value
    if not values:
        return await get_initiative(initiative_id, session)

    values["updated_at"] = _now()
    result = await session.execute(
        _initiatives.update().where(_initiatives.c.id == initiative_id).values(**values)
    )
    if _rowcount(result) == 0:
        return None
    return await get_initiative(initiative_id, session)


async def delete_initiative(initiative_id: str, session: AsyncSession) -> bool:
    """FR-011: unconditional -- never blocked by existing links, unlike theme
    delete's in-use block (ADP-d8u.5). Deleting the row is enough; the real
    ON DELETE CASCADE FK (migration 027) removes any links pointing at it,
    the same pattern already verified for every other cascade in this
    package (confirmed directly against Postgres, not re-tested at the
    SQLite unit layer -- matches test_strategy_store.py's own precedent)."""
    result = await session.execute(_initiatives.delete().where(_initiatives.c.id == initiative_id))
    return _rowcount(result) > 0


# ── Initiative <-> Objective links ──────────────────────────────────────────


async def link_initiative_objective(
    initiative_id: str, objective_id: str, session: AsyncSession
) -> None:
    """Caller (router) has already validated both ids exist."""
    try:
        await session.execute(
            _initiative_objective_links.insert().values(
                initiative_id=initiative_id, objective_id=objective_id, created_at=_now()
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Initiative {initiative_id!r} is already linked to objective {objective_id!r}"
            ) from exc
        raise


async def unlink_initiative_objective(
    initiative_id: str, objective_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _initiative_objective_links.delete().where(
            _initiative_objective_links.c.initiative_id == initiative_id,
            _initiative_objective_links.c.objective_id == objective_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(
            f"Initiative {initiative_id!r} is not linked to objective {objective_id!r}"
        )


async def list_objective_initiative_ids(objective_id: str, session: AsyncSession) -> list[str]:
    """Reverse lookup (FR-005)."""
    result = await session.execute(
        sa.select(_initiative_objective_links.c.initiative_id)
        .where(_initiative_objective_links.c.objective_id == objective_id)
        .order_by(_initiative_objective_links.c.initiative_id)
    )
    return [row.initiative_id for row in result]


# ── Initiative <-> ControlMapping links (925-strategy-compliance-linkage, COMPLY-05) ────────────


def _target_condition(
    mirror_or_link: sa.Table, target_col: str | None, target_id: str | None
) -> list[Any]:
    conditions: list[Any] = []
    if target_col is not None:
        conditions.append(getattr(mirror_or_link.c, target_col) == target_id)
    return conditions


async def link_initiative_control_mapping(
    initiative_id: str,
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    session: AsyncSession,
) -> None:
    """Caller (router) has already validated the initiative exists. Raises
    ControlMappingNotFoundError if no ControlMapping row exists yet for
    (control_id, target_type, target_id) -- an Initiative links to an already-*assessed* mapping,
    it does not create one (data-model.md State/validation rules)."""
    mirror, target_col = _MIRROR_BY_TARGET_TYPE[target_type]
    conditions = [
        mirror.c.control_id == control_id, *_target_condition(mirror, target_col, target_id),
    ]
    exists = (await session.execute(sa.select(mirror.c.control_id).where(*conditions))).first()
    if exists is None:
        raise ControlMappingNotFoundError(control_id, target_type, target_id)

    link_table, link_target_col = _LINK_TABLE_BY_TARGET_TYPE[target_type]
    values: dict[str, Any] = {
        "initiative_id": initiative_id, "control_id": control_id, "created_at": _now(),
    }
    if link_target_col is not None:
        values[link_target_col] = target_id
    try:
        await session.execute(link_table.insert().values(**values))
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Initiative {initiative_id!r} is already linked to control mapping "
                f"(control_id={control_id!r}, target_type={target_type!r}, target_id={target_id!r})"
            ) from exc
        raise


async def unlink_initiative_control_mapping(
    initiative_id: str,
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    session: AsyncSession,
) -> None:
    link_table, link_target_col = _LINK_TABLE_BY_TARGET_TYPE[target_type]
    conditions = [
        link_table.c.initiative_id == initiative_id,
        link_table.c.control_id == control_id,
        *_target_condition(link_table, link_target_col, target_id),
    ]
    result = await session.execute(link_table.delete().where(*conditions))
    if _rowcount(result) == 0:
        raise LinkNotFoundError(
            f"Initiative {initiative_id!r} is not linked to control mapping "
            f"(control_id={control_id!r}, target_type={target_type!r}, target_id={target_id!r})"
        )


async def _linked_control_mappings(
    initiative_id: str, session: AsyncSession
) -> list[ControlMappingRef]:
    """Live JOIN against adp.strategy.store's read-only ControlMapping mirrors on every call --
    compliance_status is never cached or copied onto the link row itself (FR-008, research.md
    D3)."""
    refs: list[ControlMappingRef] = []
    for target_type, (link_table, link_target_col) in _LINK_TABLE_BY_TARGET_TYPE.items():
        mirror, target_col = _MIRROR_BY_TARGET_TYPE[target_type]
        join_condition = [link_table.c.control_id == mirror.c.control_id]
        target_id_expr: Any = sa.literal(None)
        if target_col is not None:
            # Both dispatch dicts set their str-or-None target-column entry together per
            # target_type (never one None while the other isn't) -- see _LINK_TABLE_BY_TARGET_TYPE/
            # _MIRROR_BY_TARGET_TYPE above.
            assert link_target_col is not None
            join_condition.append(
                getattr(link_table.c, link_target_col) == getattr(mirror.c, target_col)
            )
            target_id_expr = getattr(mirror.c, target_col)
        query = (
            sa.select(
                mirror.c.control_id,
                target_id_expr.label("target_id"),
                mirror.c.compliance_status,
                mirror.c.evidence_ref,
                mirror.c.assessed_at,
            )
            .select_from(link_table.join(mirror, sa.and_(*join_condition)))
            .where(link_table.c.initiative_id == initiative_id)
        )
        result = await session.execute(query)
        for row in result:
            refs.append(
                ControlMappingRef(
                    control_id=row.control_id,
                    target_type=target_type,
                    target_id=row.target_id,
                    compliance_status=row.compliance_status,
                    evidence_ref=row.evidence_ref,
                    assessed_at=row.assessed_at,
                )
            )
    return refs


async def list_initiatives_for_control_mapping(
    control_id: str,
    target_type: MappingTargetType,
    target_id: str | None,
    session: AsyncSession,
) -> StrategyInitiativeListResponse:
    """Reverse lookup (called from adp.compliance.router -- mirrors
    adp.strategy.store.list_objectives_for_design's exact shape)."""
    link_table, link_target_col = _LINK_TABLE_BY_TARGET_TYPE[target_type]
    conditions = [
        link_table.c.control_id == control_id,
        *_target_condition(link_table, link_target_col, target_id),
    ]
    result = await session.execute(
        sa.select(link_table.c.initiative_id).where(*conditions).order_by(link_table.c.initiative_id)
    )
    items = []
    for row in result:
        initiative = await get_initiative(row.initiative_id, session)
        if initiative is not None:
            items.append(initiative)
    return StrategyInitiativeListResponse(items=items, total=len(items))


# ── Objective dependencies (research.md Decision 2) ─────────────────────────


def _reaches(start: str, target: str, edges: dict[str, list[str]]) -> bool:
    """Pure, no-I/O BFS: can `target` be reached from `start` by following
    `edges` (objective_id -> [depends_on_objective_id, ...])?

    Used to answer "would adding start -depends_on-> target create a cycle?"
    -- a cycle exists iff target can already reach start (i.e. start is
    already, directly or transitively, a dependency of target)."""
    visited: set[str] = {start}
    queue: list[str] = [start]
    while queue:
        node = queue.pop(0)
        if node == target and node != start:
            return True
        for neighbor in edges.get(node, []):
            if neighbor == target:
                return True
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


async def _would_create_cycle(
    objective_id: str, depends_on_objective_id: str, session: AsyncSession
) -> bool:
    """Thin async wrapper: self-check, fetch all existing edges into a dict,
    delegate to the pure _reaches(). A cycle would result from adding the
    edge objective_id -> depends_on_objective_id iff depends_on_objective_id
    can already reach objective_id (direct, chained, or self)."""
    if objective_id == depends_on_objective_id:
        return True
    result = await session.execute(
        sa.select(
            _objective_dependencies.c.objective_id,
            _objective_dependencies.c.depends_on_objective_id,
        )
    )
    edges: dict[str, list[str]] = {}
    for row in result:
        edges.setdefault(row.objective_id, []).append(row.depends_on_objective_id)
    return _reaches(depends_on_objective_id, objective_id, edges)


async def add_objective_dependency(
    objective_id: str, depends_on_objective_id: str, session: AsyncSession
) -> None:
    """Caller (router) has already validated both ids exist."""
    if await _would_create_cycle(objective_id, depends_on_objective_id, session):
        raise CycleError(
            f"Objective {objective_id!r} cannot depend on "
            f"{depends_on_objective_id!r} -- this would create a cycle"
        )
    try:
        await session.execute(
            _objective_dependencies.insert().values(
                objective_id=objective_id,
                depends_on_objective_id=depends_on_objective_id,
                created_at=_now(),
            )
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower() or "23505" in str(exc):
            raise DuplicateLinkError(
                f"Objective {objective_id!r} already depends on "
                f"{depends_on_objective_id!r}"
            ) from exc
        raise


async def remove_objective_dependency(
    objective_id: str, depends_on_objective_id: str, session: AsyncSession
) -> None:
    result = await session.execute(
        _objective_dependencies.delete().where(
            _objective_dependencies.c.objective_id == objective_id,
            _objective_dependencies.c.depends_on_objective_id == depends_on_objective_id,
        )
    )
    if _rowcount(result) == 0:
        raise LinkNotFoundError(
            f"Objective {objective_id!r} does not depend on {depends_on_objective_id!r}"
        )


async def get_objective_dependencies(
    objective_id: str, session: AsyncSession
) -> ObjectiveDependenciesResponse:
    """Both directions: depends_on (what this objective needs) and blocks
    (what this objective, if unfinished, holds up)."""
    depends_on_result = await session.execute(
        sa.select(_objective_dependencies.c.depends_on_objective_id)
        .where(_objective_dependencies.c.objective_id == objective_id)
        .order_by(_objective_dependencies.c.depends_on_objective_id)
    )
    blocks_result = await session.execute(
        sa.select(_objective_dependencies.c.objective_id)
        .where(_objective_dependencies.c.depends_on_objective_id == objective_id)
        .order_by(_objective_dependencies.c.objective_id)
    )
    return ObjectiveDependenciesResponse(
        depends_on=[row.depends_on_objective_id for row in depends_on_result],
        blocks=[row.objective_id for row in blocks_result],
    )
