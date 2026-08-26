"""ADP-68z: Admin screen for editing scoring rubric weights (business value, and future
similar composite scores).

Two new tables, mirroring migration 023's agent_prompt_overrides/agent_prompt_history shape
exactly: rubric_weight_overrides (one row per rubric currently running an admin-saved override;
absence of a row means "using the hardcoded fallback constant") and rubric_weight_history
(append-only, one row per confirmed edit or restore -- never updated or deleted, per ART-IX).
Weights are stored as JSONB (not one column per dimension) so a future second registered rubric
needs zero schema change (spec.md SC-004) -- validated at the application layer by each rubric's
own registered validator (adp.admin.rubric_registry), not a DB CHECK constraint.

Revision ID: 040
Revises: 039
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rubric_weight_overrides",
        sa.Column("rubric_id", sa.Text(), primary_key=True),
        sa.Column("weights", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "rubric_weight_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("rubric_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("prior_weights", postgresql.JSONB(), nullable=False),
        sa.Column("new_weights", postgresql.JSONB(), nullable=False),
        sa.Column("confirmation_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('edit', 'restore')", name="ck_rubric_weight_history_change_type"
        ),
    )
    op.create_index(
        "ix_rubric_weight_history_rubric_id_changed_at",
        "rubric_weight_history",
        ["rubric_id", sa.text("changed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rubric_weight_history_rubric_id_changed_at", table_name="rubric_weight_history"
    )
    op.drop_table("rubric_weight_history")
    op.drop_table("rubric_weight_overrides")
