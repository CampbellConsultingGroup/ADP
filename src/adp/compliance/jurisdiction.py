"""Framework jurisdiction and derived applicability, with I/O (948 GEO-03, ADP-bo1.3).

The jurisdiction (places/nodes + trigger relations) is stored here; applicability is computed on
read by the pure ``adp.compliance.applicability`` over a snapshot read from the organization
domain (946 geography graph as of the date, 947 typed links and legal entity links). Reading
organization from compliance is one-way: ``adp.organization`` never imports compliance (GT-2).

The tables are on the compliance metadata so every compliance fixture creates them. The geography
column has no foreign key here (geographies live on the organization metadata); migration 059
holds the real CASCADE, and reads inner-join geographies, so a dangling id never surfaces.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.compliance.applicability import (
    FrameworkFacts,
    LinkFact,
    Result,
    compute_framework_applicability,
)
from adp.compliance.models import (
    Applicability,
    ApplicabilityEvidence,
    ApplicabilityRef,
    FrameworkApplicabilityResponse,
    FrameworkJurisdiction,
    JurisdictionGeography,
    JurisdictionTrigger,
    SetFrameworkJurisdiction,
    SubjectApplicabilityResponse,
)
from adp.compliance.store import _frameworks, _metadata
from adp.organization import geo_links, legal_entities
from adp.organization import store as ostore
from adp.organization.geo_model import GeoGraph

_jurisdiction_geographies = sa.Table(
    "framework_jurisdiction_geographies",
    _metadata,
    sa.Column(
        "framework_id",
        sa.String(36),
        sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("geography_id", sa.String(36), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("framework_id", "geography_id"),
)

_jurisdiction_triggers = sa.Table(
    "framework_jurisdiction_triggers",
    _metadata,
    sa.Column(
        "framework_id",
        sa.String(36),
        sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("subject_type", sa.String(20), nullable=False),
    sa.Column("relation", sa.String(40), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint("framework_id", "subject_type", "relation"),
)

SUBJECTS = ("application", "legal_entity")


class JurisdictionError(ValueError):
    """A jurisdiction the rules don't allow (422)."""


class FrameworkNotFound(LookupError):
    pass


class SubjectNotFound(LookupError):
    pass


def _label(subject_type: str, relation: str) -> str:
    rule = geo_links.RELATIONS.get(subject_type, {}).get(relation)
    return rule.label if rule else relation.replace("_", " ")


def _relation_labels() -> dict[str, str]:
    return {r: rule.label for rules in geo_links.RELATIONS.values() for r, rule in rules.items()}


# ── Geography details ─────────────────────────────────────────────────────────


async def _geographies(
    session: AsyncSession, ids: set[str] | None = None
) -> dict[str, JurisdictionGeography]:
    g, h = ostore._geographies, ostore._geo_hierarchies
    q = sa.select(
        g.c.id, g.c.name, g.c.code, g.c.entity, h.c.name.label("hname"), h.c.kind.label("hkind")
    ).select_from(g.outerjoin(h, h.c.id == g.c.hierarchy_id))
    if ids is not None:
        if not ids:
            return {}
        q = q.where(g.c.id.in_(ids))
    return {
        r.id: JurisdictionGeography(
            id=r.id,
            name=r.name,
            code=r.code,
            entity=r.entity,
            hierarchy_name=r.hname,
            hierarchy_kind=r.hkind,
        )
        for r in await session.execute(q)
    }


# ── Jurisdiction (FR-001, FR-002) ─────────────────────────────────────────────


async def _require_framework(framework_id: str, session: AsyncSession) -> Any:
    row = (
        await session.execute(sa.select(_frameworks).where(_frameworks.c.id == framework_id))
    ).first()
    if row is None:
        raise FrameworkNotFound(f"Framework {framework_id!r} not found")
    return row


async def _scopes(
    session: AsyncSession,
) -> tuple[dict[str, list[str]], dict[str, set[tuple[str, str]]]]:
    geos: dict[str, list[str]] = defaultdict(list)
    g = ostore._geographies
    for fid, gid in await session.execute(
        sa.select(
            _jurisdiction_geographies.c.framework_id, _jurisdiction_geographies.c.geography_id
        )
        .select_from(
            _jurisdiction_geographies.join(g, g.c.id == _jurisdiction_geographies.c.geography_id)
        )
        .order_by(g.c.name)
    ):
        geos[fid].append(gid)
    triggers: dict[str, set[tuple[str, str]]] = defaultdict(set)
    t = _jurisdiction_triggers
    for fid, st, rel in await session.execute(
        sa.select(t.c.framework_id, t.c.subject_type, t.c.relation)
    ):
        triggers[fid].add((st, rel))
    return geos, triggers


