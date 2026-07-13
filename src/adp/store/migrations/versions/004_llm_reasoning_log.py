"""Immutable LLM reasoning log — append-only table with DB-level triggers (ADP-SPEC-027).

Revision ID: 004
Revises: 003
Create Date: 2026-07-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Requires pgcrypto for gen_random_uuid() — available in PostgreSQL 14+
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "llm_reasoning_log",
        sa.Column(
            "id",
            sa.Text(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("option_id", sa.Text(), nullable=True),
        sa.Column("step_name", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("reasoning_text", sa.Text(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("prompt_hash", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_reasoning_operation", "llm_reasoning_log", ["operation_id"])
    op.create_index(
        "ix_reasoning_option",
        "llm_reasoning_log",
        ["option_id"],
        postgresql_where=sa.text("option_id IS NOT NULL"),
    )

    # ── Immutability: PL/pgSQL function + triggers ────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION llm_reasoning_immutable()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'llm_reasoning_log is append-only — UPDATE is not permitted';
            ELSIF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'llm_reasoning_log is append-only — DELETE is not permitted';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_reasoning_no_update
            BEFORE UPDATE ON llm_reasoning_log
            FOR EACH ROW EXECUTE FUNCTION llm_reasoning_immutable();
    """)

    op.execute("""
        CREATE TRIGGER trg_reasoning_no_delete
            BEFORE DELETE ON llm_reasoning_log
            FOR EACH ROW EXECUTE FUNCTION llm_reasoning_immutable();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reasoning_no_delete ON llm_reasoning_log")
    op.execute("DROP TRIGGER IF EXISTS trg_reasoning_no_update ON llm_reasoning_log")
    op.execute("DROP FUNCTION IF EXISTS llm_reasoning_immutable()")
    op.drop_index("ix_reasoning_option", table_name="llm_reasoning_log")
    op.drop_index("ix_reasoning_operation", table_name="llm_reasoning_log")
    op.drop_table("llm_reasoning_log")
