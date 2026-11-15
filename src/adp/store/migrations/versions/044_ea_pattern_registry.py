"""EA pattern registry: families, versions, relations, lifecycle history (ADP-mmm.2, 935).

Adds:
  - ea_pattern: a pattern family (stable dotted key, fixed kind and owner role);
  - ea_pattern_version: one version (semver) holding the canonical definition JSONB and its
    SHA-256 digest; at most one 'current' version per family (partial unique index);
  - ea_pattern_relation: pattern -> pattern edges, rebuilt from the definition. The target key
    deliberately has NO foreign key: drafts may reference families that do not exist yet
    (reported as warnings, blocking only at promotion -- research.md D2);
  - ea_pattern_lifecycle_event: every lifecycle transition with its reason and ART-VIII
    confirmation id.

No principle/control link tables: references are resolved from the stored definition
(research.md D2), and assessed control links already live in control_pattern_mapping (033),
reached through the knowledge projection.

Revision ID: 044
Revises: 043
Create Date: 2026-11-14
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels = None
depends_on = None

_KEY_RE = r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$"
_SEMVER_RE = r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
_KINDS = "('reference-architecture', 'portfolio-rule', 'transition', 'anti-pattern')"
_OWNER_ROLES = (
    "('business', 'enterprise', 'solution', 'technical', 'security', 'infrastructure', 'identity')"
)
_STATES = "('draft', 'proposed', 'current', 'deprecated', 'decommissioned')"
_RELATION_TYPES = (
    "('realizes', 'specializes', 'replaces', 'conflicts_with', 'requires', 'alternative_to')"
)


def upgrade() -> None:
    op.create_table(
        "ea_pattern",
        sa.Column("pattern_key", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("owner_role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint(f"pattern_key ~ '{_KEY_RE}'", name="ck_ea_pattern_key_format"),
        sa.CheckConstraint(f"kind IN {_KINDS}", name="ck_ea_pattern_kind"),
        sa.CheckConstraint(f"owner_role IN {_OWNER_ROLES}", name="ck_ea_pattern_owner_role"),
    )

    op.create_table(
        "ea_pattern_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "pattern_key",
            sa.Text(),
            sa.ForeignKey("ea_pattern.pattern_key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("lifecycle_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_changed_by", sa.Text(), nullable=False),
        sa.UniqueConstraint("pattern_key", "version", name="uq_ea_pattern_version_key_version"),
        sa.CheckConstraint(f"version ~ '{_SEMVER_RE}'", name="ck_ea_pattern_version_semver"),
        sa.CheckConstraint(f"lifecycle IN {_STATES}", name="ck_ea_pattern_version_lifecycle"),
    )
    op.create_index(
        "uq_ea_pattern_version_current",
        "ea_pattern_version",
        ["pattern_key"],
        unique=True,
        postgresql_where=sa.text("lifecycle = 'current'"),
    )
    op.create_index("ix_ea_pattern_version_digest", "ea_pattern_version", ["digest"])
    op.create_index("ix_ea_pattern_version_lifecycle", "ea_pattern_version", ["lifecycle"])

    op.create_table(
        "ea_pattern_relation",
        sa.Column(
            "source_version_id",
            sa.String(36),
            sa.ForeignKey("ea_pattern_version.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("target_pattern_key", sa.Text(), primary_key=True),
        sa.Column("relation_type", sa.Text(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"relation_type IN {_RELATION_TYPES}", name="ck_ea_pattern_relation_type"
        ),
    )
    op.create_index("ix_ea_pattern_relation_target", "ea_pattern_relation", ["target_pattern_key"])

    op.create_table(
        "ea_pattern_lifecycle_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("ea_pattern_version.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("confirmation_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("caused_by_event_id", sa.String(36), nullable=True),
        sa.CheckConstraint(
            f"from_state IN {_STATES} AND to_state IN {_STATES}",
            name="ck_ea_pattern_event_states",
        ),
        sa.CheckConstraint(
            "char_length(reason) BETWEEN 1 AND 500", name="ck_ea_pattern_event_reason_len"
        ),
    )
    op.create_index("ix_ea_pattern_event_version", "ea_pattern_lifecycle_event", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_ea_pattern_event_version", table_name="ea_pattern_lifecycle_event")
    op.drop_table("ea_pattern_lifecycle_event")
    op.drop_index("ix_ea_pattern_relation_target", table_name="ea_pattern_relation")
    op.drop_table("ea_pattern_relation")
    op.drop_index("ix_ea_pattern_version_lifecycle", table_name="ea_pattern_version")
    op.drop_index("ix_ea_pattern_version_digest", table_name="ea_pattern_version")
    op.drop_index("uq_ea_pattern_version_current", table_name="ea_pattern_version")
    op.drop_table("ea_pattern_version")
    op.drop_table("ea_pattern")
