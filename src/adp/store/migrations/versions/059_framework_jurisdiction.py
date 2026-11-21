"""Framework jurisdiction: places/nodes and trigger relations (948 GEO-03, ADP-bo1.3).

* ``framework_jurisdiction_geographies``: the places and hierarchy nodes a regulatory framework
  covers (e.g. the EU node of a regulatory hierarchy).
* ``framework_jurisdiction_triggers``: the typed geography relations (947) that bring a subject
  into scope, per subject type (e.g. application / processes_personal_data_of).

Applicability itself is derived on read and never stored. The free-text
``regulatory_frameworks.jurisdiction`` stays as the display label.

Revision ID: 059
Revises: 058
Create Date: 2026-11-20
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "framework_jurisdiction_geographies",
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("framework_id", "geography_id"),
    )
    op.create_index(
        "ix_framework_jurisdiction_geographies_geography",
        "framework_jurisdiction_geographies",
        ["geography_id"],
    )
    op.create_table(
        "framework_jurisdiction_triggers",
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
        sa.CheckConstraint(
            "subject_type IN ('application', 'legal_entity')",
            name="ck_framework_jurisdiction_triggers_subject",
        ),
    )


def downgrade() -> None:
    op.drop_table("framework_jurisdiction_triggers")
    op.drop_table("framework_jurisdiction_geographies")
