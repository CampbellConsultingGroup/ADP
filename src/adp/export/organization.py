"""Export org units and geography (940-org-units-geography, research R7).

Called at the end of the business-architecture reconciliation cycle, so it lands under
``business-architecture/organization/``:

    organization/org-units/<id>.json        one file per org unit (geography links, applications)
    organization/legal-entities/<id>.json   one file per legal entity (947 GEO-02)
    organization/application-geo-links.json every application's legal entities and geo links
    organization/geographies.json           the whole geography tree, one file

A fixed number of queries per cycle (no N+1). Org-unit files of deleted units are removed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.export.common import _cleanup_orphan_files, _safe_filename, _write_entity_file
from adp.organization import geo_links, hierarchies, legal_entities
from adp.organization import store as ostore
from adp.organization.models import (
    Geography,
    GeoHierarchyDetail,
    GeoLink,
    LegalEntity,
    OrgUnit,
)


def _link(g: GeoLink) -> dict[str, Any]:
    return {
        "relation": g.relation,
        "geography_id": g.geography.id,
        "valid_from": g.valid_from.isoformat() if g.valid_from else None,
        "valid_to": g.valid_to.isoformat() if g.valid_to else None,
    }


def _links(items: list[GeoLink]) -> list[dict[str, Any]]:
    return sorted(
        (_link(g) for g in items),
        key=lambda d: (d["relation"], d["geography_id"], d["valid_from"] or ""),
    )


def _serialize_legal_entity(
    le: LegalEntity, application_ids: list[str], links: list[GeoLink]
) -> dict[str, Any]:
    return {
        "id": le.id,
        "name": le.name,
        "registration_number": le.registration_number,
        "lei": le.lei,
        "description": le.description,
        "parent_id": le.parent_id,
        "path": [p.name for p in le.path],
        "org_unit_ids": sorted(le.org_unit_ids),
        "application_ids": sorted(application_ids),
        "geo_links": _links(links),
    }


def _serialize_org_unit(
    ou: OrgUnit, application_ids: list[str], links: list[GeoLink] | None = None
) -> dict[str, Any]:
    return {
        "id": ou.id,
        "name": ou.name,
        "description": ou.description,
        "kind": ou.kind,
        "level": ou.level,
        "parent_id": ou.parent_id,
        "path": [p.name for p in ou.path],
        "primary_geography_id": ou.primary_geography_id,
        "geography_ids": sorted(ou.geography_ids),
        "application_ids": sorted(application_ids),
        # 947: every typed link, dated (geography_ids above = operates_in active today).
        "geo_links": _links(links or []),
    }


def _serialize_geographies(
    items: list[Geography], hierarchy_details: list[GeoHierarchyDetail] | None = None
) -> dict[str, Any]:
    return {
        "geographies": [
            {
                "id": g.id,
                "name": g.name,
                "kind": g.kind,
                "entity": g.entity,
                "hierarchy_id": g.hierarchy_id,
                "code": g.code,
                "m49": g.m49,
                "parent_id": g.parent_id,  # the reference (UN M49) parent today
                "place_type": g.place_type,  # 949: country | subdivision | authority | residual
                "parent_place_id": g.parent_place_id,
            }
            for g in sorted(items, key=lambda g: (g.level, g.name))
        ],
        # 946 GEO-01: every hierarchy with its dated memberships (all of them, not only today's).
        "hierarchies": [
            {
                "id": h.id,
                "name": h.name,
                "kind": h.kind,
                "shape": h.shape,
                "system_of_record": h.system_of_record,
                "description": h.description,
                "node_ids": [n.id for n in h.nodes],
                "memberships": [
                    {
                        "parent_id": m.parent_id,
                        "child_id": m.child_id,
                        "valid_from": m.valid_from.isoformat() if m.valid_from else None,
                        "valid_to": m.valid_to.isoformat() if m.valid_to else None,
                    }
                    for m in sorted(
                        h.memberships,
                        key=lambda m: (m.parent_id, m.child_id, str(m.valid_from or "")),
                    )
                ],
            }
            for h in hierarchy_details or []
        ],
    }


async def reconcile_organization(root: Path, session: AsyncSession, now: datetime) -> None:
    org_units = (await ostore.list_org_units(session)).items
    geographies = (await ostore.list_geographies(session)).items
    details = [
        d
        for h in (await hierarchies.list_hierarchies(session)).items
        if (d := await hierarchies.get_hierarchy(h.id, session)) is not None
    ]
    apps_by_ou: dict[str, list[str]] = defaultdict(list)
    for app_id, ou_id in (
        await session.execute(
            sa.select(ostore._applications.c.id, ostore._applications.c.owning_org_unit_id).where(
                ostore._applications.c.owning_org_unit_id.is_not(None)
            )
        )
    ).all():
        apps_by_ou[ou_id].append(app_id)

    by_subject: dict[tuple[str, str], list[GeoLink]] = defaultdict(list)
    for subject in ("application", "legal_entity", "org_unit"):
        for link in await geo_links.all_links(subject, session):  # type: ignore[arg-type]
            by_subject[(subject, link.subject_id)].append(link)
    entities = (await legal_entities.list_legal_entities(session)).items
    app_entities: dict[str, list[str]] = defaultdict(list)
    entity_apps: dict[str, list[str]] = defaultdict(list)
    for app_id, le_id in await legal_entities.all_application_links(session):
        app_entities[app_id].append(le_id)
        entity_apps[le_id].append(app_id)

    base = root / "organization"
    for ou in org_units:
        _write_entity_file(
            base / "org-units" / _safe_filename(ou.id),
            _serialize_org_unit(
                ou, apps_by_ou.get(ou.id, []), by_subject.get(("org_unit", ou.id), [])
            ),
            now,
        )
    for le in entities:
        _write_entity_file(
            base / "legal-entities" / _safe_filename(le.id),
            _serialize_legal_entity(
                le, entity_apps.get(le.id, []), by_subject.get(("legal_entity", le.id), [])
            ),
            now,
        )
    app_ids = sorted(
        set(app_entities) | {sid for (kind, sid) in by_subject if kind == "application"}
    )
    _write_entity_file(
        base / "application-geo-links.json",
        {
            "applications": [
                {
                    "application_id": a,
                    "legal_entity_ids": sorted(app_entities.get(a, [])),
                    "geo_links": _links(by_subject.get(("application", a), [])),
                }
                for a in app_ids
            ]
        },
        now,
    )
    _cleanup_orphan_files(base / "legal-entities", {le.id for le in entities})
    _write_entity_file(base / "geographies.json", _serialize_geographies(geographies, details), now)
    _cleanup_orphan_files(base / "org-units", {ou.id for ou in org_units})
