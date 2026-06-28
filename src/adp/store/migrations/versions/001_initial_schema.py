"""Initial ADP persistence schema.

Revision ID: 001
Revises:
Create Date: 2026-06-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "designs",
        sa.Column("id", sa.String(), nullable=False, primary_key=True),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("schema_version_at_creation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "design_versions",
        sa.Column("design_id", sa.String(), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("design_id", "version_num"),
    )

    op.create_index("ix_design_versions_content_gin", "design_versions", ["content"],
                    postgresql_using="gin")

    op.create_table(
        "audit_entries",
        sa.Column("id", sa.Text(), nullable=False, primary_key=True),
        sa.Column("design_id", sa.String(), nullable=False),
        sa.Column("design_version", sa.Integer(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("affected_entity", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_audit_entries_design", "audit_entries", ["design_id", "design_version"])

    # ART-IX / FR-004: Structural enforcement — audit entries are append-only.
    op.execute("""
        CREATE OR REPLACE FUNCTION deny_audit_mutation()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_entries is append-only: UPDATE and DELETE are prohibited (ART-IX / FR-004)';
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER audit_entries_immutable
            BEFORE UPDATE OR DELETE ON audit_entries
            FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_entries_immutable ON audit_entries")
    op.execute("DROP FUNCTION IF EXISTS deny_audit_mutation()")
    op.drop_index("ix_audit_entries_design", table_name="audit_entries")
    op.drop_table("audit_entries")
    op.drop_index("ix_design_versions_content_gin", table_name="design_versions")
    op.drop_table("design_versions")
    op.drop_table("designs")
