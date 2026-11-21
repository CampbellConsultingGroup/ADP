"""Subdivisions, governed custom places and the regulatory blocs (949 GEO-04, ADP-bo1.4).

* ``geographies.parent_place_id``: the country a subdivision or an authority lies in. A place
  contains itself and the places whose parent place it is, so a link to California (US-CA) is
  inside the United States wherever the United States is a member.
* ``place_type`` is checked: country, subdivision (needs a parent place), authority, residual.
* Seeds two custom places (Lloyd's of London inside GB; Rest of World) and the "Regulatory blocs"
  hierarchy (EU, EEA) with dated country memberships, from ``data/regulatory_blocs.json``.

No subdivision is inserted: they are added on demand, validated against the pinned ISO 3166-2
snapshot. Downgrade deletes the seeded rows and every subdivision (and, by CASCADE, any link,
membership or mapping that points at them).

Revision ID: 060
Revises: 059
Create Date: 2026-11-21
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

import sqlalchemy as sa
from alembic import op

from adp.organization.geodata import BLOCS_HIERARCHY_ID, blocs_seed

revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels = None
depends_on = None

_PLACE_TYPES = "'country', 'subdivision', 'authority', 'residual'"


def _tables() -> tuple[sa.Table, sa.Table, sa.Table]:
    meta = sa.MetaData()
    hierarchies = sa.Table(
        "geo_hierarchies",
        meta,
        sa.Column("id", sa.String(36)),
        sa.Column("name", sa.String(255)),
        sa.Column("kind", sa.Text()),
        sa.Column("shape", sa.Text()),
        sa.Column("system_of_record", sa.String(255)),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    geographies = sa.Table(
        "geographies",
        meta,
        sa.Column("id", sa.String(36)),
        sa.Column("name", sa.String(255)),
        sa.Column("code", sa.String(8)),
        sa.Column("m49", sa.String(3)),
        sa.Column("entity", sa.Text()),
        sa.Column("hierarchy_id", sa.String(36)),
        sa.Column("place_type", sa.Text()),
        sa.Column("parent_place_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    memberships = sa.Table(
        "geo_memberships",
        meta,
        sa.Column("id", sa.String(36)),
        sa.Column("hierarchy_id", sa.String(36)),
        sa.Column("parent_id", sa.String(36)),
        sa.Column("child_id", sa.String(36)),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    return hierarchies, geographies, memberships


def upgrade() -> None:
    op.add_column(
        "geographies",
        sa.Column(
            "parent_place_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", name="fk_geographies_parent_place"),
            nullable=True,
        ),
    )
    op.create_index("ix_geographies_parent_place", "geographies", ["parent_place_id"])
    op.create_check_constraint(
        "ck_geographies_place_type",
        "geographies",
        f"(entity = 'node' AND parent_place_id IS NULL) OR (entity = 'place' AND place_type IN"
        f" ({_PLACE_TYPES}) AND (place_type <> 'subdivision' OR parent_place_id IS NOT NULL)"
        " AND (place_type <> 'country' OR parent_place_id IS NULL))",
    )

    hierarchies, geographies, memberships = _tables()
    seed = blocs_seed(datetime.now(timezone.utc))
    op.bulk_insert(geographies, seed["places"])
    op.bulk_insert(hierarchies, [seed["hierarchy"]])
    op.bulk_insert(geographies, seed["nodes"])
    op.bulk_insert(memberships, seed["memberships"])


def downgrade() -> None:
    _, geographies, _ = _tables()
    seed = blocs_seed(datetime.now(timezone.utc))
    op.execute(sa.text("DELETE FROM geo_memberships WHERE hierarchy_id = :h").bindparams(
        h=BLOCS_HIERARCHY_ID
    ))
    op.execute(sa.text("DELETE FROM geographies WHERE hierarchy_id = :h").bindparams(
        h=BLOCS_HIERARCHY_ID
    ))
    op.execute(sa.text("DELETE FROM geo_hierarchies WHERE id = :h").bindparams(
        h=BLOCS_HIERARCHY_ID
    ))
    ids = [p["id"] for p in seed["places"]]
    op.execute(geographies.delete().where(geographies.c.id.in_(ids)))
    op.execute("DELETE FROM geographies WHERE place_type = 'subdivision'")
    op.drop_constraint("ck_geographies_place_type", "geographies", type_="check")
    op.drop_index("ix_geographies_parent_place", table_name="geographies")
    op.drop_constraint("fk_geographies_parent_place", "geographies", type_="foreignkey")
    op.drop_column("geographies", "parent_place_id")
