"""Pattern adoptions: a pattern applied to a scope, with members and pins (936 US2, research D2).

Store functions never commit (the router owns the transaction). Adoption tables live on
``adp.patterns.store._metadata``; migration 045 owns the FK/CHECK constraints. The partial unique
indexes are also declared here (``sqlite_where``) so SQLite fixtures enforce them like Postgres.
Child rows are deleted explicitly so SQLite (no FK enforcement) behaves like Postgres CASCADE.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adp.patterns.conformance_models import (
    Adoption,
    AdoptionCreate,
    AdoptionListResponse,
    AdoptionNotFoundError,
    AdoptionUpdate,
    DraftPinError,
    DuplicateAdoptionError,
    InvalidPinError,
    InvalidScopeError,
    PinIn,
    ScopeTargetNotFoundError,
    ScopeType,
)
from adp.patterns.models import PatternDefinition, PatternKind
from adp.patterns.registry_models import (
    PatternLifecycle,
    PatternNotFoundError,
    PatternVersionNotFoundError,
)
from adp.patterns.snapshot import Scope
from adp.patterns.snapshot_store import ELEMENT_TABLES, _domains
from adp.patterns.store import (
    _applications_mirror,
    _metadata,
    _now,
    _patterns,
    _versions,
    definition_from_db,
)

_adoptions = sa.Table(
    "ea_pattern_adoption",
    _metadata,
    sa.Column("id", sa.String(36), primary_key=True),
    sa.Column("pattern_key", sa.Text(), nullable=False),
    sa.Column("pinned_version_id", sa.String(36)),
    sa.Column("scope_type", sa.Text(), nullable=False),
    sa.Column("scope_ref", sa.String(36)),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
sa.Index(
    "uq_ea_pattern_adoption_domain",
    _adoptions.c.pattern_key,
    _adoptions.c.scope_ref,
    unique=True,
    postgresql_where=_adoptions.c.scope_type == "business_domain",
    sqlite_where=_adoptions.c.scope_type == "business_domain",
)
sa.Index(
    "uq_ea_pattern_adoption_portfolio",
    _adoptions.c.pattern_key,
    unique=True,
    postgresql_where=_adoptions.c.scope_type == "portfolio",
    sqlite_where=_adoptions.c.scope_type == "portfolio",
)
sa.Index("uq_ea_pattern_adoption_name", _adoptions.c.pattern_key, _adoptions.c.name, unique=True)

_members = sa.Table(
    "ea_pattern_adoption_member",
    _metadata,
    sa.Column("adoption_id", sa.String(36), primary_key=True),
    sa.Column("application_id", sa.String(36), primary_key=True),
)
_pins = sa.Table(
    "ea_pattern_adoption_pin",
    _metadata,
    sa.Column("adoption_id", sa.String(36), primary_key=True),
    sa.Column("role_key", sa.Text(), primary_key=True),
    sa.Column("element_type", sa.Text(), primary_key=True),
    sa.Column("element_id", sa.Text(), primary_key=True),
)


# ── Lookups ─────────────────────────────────────────────────────────────────────────────
async def _row(adoption_id: str, session: AsyncSession) -> Any:
    row = (
        await session.execute(sa.select(_adoptions).where(_adoptions.c.id == adoption_id))
    ).first()
    if row is None:
        raise AdoptionNotFoundError(adoption_id)
    return row


async def _version_by_id(version_id: str, session: AsyncSession) -> Any:
    return (await session.execute(sa.select(_versions).where(_versions.c.id == version_id))).first()


async def _current(pattern_key: str, session: AsyncSession) -> Any:
    return (
        await session.execute(
            sa.select(_versions).where(
                _versions.c.pattern_key == pattern_key,
                _versions.c.lifecycle == PatternLifecycle.CURRENT.value,
            )
        )
    ).first()


async def _resolved_row(row: Any, session: AsyncSession) -> Any:
    if row.pinned_version_id:
        return await _version_by_id(row.pinned_version_id, session)
    return await _current(row.pattern_key, session)


async def _family(pattern_key: str, session: AsyncSession) -> Any:
    family = (
        await session.execute(sa.select(_patterns).where(_patterns.c.pattern_key == pattern_key))
    ).first()
    if family is None:
        raise PatternNotFoundError(pattern_key)
    return family


async def _missing(table: sa.Table, ids: list[str], session: AsyncSession) -> list[str]:
    if not ids:
        return []
    found = {r[0] for r in await session.execute(sa.select(table.c.id).where(table.c.id.in_(ids)))}
    return [i for i in ids if i not in found]


def scope_of(adoption: Adoption) -> Scope:
    return Scope(adoption.scope_type, adoption.scope_ref, frozenset(adoption.member_ids))


async def _to_model(row: Any, session: AsyncSession) -> Adoption:
    family = await _family(row.pattern_key, session)
    members = sorted(
        r.application_id
        for r in await session.execute(
            sa.select(_members.c.application_id).where(_members.c.adoption_id == row.id)
        )
    )
    pins = [
        PinIn(role_key=r.role_key, element_type=r.element_type, element_id=r.element_id)
        for r in await session.execute(
            sa.select(_pins)
            .where(_pins.c.adoption_id == row.id)
            .order_by(_pins.c.role_key, _pins.c.element_type, _pins.c.element_id)
        )
    ]
    pinned = await _version_by_id(row.pinned_version_id, session) if row.pinned_version_id else None
    resolved = pinned or await _current(row.pattern_key, session)
    scope_name = None
    if row.scope_ref:
        dom = (
            await session.execute(sa.select(_domains.c.name).where(_domains.c.id == row.scope_ref))
        ).first()
        scope_name = dom.name if dom else None
    return Adoption(
        id=row.id,
        pattern_key=row.pattern_key,
        pattern_name=resolved.name if resolved else None,
        kind=PatternKind(family.kind),
        name=row.name,
        scope_type=ScopeType(row.scope_type),
        scope_ref=row.scope_ref,
        scope_name=scope_name,
        member_ids=members,
        pinned_version=pinned.version if pinned else None,
        resolved_version=resolved.version if resolved else None,
        pins=pins,
        created_at=row.created_at,
        created_by=row.created_by,
        updated_at=row.updated_at,
    )


async def get_adoption(adoption_id: str, session: AsyncSession) -> Adoption:
    return await _to_model(await _row(adoption_id, session), session)


async def list_adoptions(
    session: AsyncSession,
    *,
    pattern_key: str | None = None,
    scope_type: ScopeType | None = None,
) -> AdoptionListResponse:
    stmt = sa.select(_adoptions).order_by(_adoptions.c.pattern_key, _adoptions.c.name)
    if pattern_key:
        stmt = stmt.where(_adoptions.c.pattern_key == pattern_key)
    if scope_type:
        stmt = stmt.where(_adoptions.c.scope_type == scope_type.value)
    items = [await _to_model(r, session) for r in (await session.execute(stmt)).all()]
    return AdoptionListResponse(items=items, total=len(items))


async def resolve_definition(
    adoption: Adoption, session: AsyncSession
) -> tuple[PatternDefinition, str] | None:
    """The definition (and digest) an adoption evaluates: its pinned version, else the family's
    current version; None when neither exists (B1)."""
    row = await _row(adoption.id, session)
    version = await _resolved_row(row, session)
    if version is None:
        return None
    return definition_from_db(version.definition), str(version.digest)


# ── Validation ─────────────────────────────────────────────────────────────────────────
async def _pinned_version_id(
    pattern_key: str, version: str | None, session: AsyncSession
) -> str | None:
    if version is None:
        return None
    row = (
        await session.execute(
            sa.select(_versions).where(
                _versions.c.pattern_key == pattern_key, _versions.c.version == version
            )
        )
    ).first()
    if row is None:
        raise PatternVersionNotFoundError(pattern_key, version)
    if row.lifecycle == PatternLifecycle.DRAFT.value:
        raise DraftPinError(pattern_key, version)
    return str(row.id)


async def _check_members(member_ids: list[str], session: AsyncSession) -> None:
    missing = await _missing(_applications_mirror, sorted(set(member_ids)), session)
    if missing:
        raise ScopeTargetNotFoundError("application", ", ".join(missing))


async def validate_pins(
    pins: list[PinIn], definition: PatternDefinition | None, session: AsyncSession
) -> None:
    """FR-003: role exists, type matches the role, element exists. All problems at once."""
    if not pins:
        return
    if definition is None:
        raise InvalidPinError(["the adoption has no version to validate pins against"])
    reasons: list[str] = []
    to_check: dict[str, list[str]] = {}
    for p in pins:
        role = definition.roles.get(p.role_key)
        if role is None:
            reasons.append(f"role '{p.role_key}' is not declared by {definition.pattern}")
            continue
        if role.element_type != p.element_type:
            reasons.append(
                f"role '{p.role_key}' binds {role.element_type.value}, not {p.element_type.value}"
            )
            continue
        to_check.setdefault(p.element_type.value, []).append(p.element_id)
    for etype, ids in to_check.items():
        for missing in await _missing(ELEMENT_TABLES[etype], sorted(set(ids)), session):
            reasons.append(f"{etype} '{missing}' does not exist")
    if reasons:
        raise InvalidPinError(reasons)


async def _definition_for(
    pattern_key: str, pinned_version_id: str | None, session: AsyncSession
) -> PatternDefinition | None:
    row = (
        await _version_by_id(pinned_version_id, session)
        if pinned_version_id
        else await _current(pattern_key, session)
    )
    return definition_from_db(row.definition) if row else None


async def _replace_pins(adoption_id: str, pins: list[PinIn], session: AsyncSession) -> None:
    await session.execute(_pins.delete().where(_pins.c.adoption_id == adoption_id))
    for p in {(p.role_key, p.element_type.value, p.element_id) for p in pins}:
        await session.execute(
            _pins.insert().values(
                adoption_id=adoption_id, role_key=p[0], element_type=p[1], element_id=p[2]
            )
        )


async def _replace_members(adoption_id: str, member_ids: list[str], session: AsyncSession) -> None:
    await session.execute(_members.delete().where(_members.c.adoption_id == adoption_id))
    for mid in sorted(set(member_ids)):
        await session.execute(_members.insert().values(adoption_id=adoption_id, application_id=mid))


async def _assert_unique(
    pattern_key: str,
    scope_type: ScopeType,
    scope_ref: str | None,
    name: str,
    session: AsyncSession,
    exclude_id: str | None = None,
) -> None:
    a = _adoptions
    others = sa.select(a.c.id).where(a.c.pattern_key == pattern_key)
    if exclude_id:
        others = others.where(a.c.id != exclude_id)
    if (await session.execute(others.where(a.c.name == name))).first():
        raise DuplicateAdoptionError(f"'{pattern_key}' already has an adoption named '{name}'")
    if (
        scope_type == ScopeType.BUSINESS_DOMAIN
        and (
            await session.execute(
                others.where(a.c.scope_type == scope_type.value, a.c.scope_ref == scope_ref)
            )
        ).first()
    ):
        raise DuplicateAdoptionError(f"'{pattern_key}' is already adopted for this domain")
    if (
        scope_type == ScopeType.PORTFOLIO
        and (await session.execute(others.where(a.c.scope_type == scope_type.value))).first()
    ):
        raise DuplicateAdoptionError(f"'{pattern_key}' is already adopted for the portfolio")


# ── Writes ─────────────────────────────────────────────────────────────────────────────
async def create_adoption(body: AdoptionCreate, actor: str, session: AsyncSession) -> Adoption:
    await _family(body.pattern_key, session)
    if body.scope_type == ScopeType.BUSINESS_DOMAIN:
        assert body.scope_ref is not None
        if await _missing(_domains, [body.scope_ref], session):
            raise ScopeTargetNotFoundError("business domain", body.scope_ref)
    if body.scope_type == ScopeType.APPLICATION_SET:
        await _check_members(body.member_ids, session)
    pinned_id = await _pinned_version_id(body.pattern_key, body.pinned_version, session)
    await validate_pins(
        body.pins, await _definition_for(body.pattern_key, pinned_id, session), session
    )
    await _assert_unique(body.pattern_key, body.scope_type, body.scope_ref, body.name, session)

    now = _now()
    adoption_id = str(uuid.uuid4())
    try:
        await session.execute(
            _adoptions.insert().values(
                id=adoption_id,
                pattern_key=body.pattern_key,
                pinned_version_id=pinned_id,
                scope_type=body.scope_type.value,
                scope_ref=body.scope_ref,
                name=body.name,
                created_at=now,
                created_by=actor,
                updated_at=now,
            )
        )
    except IntegrityError as exc:  # concurrent duplicate
        raise DuplicateAdoptionError("an equivalent adoption was created concurrently") from exc
    await _replace_members(adoption_id, body.member_ids, session)
    await _replace_pins(adoption_id, body.pins, session)
    return await get_adoption(adoption_id, session)


async def update_adoption(
    adoption_id: str,
    body: AdoptionUpdate,
    fields_set: set[str],
    actor: str,  # noqa: ARG001 - kept for a uniform write signature; logged by the router
    session: AsyncSession,
) -> Adoption:
    """PATCH: only the fields the caller sent (``pinned_version: null`` follows current)."""
    row = await _row(adoption_id, session)
    values: dict[str, Any] = {"updated_at": _now()}
    if "name" in fields_set and body.name is not None:
        await _assert_unique(
            row.pattern_key,
            ScopeType(row.scope_type),
            row.scope_ref,
            body.name,
            session,
            exclude_id=adoption_id,
        )
        values["name"] = body.name
    if "pinned_version" in fields_set:
        values["pinned_version_id"] = await _pinned_version_id(
            row.pattern_key, body.pinned_version, session
        )
    await session.execute(
        _adoptions.update().where(_adoptions.c.id == adoption_id).values(**values)
    )
    return await get_adoption(adoption_id, session)


async def set_members(
    adoption_id: str, member_ids: list[str], actor: str, session: AsyncSession
) -> Adoption:
    row = await _row(adoption_id, session)
    if row.scope_type != ScopeType.APPLICATION_SET.value:
        raise InvalidScopeError("members can only be set on application_set adoptions")
    await _check_members(member_ids, session)
    await _replace_members(adoption_id, member_ids, session)
    await session.execute(
        _adoptions.update().where(_adoptions.c.id == adoption_id).values(updated_at=_now())
    )
    return await get_adoption(adoption_id, session)


async def set_pins(
    adoption_id: str, pins: list[PinIn], actor: str, session: AsyncSession
) -> Adoption:
    row = await _row(adoption_id, session)
    definition = await _definition_for(row.pattern_key, row.pinned_version_id, session)
    await validate_pins(pins, definition, session)
    await _replace_pins(adoption_id, pins, session)
    await session.execute(
        _adoptions.update().where(_adoptions.c.id == adoption_id).values(updated_at=_now())
    )
    return await get_adoption(adoption_id, session)


async def delete_adoption(adoption_id: str, session: AsyncSession) -> None:
    await _row(adoption_id, session)
    await session.execute(_pins.delete().where(_pins.c.adoption_id == adoption_id))
    await session.execute(_members.delete().where(_members.c.adoption_id == adoption_id))
    await session.execute(_adoptions.delete().where(_adoptions.c.id == adoption_id))
