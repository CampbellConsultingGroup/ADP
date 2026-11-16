"""Org Units and Geography reference models.

940-org-units-geography (ADP-55k.1, spec 1 of epic ADP-55k). Two governed trees under Business
Architecture -- org units (enterprise > division > function) and geography (global > region >
country, seeded from the committed ISO 3166 / UN M49 data file) -- an org unit <-> geography
link, and an optional owning org unit on applications. The free-text
applications.owning_business_unit is untouched; a review queue maps it onto org units.

Revision ID: 048
Revises: 047
Create Date: 2026-11-15
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union

import sqlalchemy as sa
from alembic import op

from adp.organization.geodata import geography_seed_rows

revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    geographies = op.create_table(
        "geographies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(8), nullable=True),
        sa.Column("m49", sa.String(3), nullable=True),
        # No cascade: the store refuses to delete a geography that has children.
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("geographies.id"), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="ck_geographies_level"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_geographies_sibling_name ON geographies "
        "(COALESCE(parent_id, ''), lower(name))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_geographies_code ON geographies (code) WHERE code IS NOT NULL"
    )

    op.create_table(
        "org_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("org_units.id"), nullable=True),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column(
            "primary_geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="ck_org_units_level"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_org_units_sibling_name ON org_units "
        "(COALESCE(parent_id, ''), lower(name))"
    )

    op.create_table(
        "org_unit_geographies",
        sa.Column(
            "org_unit_id",
            sa.String(36),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("org_unit_id", "geography_id"),
    )
    op.create_index("ix_oug_geography_id", "org_unit_geographies", ["geography_id"])

    op.add_column("applications", sa.Column("owning_org_unit_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_applications_owning_org_unit",
        "applications",
        "org_units",
        ["owning_org_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_owning_org_unit_id", "applications", ["owning_org_unit_id"])

    op.bulk_insert(geographies, geography_seed_rows(datetime.now(timezone.utc)))


def downgrade() -> None:
    op.drop_index("ix_applications_owning_org_unit_id", table_name="applications")
    op.drop_constraint("fk_applications_owning_org_unit", "applications", type_="foreignkey")
    op.drop_column("applications", "owning_org_unit_id")
    op.drop_index("ix_oug_geography_id", table_name="org_unit_geographies")
    op.drop_table("org_unit_geographies")
    op.execute("DROP INDEX IF EXISTS uq_org_units_sibling_name")
    op.drop_table("org_units")
    op.execute("DROP INDEX IF EXISTS uq_geographies_code")
    op.execute("DROP INDEX IF EXISTS uq_geographies_sibling_name")
    op.drop_table("geographies")
