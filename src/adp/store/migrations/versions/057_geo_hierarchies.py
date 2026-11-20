"""Geography as places, typed hierarchies and dated memberships (946 GEO-01, ADP-bo1.1).

``geographies`` stays the one table everything links to, and every id is kept, so the six
tables that reference it are untouched. Each row becomes a **place** (a country) or a **node**
of a hierarchy:

* ``geo_hierarchies`` (new): name, kind, shape (strict tree or DAG), system of record. The 940
  UN M49 tree becomes the read-only reference hierarchy ``geoh-m49``: Global and the UN regions
  are its nodes.
* ``geo_memberships`` (new): a node or place under a node of the same hierarchy, valid from a
  date (inclusive) until a date (exclusive); NULL = open. Every old ``parent_id`` link becomes an
  undated membership.
* Regions and the like that users added to the old tree become nodes of a "Custom (migrated)"
  hierarchy (created only if there are any), with their old children as members.
* ``geographies.parent_id`` and ``level`` are dropped; the sibling-name index becomes a per-
  hierarchy node-name index.

Revision ID: 057
Revises: 056
Create Date: 2026-11-20
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels = None
depends_on = None

REFERENCE_ID = "geoh-m49"
CUSTOM_ID = "geoh-custom-migrated"
KINDS = (
    "reference", "regulatory", "data_residency", "infrastructure", "sales", "tax",
    "operational", "custom",
)


def upgrade() -> None:
    kinds = ", ".join(f"'{k}'" for k in KINDS)
    op.create_table(
        "geo_hierarchies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("shape", sa.Text(), nullable=False),
        sa.Column("system_of_record", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"kind IN ({kinds})", name="ck_geo_hierarchies_kind"),
        sa.CheckConstraint("shape IN ('strict_tree', 'dag')", name="ck_geo_hierarchies_shape"),
    )
    op.create_index(
        "uq_geo_hierarchies_name", "geo_hierarchies", [sa.text("lower(name)")], unique=True
    )
    op.execute(
        "INSERT INTO geo_hierarchies (id, name, kind, shape, system_of_record, description,"
        " created_at, updated_at) VALUES"
        f" ('{REFERENCE_ID}', 'UN M49 regions', 'reference', 'strict_tree', 'UN M49',"
        " 'The UN M49 standard regions with ISO 3166 countries. Read-only reference.',"
        " now(), now())"
    )

    op.add_column(
        "geographies",
        sa.Column("entity", sa.Text(), nullable=False, server_default="place"),
    )
    op.add_column(
        "geographies",
        sa.Column(
            "hierarchy_id", sa.String(36), sa.ForeignKey("geo_hierarchies.id"), nullable=True
        ),
    )
    op.add_column("geographies", sa.Column("place_type", sa.Text(), nullable=True))

    op.execute(
        f"UPDATE geographies SET entity = 'node', hierarchy_id = '{REFERENCE_ID}'"
        " WHERE id = 'geo-001' OR id LIKE 'geo-m49-%'"
    )
    # Rows users added above country level (940 allowed new regions under Global).
    op.execute(
        f"""
        INSERT INTO geo_hierarchies (id, name, kind, shape, description, created_at, updated_at)
        SELECT '{CUSTOM_ID}', 'Custom (migrated)', 'custom', 'dag',
               'Regions added to the old geography tree before hierarchies existed.', now(), now()
         WHERE EXISTS (SELECT 1 FROM geographies WHERE level < 3 AND entity = 'place')
        """
    )
    op.execute(
        f"UPDATE geographies SET entity = 'node', hierarchy_id = '{CUSTOM_ID}'"
        " WHERE level < 3 AND entity = 'place'"
    )
    op.execute("UPDATE geographies SET place_type = 'country' WHERE entity = 'place'")

    op.create_table(
        "geo_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "hierarchy_id",
            sa.String(36),
            sa.ForeignKey("geo_hierarchies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_to > valid_from",
            name="ck_geo_memberships_dates",
        ),
        sa.CheckConstraint("parent_id <> child_id", name="ck_geo_memberships_not_self"),
    )
    op.create_index("ix_geo_memberships_hierarchy", "geo_memberships", ["hierarchy_id"])
    op.create_index("ix_geo_memberships_parent", "geo_memberships", ["parent_id"])
    op.create_index("ix_geo_memberships_child", "geo_memberships", ["child_id"])
    # Every old parent link becomes an undated membership in the parent's hierarchy. A node of
    # another hierarchy (a migrated custom region under Global) becomes a root instead.
    op.execute(
        """
        INSERT INTO geo_memberships (id, hierarchy_id, parent_id, child_id, created_at, updated_at)
        SELECT gen_random_uuid()::text, p.hierarchy_id, p.id, c.id, now(), now()
          FROM geographies c JOIN geographies p ON p.id = c.parent_id
         WHERE NOT (c.entity = 'node' AND c.hierarchy_id <> p.hierarchy_id)
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_geographies_sibling_name")
    op.drop_constraint("ck_geographies_level", "geographies", type_="check")
    op.drop_column("geographies", "parent_id")
    op.drop_column("geographies", "level")
    op.create_check_constraint(
        "ck_geographies_entity",
        "geographies",
        "(entity = 'node' AND hierarchy_id IS NOT NULL AND place_type IS NULL)"
        " OR (entity = 'place' AND hierarchy_id IS NULL)",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_geographies_node_name ON geographies"
        " (hierarchy_id, lower(name)) WHERE entity = 'node'"
    )
    op.create_index("ix_geographies_hierarchy_id", "geographies", ["hierarchy_id"])