async def get_jurisdiction(framework_id: str, session: AsyncSession) -> FrameworkJurisdiction:
    await _require_framework(framework_id, session)
    geos, triggers = await _scopes(session)
    ids = geos.get(framework_id, [])
    details = await _geographies(session, set(ids))
    trig = sorted(
        triggers.get(framework_id, set()),
        key=lambda t: (SUBJECTS.index(t[0]) if t[0] in SUBJECTS else 9, t[1]),
    )
    return FrameworkJurisdiction(
        framework_id=framework_id,
        configured=bool(ids) and bool(trig),
        geographies=[details[i] for i in ids if i in details],
        triggers=[
            JurisdictionTrigger(subject_type=st, relation=rel, label=_label(st, rel))  # type: ignore[arg-type]
            for st, rel in trig
        ],
    )


async def set_jurisdiction(
    framework_id: str, body: SetFrameworkJurisdiction, session: AsyncSession
) -> FrameworkJurisdiction:
    await _require_framework(framework_id, session)
    geo_ids = list(dict.fromkeys(body.geography_ids))
    known = await _geographies(session, set(geo_ids))
    missing = [g for g in geo_ids if g not in known]
    if missing:
        raise JurisdictionError(f"Unknown geography: {', '.join(missing)}")
    pairs = list(dict.fromkeys((t.subject_type, t.relation) for t in body.triggers))
    for st, rel in pairs:
        if rel not in geo_links.RELATIONS.get(st, {}):
            allowed = ", ".join(geo_links.RELATIONS.get(st, {}))
            raise JurisdictionError(
                f"Relation {rel!r} is not a {st.replace('_', ' ')} relation (allowed: {allowed})"
            )
    now = datetime.now(timezone.utc)
    await session.execute(
        _jurisdiction_geographies.delete().where(
            _jurisdiction_geographies.c.framework_id == framework_id
        )
    )
    await session.execute(
        _jurisdiction_triggers.delete().where(_jurisdiction_triggers.c.framework_id == framework_id)
    )
    if geo_ids:
        await session.execute(
            _jurisdiction_geographies.insert(),
            [{"framework_id": framework_id, "geography_id": g, "created_at": now} for g in geo_ids],
        )
    if pairs:
        await session.execute(
            _jurisdiction_triggers.insert(),
            [
                {
                    "framework_id": framework_id,
                    "subject_type": st,
                    "relation": rel,
                    "created_at": now,
                }
                for st, rel in pairs
            ],
        )
    return await get_jurisdiction(framework_id, session)


# ── Snapshot (one read per request, fixed number of queries) ──────────────────


@dataclass
class _Snapshot:
    as_of: date
    graph: GeoGraph
    frameworks: list[FrameworkFacts]
    links: dict[tuple[str, str], list[LinkFact]]  # (subject type, id) -> own links
    app_entities: dict[str, list[str]]
    names: dict[tuple[str, str], str]


async def _snapshot(
    session: AsyncSession, as_of: date, framework_id: str | None = None
) -> _Snapshot:
    f = _frameworks
    q = sa.select(
        f.c.id, f.c.name, f.c.status, f.c.entry_into_force_date, f.c.effective_date
    ).order_by(f.c.name)
    if framework_id is not None:
        q = q.where(f.c.id == framework_id)
    geos, triggers = await _scopes(session)
    frameworks = [
        FrameworkFacts(
            id=r.id,
            name=r.name,
            status=r.status,
            in_force_from=r.entry_into_force_date or r.effective_date,
            geography_ids=tuple(geos.get(r.id, [])),
            triggers=frozenset(triggers.get(r.id, set())),
        )
        for r in await session.execute(q)
    ]
    links: dict[tuple[str, str], list[LinkFact]] = defaultdict(list)
    for subject in SUBJECTS:
        for lk in await geo_links.all_links(subject, session):  # type: ignore[arg-type]
            links[(subject, lk.subject_id)].append(
                LinkFact(subject, lk.relation, lk.geography.id, lk.valid_from, lk.valid_to)
            )
    app_entities: dict[str, list[str]] = defaultdict(list)
    for app_id, le_id in await legal_entities.all_application_links(session):
        app_entities[app_id].append(le_id)
    names: dict[tuple[str, str], str] = {}
    a = ostore._applications
    for r in await session.execute(sa.select(a.c.id, a.c.name)):
        names[("application", r.id)] = r.name
    le = ostore._legal_entities
    for r in await session.execute(sa.select(le.c.id, le.c.name)):
        names[("legal_entity", r.id)] = r.name
    return _Snapshot(
        as_of, await ostore.geo_graph(session, as_of), frameworks, links, app_entities, names
    )


