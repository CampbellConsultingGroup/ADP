"""Theme–Framework Mapping — COMPLY-05 link #3 (927-theme-framework-mapping, ADP-1ox).

One new table, `theme_framework_links`, tagging a reusable `StrategicTheme` against one or more
`RegulatoryFramework`s (coarse portfolio grouping — see docs/speckit-compliance-bundle_1.md's COMPLY-05
section, and specs/927-theme-framework-mapping/). Deliberately the simplest possible shape: a bare
composite-PK join table with `ON DELETE CASCADE` on both legs, no status/evidence payload of its own,
mirroring `objective_control_links`'s exact precedent (migration 034) one level up.

Revision ID: 037
Revises: 036
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "theme_framework_links",
        sa.Column(
            "theme_id",
            sa.String(36),
            sa.ForeignKey("strategic_themes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "framework_id",
            sa.String(36),
            sa.ForeignKey("regulatory_frameworks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Indexes the reverse-lookup direction (given a framework, which themes) — mirrors
    # objective_control_links' own ix_ocl_control_id, the identical-purpose index on the
    # non-leading composite-PK column.
    op.create_index("ix_tfl_framework_id", "theme_framework_links", ["framework_id"])


def downgrade() -> None:
    op.drop_index("ix_tfl_framework_id", table_name="theme_framework_links")
    op.drop_table("theme_framework_links")
