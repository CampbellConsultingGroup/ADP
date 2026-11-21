"""Legal entities and typed, dated geography links (947 GEO-02, ADP-bo1.2).

* ``legal_entities`` (new): the companies that contract, hold licences and file. Optional parent
  legal entity (group ownership); name unique ignoring case.
* ``legal_entity_org_units`` and ``application_legal_entities`` (new): plain many-to-many links.
* ``application_geo_links``, ``legal_entity_geo_links``, ``org_unit_geo_links`` (new, one shape):
  a subject touches a place or node through a relation, valid from a date (inclusive) until a
  date (exclusive); NULL = open. Which relation fits which subject is checked in
  ``adp.organization.geo_links``; the CHECK here only bounds each table's vocabulary.
* Every ``org_unit_geographies`` row (940) becomes an undated ``operates_in`` link and the table
  is dropped. Downgrade rebuilds it from the ``operates_in`` links (dates are lost).

Revision ID: 058
Revises: 057
Create Date: 2026-11-20
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels = None
depends_on = None

# (table, subject column, subject table, relations) -- frozen copy of the 947 vocabulary.
LINK_TABLES = (
    (
        "application_geo_links",
        "application_id",
        "applications",
        ("deployed_in", "stores_data_in", "processes_personal_data_of", "serves_customers_in"),
    ),
    (
        "legal_entity_geo_links",
        "legal_entity_id",
        "legal_entities",
        ("incorporated_in", "licensed_in", "has_establishment_in", "tax_resident_in"),
    ),
    (
        "org_unit_geo_links",
        "org_unit_id",
        "org_units",
        ("operates_in", "serves_customers_in", "has_staff_in"),
    ),
)


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("registration_number", sa.String(100), nullable=True),
        sa.Column("lei", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("legal_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_ts(),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_legal_entities_parent"),
    )
    op.create_index(
        "uq_legal_entities_name", "legal_entities", [sa.text("lower(name)")], unique=True
    )
    op.create_index("ix_legal_entities_parent_id", "legal_entities", ["parent_id"])
    op.create_index(
        "uq_legal_entities_lei",
        "legal_entities",
        ["lei"],
        unique=True,
        postgresql_where=sa.text("lei IS NOT NULL"),
    )

    for name, left, left_table, right, right_table in (
        ("legal_entity_org_units", "legal_entity_id", "legal_entities", "org_unit_id", "org_units"),
        (
            "application_legal_entities",
            "application_id",
            "applications",
            "legal_entity_id",
            "legal_entities",
        ),
    ):
        op.create_table(
            name,
            sa.Column(
                left,
                sa.String(36),
                sa.ForeignKey(f"{left_table}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                right,
                sa.String(36),
                sa.ForeignKey(f"{right_table}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint(left, right),
        )
        op.create_index(f"ix_{name}_{right}", name, [right])

    for table, subject, subject_table, relations in LINK_TABLES:
        allowed = ", ".join(f"'{r}'" for r in relations)
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                subject,
                sa.String(36),
                sa.ForeignKey(f"{subject_table}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("relation", sa.String(40), nullable=False),
            sa.Column(
                "geography_id",
                sa.String(36),
                sa.ForeignKey("geographies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("valid_from", sa.Date(), nullable=True),
            sa.Column("valid_to", sa.Date(), nullable=True),
            *_ts(),
            sa.CheckConstraint(f"relation IN ({allowed})", name=f"ck_{table}_relation"),
            sa.CheckConstraint(
                "valid_from IS NULL OR valid_to IS NULL OR valid_to > valid_from",
                name=f"ck_{table}_dates",
            ),
        )
        op.create_index(f"ix_{table}_subject", table, [subject])
        op.create_index(f"ix_{table}_geography", table, ["geography_id"])

    op.execute(
        """
        INSERT INTO org_unit_geo_links
               (id, org_unit_id, relation, geography_id, created_at, updated_at)
        SELECT gen_random_uuid()::text, org_unit_id, 'operates_in', geography_id,
               created_at, created_at
          FROM org_unit_geographies
        """
    )
    op.drop_table("org_unit_geographies")


def downgrade() -> None:
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
    op.execute(
        """
        INSERT INTO org_unit_geographies (org_unit_id, geography_id, created_at)
        SELECT org_unit_id, geography_id, min(created_at)
          FROM org_unit_geo_links
         WHERE relation = 'operates_in'
         GROUP BY org_unit_id, geography_id
        """
    )
    for table, *_ in LINK_TABLES:
        op.drop_table(table)
    op.drop_table("application_legal_entities")
    op.drop_table("legal_entity_org_units")
    op.drop_table("legal_entities")
