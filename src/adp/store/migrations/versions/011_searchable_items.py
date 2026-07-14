"""Unified searchable-text index for hybrid (keyword + vector) search.

A single polymorphic table indexes text from any registry entity (business
capabilities and technical capabilities in phase 1; value streams, domains, and
other fields later) so new sources can be added by writing rows — no per-entity
migration. Mirrors the knowledge-base pattern (pgvector HNSW + generated
TSVECTOR/GIN); RRF fusion happens in the application layer (ADP-b6o / ADP-SPEC-005).

Revision ID: 011
Revises: 010
Create Date: 2026-07-14
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMBEDDING_DIM = int(os.environ.get("ADP_EMBEDDING_DIM", "384"))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "searchable_items",
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("entity_type", "entity_id"),
    )

    # pgvector embedding column (zero-vector default until first embed).
    op.execute(
        f"ALTER TABLE searchable_items ADD COLUMN embedding vector({_EMBEDDING_DIM}) NOT NULL "
        f"DEFAULT array_fill(0, ARRAY[{_EMBEDDING_DIM}])::vector"
    )

    # Generated full-text-search column (raw SQL — op.add_column can't do GENERATED).
    op.execute(
        "ALTER TABLE searchable_items ADD COLUMN fts TSVECTOR "
        "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )

    _m = int(os.environ.get("ADP_HNSW_M", "16"))
    _ef = int(os.environ.get("ADP_HNSW_EF", "64"))
    op.execute(
        f"CREATE INDEX searchable_items_embedding_hnsw ON searchable_items "
        f"USING hnsw (embedding vector_cosine_ops) WITH (m={_m}, ef_construction={_ef})"
    )
    op.create_index("searchable_items_fts_gin", "searchable_items",
                    ["fts"], postgresql_using="gin")
    op.create_index("searchable_items_entity_type", "searchable_items", ["entity_type"])


def downgrade() -> None:
    op.drop_index("searchable_items_entity_type", table_name="searchable_items")
    op.drop_index("searchable_items_fts_gin", table_name="searchable_items")
    op.execute("DROP INDEX IF EXISTS searchable_items_embedding_hnsw")
    op.drop_table("searchable_items")
