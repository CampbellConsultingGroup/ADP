"""Application Registry: 8 new tables for application portfolio management.

Revision ID: 010
Revises: 009
Create Date: 2026-07-11
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("primary_owner", sa.String(255), nullable=True),
        sa.Column("time_classification", sa.Text(), nullable=True),
        sa.Column("r_strategy", sa.Text(), nullable=True),
        sa.Column("pace_layer", sa.Text(), nullable=True),
        sa.Column("health_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "time_classification IN ('Tolerate', 'Invest', 'Migrate', 'Eliminate')",
            name="ck_applications_time_classification",
        ),
        sa.CheckConstraint(
            "r_strategy IN ('Rehost', 'Replatform', 'Repurchase', 'Refactor', "
            "'Retire', 'Retain', 'Relocate')",
            name="ck_applications_r_strategy",
        ),
        sa.CheckConstraint(
            "pace_layer IN ('Record', 'Differentiation', 'Innovation')",
            name="ck_applications_pace_layer",
        ),
        sa.CheckConstraint(
            "health_score BETWEEN 1 AND 5",
            name="ck_applications_health_score",
        ),
    )
    op.create_index("ix_applications_name", "applications", ["name"])

    op.create_table(
        "technical_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("technical_capabilities.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level IN (1, 2, 3)", name="ck_technical_capabilities_level"),
    )
    op.create_index("ix_technical_capabilities_parent_id", "technical_capabilities", ["parent_id"])

    op.create_table(
        "application_capability_links",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fit_score", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("app_id", "capability_id"),
        sa.CheckConstraint("fit_score BETWEEN 1 AND 5", name="ck_acl_fit_score"),
    )
    op.create_index("ix_acl_capability_id", "application_capability_links", ["capability_id"])

    op.create_table(
        "application_tech_cap_links",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tech_cap_id",
            sa.String(36),
            sa.ForeignKey("technical_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_type", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("app_id", "tech_cap_id", "usage_type"),
        sa.CheckConstraint("usage_type IN ('provides', 'consumes')", name="ck_atcl_usage_type"),
    )
    op.create_index("ix_atcl_tech_cap_id", "application_tech_cap_links", ["tech_cap_id"])

    op.create_table(
        "application_stage_links",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "stage_id",
            sa.String(36),
            sa.ForeignKey("value_stream_stages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("app_id", "stage_id"),
    )
    op.create_index("ix_asl_stage_id", "application_stage_links", ["stage_id"])

    op.create_table(
        "application_domain_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "domain_id",
            sa.String(36),
            sa.ForeignKey("business_domains.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("integration_type", sa.String(255), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound', 'bidirectional')",
            name="ck_adi_direction",
        ),
    )
    op.create_index("ix_adi_app_id", "application_domain_integrations", ["app_id"])
    op.create_index("ix_adi_domain_id", "application_domain_integrations", ["domain_id"])

    op.create_table(
        "application_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "source_app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("integration_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "integration_type IN ('API', 'event', 'file', 'database', 'messaging', 'other')",
            name="ck_ai_integration_type",
        ),
        sa.CheckConstraint("source_app_id <> target_app_id", name="ck_ai_no_self_loop"),
    )
    op.create_index("ix_ai_source", "application_integrations", ["source_app_id"])
    op.create_index("ix_ai_target", "application_integrations", ["target_app_id"])

    op.create_table(
        "application_design_links",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "design_id",
            sa.String(36),
            sa.ForeignKey("designs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("app_id", "design_id"),
    )
    op.create_index("ix_adl_design_id", "application_design_links", ["design_id"])


def downgrade() -> None:
    op.drop_index("ix_adl_design_id", table_name="application_design_links")
    op.drop_table("application_design_links")

    op.drop_index("ix_ai_target", table_name="application_integrations")
    op.drop_index("ix_ai_source", table_name="application_integrations")
    op.drop_table("application_integrations")

    op.drop_index("ix_adi_domain_id", table_name="application_domain_integrations")
    op.drop_index("ix_adi_app_id", table_name="application_domain_integrations")
    op.drop_table("application_domain_integrations")

    op.drop_index("ix_asl_stage_id", table_name="application_stage_links")
    op.drop_table("application_stage_links")

    op.drop_index("ix_atcl_tech_cap_id", table_name="application_tech_cap_links")
    op.drop_table("application_tech_cap_links")

    op.drop_index("ix_acl_capability_id", table_name="application_capability_links")
    op.drop_table("application_capability_links")

    op.drop_index("ix_technical_capabilities_parent_id", table_name="technical_capabilities")
    op.drop_table("technical_capabilities")

    op.drop_index("ix_applications_name", table_name="applications")
    op.drop_table("applications")