def downgrade() -> None:
    op.drop_index("ix_geographies_hierarchy_id", table_name="geographies")
    op.execute("DROP INDEX IF EXISTS uq_geographies_node_name")
    op.drop_constraint("ck_geographies_entity", "geographies", type_="check")
    op.add_column(
        "geographies",
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("geographies.id"), nullable=True),
    )
    op.add_column("geographies", sa.Column("level", sa.SmallInteger(), nullable=True))
    op.execute(
        "UPDATE geographies SET level = CASE WHEN entity = 'place' THEN 3"
        " WHEN id = 'geo-001' THEN 1 ELSE 2 END"
    )
    # The old tree: a place's reference region (or Global); every node but Global under Global.
    # Memberships of other hierarchies can't be expressed in one tree and are dropped; their
    # nodes come back as regions named "<node> (<hierarchy>)" so names can't collide.
    op.execute(
        f"""
        UPDATE geographies g SET parent_id = m.parent_id
          FROM geo_memberships m
         WHERE m.child_id = g.id AND m.hierarchy_id = '{REFERENCE_ID}'
           AND g.entity = 'place' AND m.valid_to IS NULL
        """
    )
    op.execute(
        "UPDATE geographies SET parent_id = 'geo-001'"
        " WHERE entity = 'place' AND parent_id IS NULL AND id <> 'geo-001'"
    )
    op.execute(
        f"""
        UPDATE geographies g SET parent_id = 'geo-001',
               name = CASE WHEN g.hierarchy_id = '{REFERENCE_ID}' THEN g.name
                           ELSE left(g.name || ' (' || h.name || ')', 255) END
          FROM geo_hierarchies h
         WHERE h.id = g.hierarchy_id AND g.entity = 'node' AND g.id <> 'geo-001'
        """
    )
    op.alter_column("geographies", "level", nullable=False)
    op.create_check_constraint("ck_geographies_level", "geographies", "level BETWEEN 1 AND 3")
    op.execute(
        "CREATE UNIQUE INDEX uq_geographies_sibling_name ON geographies "
        "(COALESCE(parent_id, ''), lower(name))"
    )
    op.drop_index("ix_geo_memberships_child", table_name="geo_memberships")
    op.drop_index("ix_geo_memberships_parent", table_name="geo_memberships")
    op.drop_index("ix_geo_memberships_hierarchy", table_name="geo_memberships")
    op.drop_table("geo_memberships")
    op.drop_column("geographies", "place_type")
    op.drop_column("geographies", "hierarchy_id")
    op.drop_column("geographies", "entity")
    op.drop_index("uq_geo_hierarchies_name", table_name="geo_hierarchies")
    op.drop_table("geo_hierarchies")
