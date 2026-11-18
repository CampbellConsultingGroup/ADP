"""LLM model choices in the database (ADP-blp.13).

The settings screen changed a dict in one worker's memory: other workers kept the old model and
a restart lost the choice. ``llm_settings`` holds the three model choices (extraction,
recommendation, validation), one row each, so every worker reads the same value. A missing row
means "use the deploy-time default". The API key is not stored here; it stays in the
environment.

Revision ID: 055
Revises: 054
Create Date: 2026-11-18
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_settings",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_settings")