def _subject_links(s: _Snapshot, subject_type: str, subject_id: str) -> list[LinkFact]:
    own = list(s.links.get((subject_type, subject_id), []))
    if subject_type == "application":  # Q1: an application inherits its legal entities' links
        for le_id in s.app_entities.get(subject_id, []):
            name = s.names.get(("legal_entity", le_id), le_id)
            own += [
                LinkFact(
                    lk.subject_type,
                    lk.relation,
                    lk.geography_id,
                    lk.valid_from,
                    lk.valid_to,
                    le_id,
                    name,
                )
                for lk in s.links.get(("legal_entity", le_id), [])
            ]
    return own


def _to_model(
    s: _Snapshot,
    f: FrameworkFacts,
    subject_type: str,
    subject_id: str,
    result: Result,
    geos: dict[str, JurisdictionGeography],
) -> Applicability:
    def geo(i: str) -> JurisdictionGeography:
        return geos.get(i) or JurisdictionGeography(id=i, name=i)

    return Applicability(
        framework=ApplicabilityRef(id=f.id, name=f.name),
        subject_type=subject_type,  # type: ignore[arg-type]
        subject=ApplicabilityRef(
            id=subject_id, name=s.names.get((subject_type, subject_id), subject_id)
        ),
        status=result.status,
        reason=result.reason,
        evidence=[
            ApplicabilityEvidence(
                relation=m.link.relation,
                relation_label=_label(m.link.subject_type, m.link.relation),
                geography=geo(m.link.geography_id),
                jurisdiction_geography=geo(m.scope_id),
                how=m.how,
                path=[geo(p).name for p in m.path],
                via_legal_entity=(
                    ApplicabilityRef(id=m.link.via_id, name=m.link.via_name or m.link.via_id)
                    if m.link.via_id
                    else None
                ),
                valid_from=m.link.valid_from,
                valid_to=m.link.valid_to,
            )
            for m in result.matches
        ],
    )


async def _evaluate(
    s: _Snapshot, pairs: list[tuple[FrameworkFacts, str, str]], session: AsyncSession
) -> list[Applicability]:
    labels = _relation_labels()
    results = [
        (
            f,
            st,
            sid,
            compute_framework_applicability(
                f, _subject_links(s, st, sid), s.graph, s.as_of, labels
            ),
        )
        for f, st, sid in pairs
    ]
    needed = {m.link.geography_id for *_, r in results for m in r.matches} | {
        m.scope_id for *_, r in results for m in r.matches
    }
    needed |= {p for *_, r in results for m in r.matches for p in m.path}
    geos = await _geographies(session, needed)
    return [_to_model(s, f, st, sid, r, geos) for f, st, sid, r in results]


async def subject_applicability(
    subject_type: str, subject_id: str, session: AsyncSession, as_of: date | None = None
) -> SubjectApplicabilityResponse:
    on = as_of or date.today()
    s = await _snapshot(session, on)
    if (subject_type, subject_id) not in s.names:
        raise SubjectNotFound(
            f"{subject_type.replace('_', ' ').capitalize()} {subject_id!r} not found"
        )
    items = await _evaluate(s, [(f, subject_type, subject_id) for f in s.frameworks], session)
    order = {"applies": 0, "unknown": 1, "does_not_apply": 2}
    items.sort(key=lambda a: (order[a.status], a.framework.name.lower()))
    return SubjectApplicabilityResponse(
        as_of=on,
        subject_type=subject_type,  # type: ignore[arg-type]
        subject_id=subject_id,
        items=items,
    )


async def framework_applicability(
    framework_id: str, session: AsyncSession, as_of: date | None = None
) -> FrameworkApplicabilityResponse:
    on = as_of or date.today()
    await _require_framework(framework_id, session)
    s = await _snapshot(session, on, framework_id)
    f = s.frameworks[0]
    subjects = sorted(
        (k for k in s.names), key=lambda k: (SUBJECTS.index(k[0]), s.names[k].lower())
    )
    items = await _evaluate(s, [(f, st, sid) for st, sid in subjects], session)
    counts = {"applies": 0, "does_not_apply": 0, "unknown": 0}
    for i in items:
        counts[i.status] += 1
    return FrameworkApplicabilityResponse(
        as_of=on,
        framework_id=framework_id,
        configured=bool(f.geography_ids) and bool(f.triggers),
        counts=counts,  # type: ignore[arg-type]
        items=items,
    )
