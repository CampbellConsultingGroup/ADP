"""ADP-d8u.6: Strategy execution layer -- initiatives and objective dependencies.

Adds three new tables. strategy_initiatives is a new, strategy-level program-
of-work record, deliberately distinct from the existing, unrelated
adp.application.models.TransformationInitiative (a much thinner shape scoped
to application-level transformation tracking -- no naming or scope collision,
confirmed by direct read). owner is plain TEXT, matching every other "who did
this" field in this codebase -- there is no `users` table anywhere to FK
against (same fact established in migration 026). status is a free enum (no
enforced transition sequence, per spec.md's resolved Clarification) --
unlike strategic_objectives.status (026), there is no NULL-means-"derive it"
convention here; status is always a real, manually-set value, default
'planned'.

strategy_initiative_objective_links is the standard many-to-many join-table
shape every prior adp.strategy join table already uses (composite PK,
ON DELETE CASCADE both legs, one index, created_at -- 025/026 precedent).

strategic_objective_dependencies is self-referential on strategic_objectives
-- two separate FK constraints against the same parent table (objective_id,
depends_on_objective_id), each needing a distinct constraint name. The
acyclic invariant on this table is enforced at the application layer (a BFS
reachability check before insert, research.md Decision 2), not by any DB
constraint -- a CHECK can't reason about the transitive closure of a
self-referential table.

Revision ID: 027
Revises: 026
Create Date: 2026-08-13
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_initiatives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_check_constraint(
        "ck_strategy_initiative_status",
        "strategy_initiatives",
        "status IN ('planned', 'in_progress', 'blocked', 'complete', 'cancelled')",
    )

    # strategy_initiative_objective_links -- standard M:M join shape, mirrors
    # strategic_objective_capabilities (025)/strategic_objective_progress (026).
    op.create_table(
        "strategy_initiative_objective_links",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_sio_links_objective_id", "strategy_initiative_objective_links", ["objective_id"]
    )

    # strategic_objective_dependencies -- self-referential on strategic_objectives.
    # Two FK columns to the same parent table; Postgres/SQLAlchemy auto-names each
    # constraint from its own column name, so no explicit ForeignKeyConstraint name
    # is needed (matches business_capabilities.parent_id's existing single-FK
    # self-referential precedent, 007). Acyclic invariant is application-enforced
    # (research.md Decision 2), not a DB constraint -- a CHECK can't reason about
    # the transitive closure of a self-referential table.
    op.create_table(
        "strategic_objective_dependencies",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "depends_on_objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_objective_deps_depends_on",
        "strategic_objective_dependencies",
        ["depends_on_objective_id"],
    )


def downgrade() -> None:
    op.drop_table("strategic_objective_dependencies")
    op.drop_table("strategy_initiative_objective_links")
    op.drop_constraint("ck_strategy_initiative_status", "strategy_initiatives", type_="check")
    op.drop_table("strategy_initiatives")
