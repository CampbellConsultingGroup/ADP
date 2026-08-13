"""ADP-d8u.2: Objective <-> design and objective <-> application traceability links.

Adds two new join tables, closing the top-priority open-frontier traceability
gap: an objective today links to capabilities/value streams (Layer 1) but
nothing forward to the designs (Layer 3) or applications (Layer 2) that
actually realize it.

objective_design_links follows capability_design_links/value_stream_design_links's
exact shape (migration 008) -- composite PK, ON DELETE CASCADE both legs, one
index on the "other side". design_id is TEXT (not VARCHAR(36)), matching
capability_design_links.design_id's exact type -- designs.id values are
DSN-NNN strings, not UUIDs (confirmed directly against migration 001).

objective_application_links is the same shape; application_id is VARCHAR(36),
matching applications.id's type (migration 010).

Revision ID: 028
Revises: 027
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "objective_design_links",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "design_id",
            sa.Text(),
            sa.ForeignKey("designs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_odl_design_id", "objective_design_links", ["design_id"])

    op.create_table(
        "objective_application_links",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_oal_application_id", "objective_application_links", ["application_id"])


def downgrade() -> None:
    op.drop_index("ix_oal_application_id", table_name="objective_application_links")
    op.drop_table("objective_application_links")
    op.drop_index("ix_odl_design_id", table_name="objective_design_links")
    op.drop_table("objective_design_links")
