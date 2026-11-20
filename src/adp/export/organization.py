"""Export org units and geography (940-org-units-geography, research R7).

Called at the end of the business-architecture reconciliation cycle, so it lands under
``business-architecture/organization/``:

    organization/org-units/<id>.json   one file per org unit (geography links, applications)
    organization/geographies.json      the whole geography tree, one file

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
from adp.organization import hierarchies
from adp.organization import store as ostore
from adp.organization.models import Geography, GeoHierarchyDetail, OrgUnit


def _serialize_org_unit(ou: OrgUnit, application_ids: list[str]) -> dict[str, Any]:
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

    base = root / "organization"
    for ou in org_units:
        _write_entity_file(
            base / "org-units" / _safe_filename(ou.id),
            _serialize_org_unit(ou, apps_by_ou.get(ou.id, [])),
            now,
        )
    _write_entity_file(base / "geographies.json", _serialize_geographies(geographies, details), now)
    _cleanup_orphan_files(base / "org-units", {ou.id for ou in org_units})
