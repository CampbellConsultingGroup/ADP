"""Business Domain Registry: domains table, domain_id FK on capabilities, stage-capability links.

Revision ID: 009
Revises: 008
Create Date: 2026-07-10
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("scope_statement", sa.Text(), nullable=True),
        sa.Column(
            "classification",
            sa.Text(),
            nullable=False,
            # safety-net constraint; Pydantic also validates at the API layer
        ),
        sa.Column("org_unit", sa.String(255), nullable=True),
        sa.Column(
            "risk_flags",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "classification IN ('strategic', 'differentiating', 'commodity')",
            name="ck_business_domains_classification",
        ),
    )
    op.create_index("ix_business_domains_name", "business_domains", ["name"])

    op.add_column(
        "business_capabilities",
        sa.Column(
            "domain_id",
            sa.String(36),
            sa.ForeignKey("business_domains.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_business_capabilities_domain_id",
        "business_capabilities",
        ["domain_id"],
    )

    op.create_table(
        "value_stream_stage_capabilities",
        sa.Column(
            "stage_id",
            sa.String(36),
            sa.ForeignKey("value_stream_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("stage_id", "capability_id"),
    )
    op.create_index(
        "ix_vssc_capability_id",
        "value_stream_stage_capabilities",
        ["capability_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_vssc_capability_id", table_name="value_stream_stage_capabilities")
    op.drop_table("value_stream_stage_capabilities")
    op.drop_index("ix_business_capabilities_domain_id", table_name="business_capabilities")
    op.drop_column("business_capabilities", "domain_id")
    op.drop_index("ix_business_domains_name", table_name="business_domains")
    op.drop_table("business_domains")
