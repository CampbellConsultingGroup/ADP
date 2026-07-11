"""Business Architecture: capabilities and value streams (ADP-SPEC-033).

Revision ID: 007
Revises: 006
Create Date: 2026-07-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # business_capabilities — self-referential adjacency list, max 3 levels
    op.create_table(
        "business_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column(
            "parent_id", sa.String(36), sa.ForeignKey("business_capabilities.id"), nullable=True
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("level IN (1, 2, 3)", name="ck_business_capabilities_level"),
    )
    op.create_index("ix_bc_parent_id", "business_capabilities", ["parent_id"])
    op.create_index("ix_bc_parent_position", "business_capabilities", ["parent_id", "position"])

    # value_streams
    op.create_table(
        "value_streams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stakeholder", sa.String(255), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_vs_position", "value_streams", ["position"])

    # value_stream_stages — CASCADE on delete of parent value stream
    op.create_table(
        "value_stream_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "value_stream_id",
            sa.String(36),
            sa.ForeignKey("value_streams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_vss_vs_position", "value_stream_stages", ["value_stream_id", "position"])


def downgrade() -> None:
    op.drop_table("value_stream_stages")
    op.drop_table("value_streams")
    op.drop_table("business_capabilities")
