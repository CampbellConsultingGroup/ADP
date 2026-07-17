"""APM US2: application identity & ownership (ADP-SPEC-038).

Adds owning_business_unit, business_owner, technical_owner, and an explicit
lifecycle_status (planned/active/sunset/retired) to the applications table,
with indexes for business-unit and lifecycle filtering.

Revision ID: 013
Revises: 012
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications", sa.Column("owning_business_unit", sa.String(255), nullable=True)
    )
    op.add_column("applications", sa.Column("business_owner", sa.String(255), nullable=True))
    op.add_column("applications", sa.Column("technical_owner", sa.String(255), nullable=True))
    op.add_column(
        "applications",
        sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="active"),
    )
    op.create_check_constraint(
        "ck_app_lifecycle_status",
        "applications",
        "lifecycle_status IN ('planned', 'active', 'sunset', 'retired')",
    )
    op.create_index("ix_applications_lifecycle_status", "applications", ["lifecycle_status"])
    op.create_index("ix_applications_business_unit", "applications", ["owning_business_unit"])


def downgrade() -> None:
    op.drop_index("ix_applications_business_unit", table_name="applications")
    op.drop_index("ix_applications_lifecycle_status", table_name="applications")
    op.drop_constraint("ck_app_lifecycle_status", "applications", type_="check")
    op.drop_column("applications", "lifecycle_status")
    op.drop_column("applications", "technical_owner")
    op.drop_column("applications", "business_owner")
    op.drop_column("applications", "owning_business_unit")
