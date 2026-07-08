"""Design lifecycle: status + date columns on designs table (ADP-SPEC-030).

Revision ID: 006
Revises: 005
Create Date: 2026-07-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lifecycle status column — indexed for portfolio filter queries (SC-002)
    op.add_column(
        "designs",
        sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="draft"),
    )
    op.create_index("ix_designs_lifecycle", "designs", ["lifecycle_status"])

    # Lifecycle date columns
    op.add_column("designs", sa.Column("proposed_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("designs", sa.Column("current_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("designs", sa.Column("review_due", sa.DateTime(timezone=True), nullable=True))
    op.add_column("designs", sa.Column("retirement_date", sa.DateTime(timezone=True), nullable=True))

    # Partial index for overdue review queries (SC-004)
    op.create_index(
        "ix_designs_review_due",
        "designs",
        ["review_due"],
        postgresql_where=sa.text("review_due IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_designs_review_due", table_name="designs")
    op.drop_column("designs", "retirement_date")
    op.drop_column("designs", "review_due")
    op.drop_column("designs", "current_since")
    op.drop_column("designs", "proposed_date")
    op.drop_index("ix_designs_lifecycle", table_name="designs")
    op.drop_column("designs", "lifecycle_status")
