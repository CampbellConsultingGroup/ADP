"""ADP-SPEC-042: Admin screen for managing AI agent system prompts.

Two new tables: agent_prompt_overrides (one row per agent currently
running an admin-saved override; absence of a row means "using the
built-in fallback") and agent_prompt_history (append-only, one row per
confirmed edit or restore -- never updated or deleted, per ART-IX).
The existing hardcoded Python prompt constants are left untouched and
remain each agent's default/fallback (data-model.md).

Revision ID: 023
Revises: 022
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_prompt_overrides",
        sa.Column("agent_id", sa.Text(), primary_key=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "agent_prompt_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("prior_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("confirmation_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('edit', 'restore')", name="ck_agent_prompt_history_change_type"
        ),
    )
    op.create_index(
        "ix_agent_prompt_history_agent_id_changed_at",
        "agent_prompt_history",
        ["agent_id", sa.text("changed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_prompt_history_agent_id_changed_at", table_name="agent_prompt_history"
    )
    op.drop_table("agent_prompt_history")
    op.drop_table("agent_prompt_overrides")
