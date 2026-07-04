"""Persistent operation store: operations table (ADP-SPEC-024).

Revision ID: 003
Revises: 002
Create Date: 2026-07-03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "operations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("actor", sa.Text(), nullable=False, server_default="architect"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_ops_design_type_status",
        "operations",
        ["design_id", "type", "status"],
    )
    op.create_index(
        "ix_ops_expires_at",
        "operations",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ops_expires_at", table_name="operations")
    op.drop_index("ix_ops_design_type_status", table_name="operations")
    op.drop_table("operations")
