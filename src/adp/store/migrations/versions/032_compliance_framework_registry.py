"""Compliance Framework & Control Registry (COMPLY-01).

Two new tables:
  - regulatory_frameworks — reference data for a tracked regulation/standard
    (NIST, GDPR, SOC 2, ...); no lifecycle status column in this pass (spec.md
    Assumption — no evidence yet that frameworks need status tracking distinct
    from effective_date).
  - controls — self-referencing hierarchy of individual clauses/requirements
    within a framework. No 'level' column (unlike business_capabilities' fixed
    3-level scheme) — nesting depth is unbounded and genuinely varies
    clause-by-clause within one framework (data-model.md, research.md D8).

Both controls.framework_id and the self-referencing controls.parent_id use
ON DELETE CASCADE — a deliberate divergence from business_capabilities'
app-layer reject-on-children precedent (delete_capability raises
ChildCapabilitiesExist instead of cascading). This registry's spec (FR-005,
FR-013) explicitly requires cascade-with-disclosure, not block-and-force-
manual-cleanup; Postgres's native FK cascade recurses through the
self-referencing chain at arbitrary depth with no application code needed
(research.md D2).

UNIQUE(framework_id, code) is DB-level, not just an application-layer
pre-check (research.md D6) — code is unique within a framework, not globally.

Revision ID: 032
Revises: 031
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── regulatory_frameworks ──────────────────────────────────────────────
    op.create_table(
        "regulatory_frameworks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("jurisdiction", sa.String(255), nullable=False),
        sa.Column("authority", sa.String(255), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    # ── controls ────────────────────────────────────────────────────────────
    op.create_table(
        "controls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("framework_id", "code", name="uq_controls_framework_code"),
    )
    op.create_index("ix_controls_framework_id", "controls", ["framework_id"])
    op.create_index(
        "ix_controls_framework_parent_position",
        "controls",
        ["framework_id", "parent_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_controls_framework_parent_position", table_name="controls")
    op.drop_index("ix_controls_framework_id", table_name="controls")
    op.drop_table("controls")
    op.drop_table("regulatory_frameworks")
