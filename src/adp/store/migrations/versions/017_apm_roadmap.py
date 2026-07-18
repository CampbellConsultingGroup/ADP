"""APM US6: lifecycle & roadmap — transformation initiatives (ADP-SPEC-038).

Adds transformation_initiatives (named change programs) and
application_initiative_links (many-to-many, each carrying a planned
disposition), building on the existing time_classification (TIME) and
lifecycle_status (US2) to power a decommission/roadmap view.

Revision ID: 017
Revises: 016
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transformation_initiatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "application_initiative_links",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("transformation_initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("planned_disposition", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("app_id", "initiative_id"),
        sa.CheckConstraint(
            "planned_disposition IN ('retire', 'replace', 'modernize', 'invest')",
            name="ck_ail_disposition",
        ),
    )
    op.create_index(
        "ix_ail_initiative", "application_initiative_links", ["initiative_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ail_initiative", table_name="application_initiative_links")
    op.drop_table("application_initiative_links")
    op.drop_table("transformation_initiatives")
