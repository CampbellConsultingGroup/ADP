"""Element technology tags: indexed table for portfolio queries (ADP-SPEC-029).

Revision ID: 005
Revises: 004
Create Date: 2026-07-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "element_technology_tags",
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=False),
        sa.Column("technology", sa.Text(), nullable=True),
        sa.Column("vendor", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("owner_team", sa.Text(), nullable=True),
        sa.Column("free_tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("design_id", "element_id"),
    )

    # B-tree indexes for structured field queries
    op.create_index("ix_ett_technology", "element_technology_tags", ["technology"])
    op.create_index("ix_ett_platform", "element_technology_tags", ["platform"])
    op.create_index("ix_ett_owner_team", "element_technology_tags", ["owner_team"])

    # GIN index for free-form tag containment queries
    op.create_index(
        "ix_ett_free_tags",
        "element_technology_tags",
        ["free_tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_ett_free_tags", table_name="element_technology_tags")
    op.drop_index("ix_ett_owner_team", table_name="element_technology_tags")
    op.drop_index("ix_ett_platform", table_name="element_technology_tags")
    op.drop_index("ix_ett_technology", table_name="element_technology_tags")
    op.drop_table("element_technology_tags")
