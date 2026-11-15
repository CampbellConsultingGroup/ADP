"""EA pattern adoptions: a pattern applied to a scope, with members and role pins (ADP-mmm.3, 936).

Adds:
  - ea_pattern_adoption: one pattern family adopted for a business domain, an explicit set of
    applications, or the whole portfolio, optionally pinned to a version (NULL follows the family's
    current version). At most one adoption per pattern per domain, one portfolio adoption per
    pattern, and unique names per pattern (partial unique indexes instead of a COALESCE sentinel);
  - ea_pattern_adoption_member: the applications of an application_set adoption;
  - ea_pattern_adoption_pin: elements pinned to roles. element_id is polymorphic (no FK):
    existence is checked on write, and a pin dangling later surfaces as a B3 finding.

No conformance status, plateau or finding is stored anywhere: they are derived on every read.

Revision ID: 045
Revises: 044
Create Date: 2026-11-14
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels = None
depends_on = None

_SCOPES = "('business_domain', 'application_set', 'portfolio')"
_ELEMENT_TYPES = (
    "('business_capability', 'value_stream', 'business_domain', 'application', 'integration', "
    "'technical_capability', 'agent')"
)


def upgrade() -> None:
    op.create_table(
        "ea_pattern_adoption",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "pattern_key",
            sa.Text(),
            sa.ForeignKey("ea_pattern.pattern_key", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pinned_version_id",
            sa.String(36),
            sa.ForeignKey("ea_pattern_version.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column(
            "scope_ref",
            sa.String(36),
            sa.ForeignKey("business_domains.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"scope_type IN {_SCOPES}", name="ck_ea_pattern_adoption_scope_type"),
        sa.CheckConstraint(
            "(scope_type = 'business_domain') = (scope_ref IS NOT NULL)",
            name="ck_ea_pattern_adoption_scope_ref",
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 120", name="ck_ea_pattern_adoption_name_len"
        ),
    )
    op.create_index(
        "uq_ea_pattern_adoption_domain",
        "ea_pattern_adoption",
        ["pattern_key", "scope_ref"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'business_domain'"),
    )
    op.create_index(
        "uq_ea_pattern_adoption_portfolio",
        "ea_pattern_adoption",
        ["pattern_key"],
        unique=True,
        postgresql_where=sa.text("scope_type = 'portfolio'"),
    )
    op.create_index(
        "uq_ea_pattern_adoption_name", "ea_pattern_adoption", ["pattern_key", "name"], unique=True
    )

    op.create_table(
        "ea_pattern_adoption_member",
        sa.Column(
            "adoption_id",
            sa.String(36),
            sa.ForeignKey("ea_pattern_adoption.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "ea_pattern_adoption_pin",
        sa.Column(
            "adoption_id",
            sa.String(36),
            sa.ForeignKey("ea_pattern_adoption.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role_key", sa.Text(), primary_key=True),
        sa.Column("element_type", sa.Text(), primary_key=True),
        sa.Column("element_id", sa.Text(), primary_key=True),
        sa.CheckConstraint(
            f"element_type IN {_ELEMENT_TYPES}", name="ck_ea_pattern_adoption_pin_type"
        ),
    )


def downgrade() -> None:
    op.drop_table("ea_pattern_adoption_pin")
    op.drop_table("ea_pattern_adoption_member")
    op.drop_index("uq_ea_pattern_adoption_name", table_name="ea_pattern_adoption")
    op.drop_index("uq_ea_pattern_adoption_portfolio", table_name="ea_pattern_adoption")
    op.drop_index("uq_ea_pattern_adoption_domain", table_name="ea_pattern_adoption")
    op.drop_table("ea_pattern_adoption")
