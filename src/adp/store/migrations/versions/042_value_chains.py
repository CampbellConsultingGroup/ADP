"""Value chains (Porter): chains, their primary/support activities, activity-capability links.

ADP-nag. Mirrors the value stream tables (migrations 007/009): a chain owns ordered activities,
and an activity links to the business capabilities it depends on. An activity's category is
'primary' (the sequential chain that creates value) or 'support' (enables the whole chain);
position orders activities within their own category.

Revision ID: 042
Revises: 041
Create Date: 2026-11-11
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "value_chains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("margin_label", sa.String(255), nullable=False, server_default="Margin"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "value_chain_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "value_chain_id",
            sa.String(36),
            sa.ForeignKey("value_chains.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # safety-net constraint; Pydantic also validates at the API layer
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "category IN ('primary', 'support')",
            name="ck_value_chain_activities_category",
        ),
    )
    op.create_index(
        "ix_value_chain_activities_chain_category_position",
        "value_chain_activities",
        ["value_chain_id", "category", "position"],
    )

    op.create_table(
        "value_chain_activity_capabilities",
        sa.Column(
            "activity_id",
            sa.String(36),
            sa.ForeignKey("value_chain_activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("activity_id", "capability_id"),
    )
    op.create_index(
        "ix_vcac_capability_id",
        "value_chain_activity_capabilities",
        ["capability_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vcac_capability_id", table_name="value_chain_activity_capabilities")
    op.drop_table("value_chain_activity_capabilities")
    op.drop_index(
        "ix_value_chain_activities_chain_category_position", table_name="value_chain_activities"
    )
    op.drop_table("value_chain_activities")
    op.drop_table("value_chains")
