"""APM US4: Total Cost of Ownership (ADP-9x6, ADP-SPEC-038).

Adds a 1:1 ``application_cost`` table (cascade-deletes with the application):
eight cost buckets (acquisition, implementation, training, operational,
maintenance, upgrades, risk_downtime, end_of_life), each carrying a one-time
and an annual amount, plus currency (ISO-4217) and an analysis horizon.

TCO = Σ(one_time) + Σ(annual) × horizon_years, computed on read (never
stored, so it can never drift from its inputs). Money is NUMERIC — never
float/double.

Revision ID: 015
Revises: 014
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BUCKETS = (
    "acquisition", "implementation", "training", "operational",
    "maintenance", "upgrades", "risk_downtime", "end_of_life",
)


def upgrade() -> None:
    columns = [
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("horizon_years", sa.SmallInteger(), nullable=False, server_default="5"),
    ]
    for bucket in _BUCKETS:
        columns.append(
            sa.Column(f"{bucket}_one_time", sa.Numeric(14, 2), nullable=False, server_default="0")
        )
        columns.append(
            sa.Column(f"{bucket}_annual", sa.Numeric(14, 2), nullable=False, server_default="0")
        )
    columns.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

    op.create_table("application_cost", *columns)
    op.create_check_constraint(
        "ck_app_cost_horizon_positive", "application_cost", "horizon_years > 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_cost_horizon_positive", "application_cost", type_="check")
    op.drop_table("application_cost")
