"""ADP-d8u.1: Capture strategic objectives as structured entities.

Two new core tables (strategic_themes, strategic_objectives) plus two new
many-to-many join tables to business_capabilities/value_streams, mirroring
migration 008's capability_design_links/value_stream_design_links shape
exactly (composite PK, ON DELETE CASCADE both legs, one index, created_at) --
research.md Decision 2. metric_name/target_value/target_unit/direction are
all-or-nothing as a group, enforced at the Pydantic layer (data-model.md),
not a single-column DB constraint. direction/period are CHECK-constrained
text columns (data-model.md: a bounded set that's semantic, not an ordered
scale, unlike strategic_relevance/maturity_level's SmallInteger precedent).

Revision ID: 025
Revises: 024
Create Date: 2026-08-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategic_themes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "strategic_objectives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "theme_id",
            sa.String(36),
            sa.ForeignKey("strategic_themes.id"),
            nullable=False,
        ),
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("metric_name", sa.Text(), nullable=True),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("target_unit", sa.Text(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("fiscal_year", sa.SmallInteger(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_strategic_obj_direction",
        "strategic_objectives",
        "direction IS NULL OR direction IN ('increase', 'decrease', 'reach')",
    )
    op.create_check_constraint(
        "ck_strategic_obj_period",
        "strategic_objectives",
        "period IN ('Q1', 'Q2', 'Q3', 'Q4', 'FY')",
    )

    # strategic_objective_capabilities -- M:M join, mirrors capability_design_links
    op.create_table(
        "strategic_objective_capabilities",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("objective_id", "capability_id"),
    )
    op.create_index(
        "ix_soc_capability_id", "strategic_objective_capabilities", ["capability_id"]
    )

    # strategic_objective_value_streams -- M:M join, mirrors value_stream_design_links
    op.create_table(
        "strategic_objective_value_streams",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "value_stream_id",
            sa.String(36),
            sa.ForeignKey("value_streams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("objective_id", "value_stream_id"),
    )
    op.create_index(
        "ix_sovs_value_stream_id", "strategic_objective_value_streams", ["value_stream_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_sovs_value_stream_id", table_name="strategic_objective_value_streams")
    op.drop_table("strategic_objective_value_streams")
    op.drop_index("ix_soc_capability_id", table_name="strategic_objective_capabilities")
    op.drop_table("strategic_objective_capabilities")
    op.drop_constraint("ck_strategic_obj_period", "strategic_objectives", type_="check")
    op.drop_constraint("ck_strategic_obj_direction", "strategic_objectives", type_="check")
    op.drop_table("strategic_objectives")
    op.drop_table("strategic_themes")
