"""Initiative linkage for agent compliance mappings (ADP-321).

944 (ADP-12x) added the agent as the sixth COMPLY-02 mapping target (control_agent_mapping) but
kept 925's initiative <-> control-mapping linkage at five target types. This adds the sixth
parallel table in 034's exact shape: an initiative linked to one already-assessed
control_agent_mapping row through a composite FK, CASCADE on every leg, so deleting the mapping,
the control, the agent or the initiative removes the link. No existing table is altered.

Revision ID: 053
Revises: 052
Create Date: 2026-11-17
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "initiative_control_agent_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("agent_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "agent_id"],
            ["control_agent_mapping.control_id", "control_agent_mapping.agent_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icagm_mapping", "initiative_control_agent_mapping", ["control_id", "agent_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_icagm_mapping", table_name="initiative_control_agent_mapping")
    op.drop_table("initiative_control_agent_mapping")
