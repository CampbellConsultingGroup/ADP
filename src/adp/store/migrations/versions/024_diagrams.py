"""ADP-SPEC-046: Diagram types beyond C4 -- standalone diagram storage.

One new table, `diagrams`. Deliberately no foreign key to `designs` --
standalone, top-level artifacts in v1 (FR-011, spec.md Clarifications).
`dsl_source` is opaque to the backend (research.md Decision 2): parsing,
validation, and rendering all happen client-side in the vendored
diagram-core library (web/src/diagrams/core/).

Revision ID: 024
Revises: 023
Create Date: 2026-08-06
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diagrams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("diagram_type", sa.Text(), nullable=False),
        sa.Column("dsl_source", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("diagrams")
