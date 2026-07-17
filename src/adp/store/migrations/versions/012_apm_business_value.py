"""APM US1: business-value scores on applications (ADP-SPEC-038).

Adds ``business_value`` and ``business_criticality`` — 1–5 assessment scores,
NULL = not assessed — to the applications table. The TIME rationalization
projection places each application from ``business_value`` × ``health_score``.

Revision ID: 012
Revises: 011
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications", sa.Column("business_value", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "applications", sa.Column("business_criticality", sa.SmallInteger(), nullable=True)
    )
    op.create_check_constraint(
        "ck_app_business_value",
        "applications",
        "business_value IS NULL OR business_value BETWEEN 1 AND 5",
    )
    op.create_check_constraint(
        "ck_app_business_criticality",
        "applications",
        "business_criticality IS NULL OR business_criticality BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_app_business_criticality", "applications", type_="check")
    op.drop_constraint("ck_app_business_value", "applications", type_="check")
    op.drop_column("applications", "business_criticality")
    op.drop_column("applications", "business_value")
