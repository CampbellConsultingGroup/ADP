"""APM US8: quality & performance signals (ADP-SPEC-038).

Adds a 1:1 ``application_quality_metrics`` table (cascade-deletes with the
application): uptime %, incident count (YTD), user satisfaction score,
a free-text performance note, and 30-day support-ticket volume.

Manual/advisory in v1 (FR-011/021) — these signals never override
``applications.health_score``.

Revision ID: 019
Revises: 018
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_quality_metrics",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("uptime_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("incidents_ytd", sa.Integer(), nullable=True),
        sa.Column("satisfaction_score", sa.SmallInteger(), nullable=True),
        sa.Column("perf_note", sa.Text(), nullable=True),
        sa.Column("ticket_volume_30d", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_aqm_uptime_pct",
        "application_quality_metrics",
        "uptime_pct IS NULL OR uptime_pct BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "ck_aqm_incidents_ytd",
        "application_quality_metrics",
        "incidents_ytd IS NULL OR incidents_ytd >= 0",
    )
    op.create_check_constraint(
        "ck_aqm_satisfaction_score",
        "application_quality_metrics",
        "satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_aqm_ticket_volume_30d",
        "application_quality_metrics",
        "ticket_volume_30d IS NULL OR ticket_volume_30d >= 0",
    )


def downgrade() -> None:
    op.drop_table("application_quality_metrics")
