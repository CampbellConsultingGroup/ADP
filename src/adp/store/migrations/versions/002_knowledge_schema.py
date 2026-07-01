"""Knowledge base schema: knowledge_items + knowledge_relationships.

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Embedding dimension read from env (NFR-002: scale via config, not code).
_EMBEDDING_DIM = int(os.environ.get("ADP_EMBEDDING_DIM", "384"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(), nullable=False, primary_key=True),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="1.0.0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Embedding column uses pgvector native type.
    op.execute(
        f"ALTER TABLE knowledge_items ADD COLUMN embedding vector({_EMBEDDING_DIM}) NOT NULL "
        f"DEFAULT array_fill(0, ARRAY[{_EMBEDDING_DIM}])::vector"
    )

    # Generated full-text search column (PostgreSQL generated column syntax).
    # op.add_column does not support GENERATED ALWAYS; use raw SQL.
    op.execute(
        "ALTER TABLE knowledge_items ADD COLUMN full_text_search TSVECTOR "
        "GENERATED ALWAYS AS (to_tsvector('english', full_text)) STORED"
    )

    # HNSW index for vector similarity (configurable m and ef_construction via env).
    _m = int(os.environ.get("ADP_HNSW_M", "16"))
    _ef = int(os.environ.get("ADP_HNSW_EF", "64"))
    op.execute(
        f"CREATE INDEX knowledge_items_embedding_hnsw ON knowledge_items "
        f"USING hnsw (embedding vector_cosine_ops) WITH (m={_m}, ef_construction={_ef})"
    )

    op.create_index("knowledge_items_fts_gin", "knowledge_items",
                    ["full_text_search"], postgresql_using="gin")
    op.create_index("knowledge_items_kind", "knowledge_items", ["kind"])
    op.execute(
        "CREATE INDEX knowledge_items_active ON knowledge_items (id) WHERE active = TRUE"
    )

    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.String(), nullable=False, primary_key=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_kr_source_type", "knowledge_relationships",
                    ["source_id", "relationship_type"])


def downgrade() -> None:
    op.drop_index("ix_kr_source_type", table_name="knowledge_relationships")
    op.drop_table("knowledge_relationships")
    op.execute("DROP INDEX IF EXISTS knowledge_items_active")
    op.drop_index("knowledge_items_kind", table_name="knowledge_items")
    op.drop_index("knowledge_items_fts_gin", table_name="knowledge_items")
    op.execute("DROP INDEX IF EXISTS knowledge_items_embedding_hnsw")
    op.drop_table("knowledge_items")
