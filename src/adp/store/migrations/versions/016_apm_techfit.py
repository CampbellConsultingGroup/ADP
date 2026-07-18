"""APM US5: technical fit depth (ADP-SPEC-038).

Adds hosting_model, architecture_pattern, and tech_debt_flags to applications,
sharpening the technical-health side of the rationalization story alongside
the existing pace_layer / element_technology_tags / application_integrations.

Revision ID: 016
Revises: 015
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("hosting_model", sa.Text(), nullable=True))
    op.add_column(
        "applications", sa.Column("architecture_pattern", sa.Text(), nullable=True)
    )
    op.add_column(
        "applications",
        sa.Column(
            "tech_debt_flags", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.create_check_constraint(
        "ck_app_hosting_model",
        "applications",
        "hosting_model IS NULL OR hosting_model IN ('on_prem', 'cloud', 'saas', 'hybrid')",
    )
    op.create_index("ix_applications_hosting_model", "applications", ["hosting_model"])
    op.create_index(
        "ix_applications_tech_debt",
        "applications",
        ["tech_debt_flags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_applications_tech_debt", table_name="applications")
    op.drop_index("ix_applications_hosting_model", table_name="applications")
    op.drop_constraint("ck_app_hosting_model", "applications", type_="check")
    op.drop_column("applications", "tech_debt_flags")
    op.drop_column("applications", "architecture_pattern")
    op.drop_column("applications", "hosting_model")
