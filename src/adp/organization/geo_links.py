"""Typed, effective-dated geography links (947 GEO-02, ADP-bo1.2).

An application, legal entity or org unit touches a place or a hierarchy node through a relation
("deployed in", "licensed in", "operates in", ...), valid from a date (inclusive) until a date
(exclusive); NULL = open. ``RELATIONS`` is the matrix of which relation fits which subject
(FR-006); ``check_link`` is the pure rule check run on every write (FR-004). One table per
subject keeps real foreign keys (R1); ``_SUBJECTS`` drives one code path over all three.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.organization.models import (
    DuplicateLinkError,
    GeoLink,
    GeoLinkCreate,
    GeoLinkListResponse,
    GeoLinkRelations,
    GeoLinkSubject,
    GeoLinkUpdate,
    LinkGeography,
    LinkRuleError,
    OrgNotFoundError,
    RelationRule,
)
from adp.organization.store import (
    _application_geo_links,
    _applications,
    _geo_hierarchies,
    _geographies,
    _legal_entities,
    _legal_entity_geo_links,
    _now,
    _org_unit_geo_links,
    _org_units,
)

RELATIONS: dict[str, dict[str, RelationRule]] = {
    "application": {
        r.relation: r
        for r in (
            RelationRule(relation="deployed_in", label="Deployed in"),
            RelationRule(relation="stores_data_in", label="Stores data in"),
            RelationRule(
                relation="processes_personal_data_of",
                label="Processes personal data of people in",
            ),
            RelationRule(relation="serves_customers_in", label="Serves customers in"),
        )
    },
    "legal_entity": {
        r.relation: r
        for r in (
            RelationRule(
                relation="incorporated_in",
                label="Incorporated in",
                place_only=True,
                single_active=True,
            ),
            RelationRule(relation="licensed_in", label="Licensed in"),
            RelationRule(relation="has_establishment_in", label="Has an establishment in"),
            RelationRule(relation="tax_resident_in", label="Tax resident in"),
        )
    },
    "org_unit": {
        r.relation: r
        for r in (
            RelationRule(relation="operates_in", label="Operates in"),
            RelationRule(relation="serves_customers_in", label="Serves customers in"),
            RelationRule(relation="has_staff_in", label="Has staff in"),
        )
    },
}


def relations() -> GeoLinkRelations:
    return GeoLinkRelations(subjects={k: list(v.values()) for k, v in RELATIONS.items()})


# ── Pure rules ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Period:
    id: str
    relation: str
    geography_id: str
    valid_from: date | None
    valid_to: date | None


def overlaps(
    a_from: date | None, a_to: date | None, b_from: date | None, b_to: date | None
) -> bool:
    """Half-open periods [from, to) overlap when each starts before the other ends."""
    return (a_to is None or b_from is None or b_from < a_to) and (
        b_to is None or a_from is None or a_from < b_to
    )


def active(valid_from: date | None, valid_to: date | None, on: date) -> bool:
    return (valid_from is None or valid_from <= on) and (valid_to is None or on < valid_to)


def check_link(
    subject_type: str,
    candidate: Period,
    existing: list[Period],
    is_place: bool,
) -> None:
    """Raises LinkRuleError (422) or DuplicateLinkError (409) naming the rule (FR-004).
    ``existing`` is the subject's other links (the candidate's own row excluded)."""
    rule = RELATIONS.get(subject_type, {}).get(candidate.relation)
    if rule is None:
        allowed = ", ".join(RELATIONS.get(subject_type, {}))
        raise LinkRuleError(
            f"Relation {candidate.relation!r} is not allowed for {subject_type.replace('_', ' ')}"
            f" links (allowed: {allowed})"
        )
    if candidate.valid_from and candidate.valid_to and candidate.valid_to <= candidate.valid_from:
        raise LinkRuleError("The end date must be after the start date")
    if rule.place_only and not is_place:
        raise LinkRuleError(f"{rule.label} must be a country, not a region or other node")
    for e in existing:
        if e.relation != candidate.relation:
            continue
        if not overlaps(e.valid_from, e.valid_to, candidate.valid_from, candidate.valid_to):
            continue
        if e.geography_id == candidate.geography_id:
            raise DuplicateLinkError(
                f"This {rule.label.lower()} link already covers part of that period"
            )
        if rule.single_active:
            raise DuplicateLinkError(
                f"Only one {rule.label.lower()} link at a time; end the current one first"
            )


# ── Subjects (R1) ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Subject:
    links: sa.Table
    column: str
    table: sa.Table
    label: str


_SUBJECTS: dict[str, _Subject] = {
    "application": _Subject(_application_geo_links, "application_id", _applications, "Application"),
    "legal_entity": _Subject(
        _legal_entity_geo_links, "legal_entity_id", _legal_entities, "Legal entity"
    ),
    "org_unit": _Subject(_org_unit_geo_links, "org_unit_id", _org_units, "Org unit"),
}


def _subject(subject_type: str) -> _Subject:
    return _SUBJECTS[subject_type]


async def _require_subject(subject_type: str, subject_id: str, session: AsyncSession) -> _Subject:
    sub = _subject(subject_type)
    found = (
        await session.execute(sa.select(sub.table.c.id).where(sub.table.c.id == subject_id))
    ).first()
    if found is None:
        raise OrgNotFoundError(f"{sub.label} {subject_id!r} not found")
    return sub


def _select(sub: _Subject) -> Any:
    t, g, h = sub.links, _geographies, _geo_hierarchies
    return sa.select(
        t,
        g.c.name.label("geo_name"),
        g.c.code.label("geo_code"),
        g.c.entity.label("geo_entity"),
        h.c.name.label("hierarchy_name"),
        h.c.kind.label("hierarchy_kind"),
    ).select_from(t.join(g, g.c.id == t.c.geography_id).outerjoin(h, h.c.id == g.c.hierarchy_id))


def _to_model(subject_type: str, sub: _Subject, r: Any, on: date) -> GeoLink:
    return GeoLink(
        id=r.id,
        subject_type=subject_type,  # type: ignore[arg-type]
        subject_id=getattr(r, sub.column),
        relation=r.relation,
        geography=LinkGeography(
            id=r.geography_id,
            name=r.geo_name,
            code=r.geo_code,
            entity=r.geo_entity,
            hierarchy_name=r.hierarchy_name,
            hierarchy_kind=r.hierarchy_kind,
        ),
        valid_from=r.valid_from,
        valid_to=r.valid_to,
        active=active(r.valid_from, r.valid_to, on),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _order(sub: _Subject) -> list[Any]:
    return [sub.links.c.relation, _geographies.c.name, sub.links.c.valid_from]


async def list_links(
    subject_type: GeoLinkSubject,
    subject_id: str,
    session: AsyncSession,
    as_of: date | None = None,
    include_inactive: bool = False,
) -> GeoLinkListResponse:
    sub = await _require_subject(subject_type, subject_id, session)
    on = as_of or date.today()
    rows = (
        await session.execute(
            _select(sub)
            .where(getattr(sub.links.c, sub.column) == subject_id)
            .order_by(*_order(sub))
        )
    ).all()
    items = [_to_model(subject_type, sub, r, on) for r in rows]
    if not include_inactive:
        items = [i for i in items if i.active]
    return GeoLinkListResponse(as_of=on, items=items)


async def all_links(subject_type: GeoLinkSubject, session: AsyncSession) -> list[GeoLink]:
    """Every link of one subject type (export, GEO-03 snapshots). One query."""
    sub = _subject(subject_type)
    on = date.today()
    q = _select(sub).order_by(getattr(sub.links.c, sub.column), *_order(sub))
    rows = (await session.execute(q)).all()
    return [_to_model(subject_type, sub, r, on) for r in rows]


async def _periods(sub: _Subject, subject_id: str, session: AsyncSession) -> list[Period]:
    t = sub.links
    return [
        Period(r.id, r.relation, r.geography_id, r.valid_from, r.valid_to)
        for r in await session.execute(
            sa.select(t.c.id, t.c.relation, t.c.geography_id, t.c.valid_from, t.c.valid_to).where(
                getattr(t.c, sub.column) == subject_id
            )
        )
    ]


async def _one(subject_type: str, sub: _Subject, link_id: str, session: AsyncSession) -> GeoLink:
    r = (await session.execute(_select(sub).where(sub.links.c.id == link_id))).first()
    if r is None:
        raise OrgNotFoundError(f"Geography link {link_id!r} not found")
    return _to_model(subject_type, sub, r, date.today())


async def add_link(
    subject_type: GeoLinkSubject, subject_id: str, body: GeoLinkCreate, session: AsyncSession
) -> GeoLink:
    sub = await _require_subject(subject_type, subject_id, session)
    geo = (
        await session.execute(
            sa.select(_geographies.c.entity).where(_geographies.c.id == body.geography_id)
        )
    ).first()
    if geo is None:
        raise OrgNotFoundError(f"Geography {body.geography_id!r} not found")
    link_id = str(uuid.uuid4())
    candidate = Period(link_id, body.relation, body.geography_id, body.valid_from, body.valid_to)
    check_link(
        subject_type, candidate, await _periods(sub, subject_id, session), geo.entity == "place"
    )
    now = _now()
    await session.execute(
        sub.links.insert().values(
            id=link_id,
            **{sub.column: subject_id},
            relation=body.relation,
            geography_id=body.geography_id,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
            created_at=now,
            updated_at=now,
        )
    )
    return await _one(subject_type, sub, link_id, session)


async def _owned_row(sub: _Subject, subject_id: str, link_id: str, session: AsyncSession) -> Any:
    t = sub.links
    row = (
        await session.execute(
            sa.select(t).where(t.c.id == link_id, getattr(t.c, sub.column) == subject_id)
        )
    ).first()
    if row is None:
        raise OrgNotFoundError(f"Geography link {link_id!r} not found")
    return row


async def update_link(
    subject_type: GeoLinkSubject,
    subject_id: str,
    link_id: str,
    body: GeoLinkUpdate,
    session: AsyncSession,
) -> GeoLink:
    sub = _subject(subject_type)
    row = await _owned_row(sub, subject_id, link_id, session)
    entity = (
        await session.execute(
            sa.select(_geographies.c.entity).where(_geographies.c.id == row.geography_id)
        )
    ).scalar_one()
    candidate = Period(link_id, row.relation, row.geography_id, body.valid_from, body.valid_to)
    others = [p for p in await _periods(sub, subject_id, session) if p.id != link_id]
    check_link(subject_type, candidate, others, entity == "place")
    await session.execute(
        sub.links.update()
        .where(sub.links.c.id == link_id)
        .values(valid_from=body.valid_from, valid_to=body.valid_to, updated_at=_now())
    )
    return await _one(subject_type, sub, link_id, session)


async def delete_link(
    subject_type: GeoLinkSubject, subject_id: str, link_id: str, session: AsyncSession
) -> GeoLink:
    sub = _subject(subject_type)
    await _owned_row(sub, subject_id, link_id, session)
    gone = await _one(subject_type, sub, link_id, session)
    await session.execute(sub.links.delete().where(sub.links.c.id == link_id))
    return gone


async def delete_subject_links(
    subject_type: GeoLinkSubject, subject_id: str, session: AsyncSession
) -> None:
    """FR-007: explicit cleanup when the subject is deleted (SQLite parity)."""
    sub = _subject(subject_type)
    await session.execute(
        sub.links.delete().where(getattr(sub.links.c, sub.column) == subject_id)
    )
