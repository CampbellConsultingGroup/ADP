"""ADP-d8u.5: Objective progress tracking, lifecycle status, and theme lifecycle completion.

Adds strategic_objective_progress (new table, one dated entry per objective,
editable in place -- research.md Decision 3, no surrogate id needed since the
composite PK (objective_id, as_of_date) is already the natural URL key for
both the create-conflict check and the edit). Adds status/status_reason to
strategic_objectives -- status is nullable TEXT restricted to NULL or
'abandoned' by CHECK (research.md Decision 2): the three other logical states
(proposed/active/at_risk/achieved) are never persisted, always computed on
read from this table plus the objective's existing target/direction (ART-II).
Adds description/owner/priority to strategic_themes (already a first-class
entity since migration 025 -- not created here, only extended; research.md's
own corrected premise). priority follows the strategic_relevance/
maturity_level SmallInteger+CHECK precedent (020/021), not direction/period's
semantic-text one. owner and recorded_by are plain TEXT, matching every other
"who did this" field in this codebase (strategic_objectives.owner,
AuditEntry.actor, element_technology_tags.owner_team) -- there is no `users`
table anywhere to FK against.

Revision ID: 026
Revises: 025
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # strategic_objective_progress -- one dated, editable entry per objective
    # (research.md Decision 3: composite PK is the natural URL key, no
    # surrogate id needed for either the create-conflict check or the edit).
    op.create_table(
        "strategic_objective_progress",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("as_of_date", sa.Date(), primary_key=True),
        sa.Column("actual_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # strategic_themes -- already a first-class entity since migration 025;
    # this only extends it (research.md's corrected premise, plan.md Ground-
    # Truth Correction 1). owner is plain TEXT, matching every other
    # "who did this" field in this codebase -- there is no users table.
    op.add_column("strategic_themes", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("strategic_themes", sa.Column("owner", sa.Text(), nullable=True))
    op.add_column("strategic_themes", sa.Column("priority", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_strategic_theme_priority",
        "strategic_themes",
        "priority IS NULL OR priority BETWEEN 1 AND 5",
    )

    # strategic_objectives.status -- nullable, restricted to NULL or
    # 'abandoned' (research.md Decision 2): the other three logical states
    # are never persisted, always computed on read (ART-II).
    op.add_column("strategic_objectives", sa.Column("status", sa.Text(), nullable=True))
    op.add_column("strategic_objectives", sa.Column("status_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_strategic_obj_status",
        "strategic_objectives",
        "status IS NULL OR status = 'abandoned'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_strategic_obj_status", "strategic_objectives", type_="check")
    op.drop_column("strategic_objectives", "status_reason")
    op.drop_column("strategic_objectives", "status")

    op.drop_constraint("ck_strategic_theme_priority", "strategic_themes", type_="check")
    op.drop_column("strategic_themes", "priority")
    op.drop_column("strategic_themes", "owner")
    op.drop_column("strategic_themes", "description")

    op.drop_table("strategic_objective_progress")
