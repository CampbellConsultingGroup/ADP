"""Application Regulatory Framework Tags (932-regulatory-framework-tags, ADP-bkg).

Replaces `application_risk.regulatory_tags` (free-text JSON array) with a governed many-to-many
link table, `application_framework_tags`, tagging an `Application` against one or more real
`RegulatoryFramework` records (COMPLY-01). Deliberately the simplest possible shape: a bare
composite-PK join table with `ON DELETE CASCADE` on both legs, no status/evidence payload of its
own -- mirroring `theme_framework_links`'s exact precedent (migration 037) one level up, since this
is an unassessed "applies here" tag, not an assessed `ControlMapping` (research.md D1).

Dropping `application_risk.regulatory_tags` outright (rather than migrating its string values) is
what makes spec.md FR-006 ("discard every application's pre-existing free-text regulatory tag
value") true by construction: the new table starts empty for every application, for every row,
with no backfill/matching logic at all (research.md D6; resolved with the user via
`/speckit.clarify`, Option B).

Revision ID: 041
Revises: 040
Create Date: 2026-10-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_framework_tags",
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
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
    # Indexes the reverse-lookup direction (given a framework, which applications) -- mirrors
    # ix_tfl_framework_id's identical purpose on theme_framework_links. No reverse-lookup endpoint
    # is built in this feature (research.md D7), but the index costs nothing to add now and saves
    # a later migration if/when one is.
    op.create_index("ix_aft_framework_id", "application_framework_tags", ["framework_id"])

    op.drop_column("application_risk", "regulatory_tags")


def downgrade() -> None:
    op.add_column(
        "application_risk",
        sa.Column(
            "regulatory_tags", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.drop_index("ix_aft_framework_id", table_name="application_framework_tags")
    op.drop_table("application_framework_tags")
