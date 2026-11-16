"""Regional assessments.

942-regional-assessments (ADP-55k.3, spec 3 of epic ADP-55k). A business capability can be assessed
per region or country (maturity 1-5 and/or a variant note); the capability's own maturity_level
stays the enterprise baseline and is not touched. A capability can be flagged region-specific
with the geographies it applies in -- a 1:1 flag table so the flag survives losing its last
geography ("scope needs updating"). Applicability, heat map cells and deltas are derived on read.

Revision ID: 050
Revises: 049
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capability_regional_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("maturity_level", sa.SmallInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "maturity_level IS NULL OR maturity_level BETWEEN 1 AND 5",
            name="ck_regional_assessment_maturity",
        ),
        sa.CheckConstraint(
            "maturity_level IS NOT NULL OR note IS NOT NULL",
            name="ck_regional_assessment_content",
        ),
        sa.CheckConstraint(
            "note IS NULL OR length(note) <= 1000", name="ck_regional_assessment_note_length"
        ),
        sa.UniqueConstraint("capability_id", "geography_id", name="uq_regional_assessment"),
    )
    op.create_index(
        "ix_regional_assessment_geography", "capability_regional_assessments", ["geography_id"]
    )
    op.create_table(
        "region_specific_capabilities",
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "region_specific_capability_geographies",
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("region_specific_capabilities.capability_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("capability_id", "geography_id"),
    )


def downgrade() -> None:
    op.drop_table("region_specific_capability_geographies")
    op.drop_table("region_specific_capabilities")
    op.drop_index("ix_regional_assessment_geography", table_name="capability_regional_assessments")
    op.drop_table("capability_regional_assessments")
