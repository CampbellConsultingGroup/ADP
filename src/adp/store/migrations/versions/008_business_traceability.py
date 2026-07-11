"""Business traceability: capability-design and value-stream-design links (ADP-SPEC-034).

Revision ID: 008
Revises: 007
Create Date: 2026-07-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # capability_design_links — M:M join between business_capabilities and designs
    op.create_table(
        "capability_design_links",
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "design_id", sa.Text(), sa.ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("capability_id", "design_id"),
    )
    op.create_index("ix_cdl_design_id", "capability_design_links", ["design_id"])

    # value_stream_design_links — M:M join between value_streams and designs
    op.create_table(
        "value_stream_design_links",
        sa.Column(
            "value_stream_id",
            sa.String(36),
            sa.ForeignKey("value_streams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "design_id", sa.Text(), sa.ForeignKey("designs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("value_stream_id", "design_id"),
    )
    op.create_index("ix_vsdl_design_id", "value_stream_design_links", ["design_id"])


def downgrade() -> None:
    op.drop_index("ix_vsdl_design_id", table_name="value_stream_design_links")
    op.drop_table("value_stream_design_links")
    op.drop_index("ix_cdl_design_id", table_name="capability_design_links")
    op.drop_table("capability_design_links")
