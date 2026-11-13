"""Agent registry: agentic solutions and the AI agents that make them up (ADP-hii, 933).

Widens applications.application_type with 'agentic' (drop/re-create of migration 039's CHECK,
the same pattern migrations 013/020/026 used), and adds:
  - agents: a solution-independent registry of AI agents (model, prompt version reference,
    autonomy level 0-4, human-approval policy, data classification, design-time cost estimates,
    optional external runtime-registry reference);
  - solution_agents: many-to-many membership between an agentic application and an agent, with
    the agent's role and position in that solution. CASCADE on both legs: deleting a solution
    removes its memberships (never its agents); deleting an agent removes it from every solution.

Revision ID: 043
Revises: 042
Create Date: 2026-11-13
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "043"
down_revision: Union[str, None] = "042"
branch_labels = None
depends_on = None

_TYPES_OLD = "('custom', 'cots', 'saas', 'legacy')"
_TYPES_NEW = "('custom', 'cots', 'saas', 'legacy', 'agentic')"


def upgrade() -> None:
    op.drop_constraint("ck_app_application_type", "applications", type_="check")
    op.create_check_constraint(
        "ck_app_application_type",
        "applications",
        f"application_type IS NULL OR application_type IN {_TYPES_NEW}",
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(255), nullable=True),
        sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("model_provider", sa.String(100), nullable=True),
        sa.Column("model_id", sa.String(200), nullable=True),
        sa.Column("model_version", sa.String(100), nullable=True),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("prompt_ref", sa.String(200), nullable=True),
        sa.Column("autonomy_level", sa.SmallInteger(), nullable=False),
        sa.Column("human_approval", sa.Text(), nullable=False),
        sa.Column("data_classification_max", sa.Text(), nullable=True),
        sa.Column("a2a_card_url", sa.Text(), nullable=True),
        sa.Column("est_cost_per_run", sa.Numeric(12, 4), nullable=True),
        sa.Column("runs_per_month", sa.Integer(), nullable=True),
        sa.Column("external_registry_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lifecycle_status IN ('planned', 'active', 'sunset', 'retired')",
            name="ck_agents_lifecycle_status",
        ),
        sa.CheckConstraint("autonomy_level BETWEEN 0 AND 4", name="ck_agents_autonomy_level"),
        sa.CheckConstraint(
            "human_approval IN ('none', 'on_write', 'on_irreversible', 'always')",
            name="ck_agents_human_approval",
        ),
        sa.CheckConstraint(
            "data_classification_max IS NULL OR data_classification_max IN "
            "('public', 'internal', 'confidential', 'restricted')",
            name="ck_agents_data_classification_max",
        ),
        sa.CheckConstraint(
            "est_cost_per_run IS NULL OR est_cost_per_run >= 0",
            name="ck_agents_est_cost_per_run",
        ),
        sa.CheckConstraint(
            "runs_per_month IS NULL OR runs_per_month >= 0", name="ck_agents_runs_per_month"
        ),
    )
    op.create_index("ix_agents_autonomy_level", "agents", ["autonomy_level"])
    op.create_index("ix_agents_model_provider", "agents", ["model_provider"])
    op.create_index("ix_agents_lifecycle_status", "agents", ["lifecycle_status"])

    op.create_table(
        "solution_agents",
        sa.Column(
            "solution_app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.String(36),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("solution_app_id", "agent_id"),
        sa.CheckConstraint(
            "role IN ('orchestrator', 'worker', 'reviewer', 'router')",
            name="ck_solution_agents_role",
        ),
    )
    op.create_index("ix_solution_agents_agent_id", "solution_agents", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_solution_agents_agent_id", table_name="solution_agents")
    op.drop_table("solution_agents")
    op.drop_index("ix_agents_lifecycle_status", table_name="agents")
    op.drop_index("ix_agents_model_provider", table_name="agents")
    op.drop_index("ix_agents_autonomy_level", table_name="agents")
    op.drop_table("agents")

    op.execute("UPDATE applications SET application_type = NULL WHERE application_type = 'agentic'")
    op.drop_constraint("ck_app_application_type", "applications", type_="check")
    op.create_check_constraint(
        "ck_app_application_type",
        "applications",
        f"application_type IS NULL OR application_type IN {_TYPES_OLD}",
    )
