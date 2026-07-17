"""APM US3: application risk & compliance register (ADP-SPEC-038).

Adds a 1:1 ``application_risk`` table (cascade-deletes with the application):
security posture, vulnerability status, data classification, regulatory tags,
DR/BC status, and end-of-life / end-of-support dates.

Revision ID: 014
Revises: 013
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_risk",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("security_posture", sa.Text(), nullable=True),
        sa.Column("vulnerability_status", sa.Text(), nullable=True),
        sa.Column("data_classification", sa.Text(), nullable=True),
        sa.Column("regulatory_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("dr_bc_status", sa.Text(), nullable=True),
        sa.Column("end_of_life_date", sa.Date(), nullable=True),
        sa.Column("end_of_support_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_app_risk_eos",
        "application_risk",
        ["end_of_support_date"],
        postgresql_where=sa.text("end_of_support_date IS NOT NULL"),
    )
    op.create_index("ix_app_risk_class", "application_risk", ["data_classification"])


def downgrade() -> None:
    op.drop_index("ix_app_risk_class", table_name="application_risk")
    op.drop_index("ix_app_risk_eos", table_name="application_risk")
    op.drop_table("application_risk")
