"""Application capabilities: the middle layer between business and technical capabilities.

937-application-capabilities (ADP-6et.1). A shared L1-L3 catalog of application capabilities,
plus three many-to-many link tables. Level rules (business L3 <-> application L3, application L3
-> technical L2/L3, only L3s are realized by applications) are enforced in the store, because a
foreign key can't constrain the referenced row's level.

Revision ID: 046
Revises: 045
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels = None
depends_on = None


def _fk(name: str, target: str) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "application_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # No cascade: the store refuses to delete a capability that has children.
        sa.Column(
            "parent_id",
            sa.String(36),
            sa.ForeignKey("application_capabilities.id"),
            nullable=True,
        ),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 3", name="ck_application_capabilities_level"),
    )
    # Sibling names are unique, case-insensitive. COALESCE makes L1 roots (NULL parent) collide
    # too, since a plain unique constraint treats NULLs as distinct.
    op.execute(
        "CREATE UNIQUE INDEX uq_app_cap_sibling_name ON application_capabilities "
        "(COALESCE(parent_id, ''), lower(name))"
    )

    op.create_table(
        "business_capability_app_capability_links",
        _fk("business_capability_id", "business_capabilities.id"),
        _fk("app_capability_id", "application_capabilities.id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("business_capability_id", "app_capability_id"),
    )
    op.create_index(
        "ix_bcacl_app_capability_id",
        "business_capability_app_capability_links",
        ["app_capability_id"],
    )

    op.create_table(
        "app_capability_tech_cap_links",
        _fk("app_capability_id", "application_capabilities.id"),
        _fk("tech_cap_id", "technical_capabilities.id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("app_capability_id", "tech_cap_id"),
    )
    op.create_index("ix_actcl_tech_cap_id", "app_capability_tech_cap_links", ["tech_cap_id"])

    op.create_table(
        "app_capability_realizations",
        _fk("app_capability_id", "application_capabilities.id"),
        _fk("app_id", "applications.id"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("app_capability_id", "app_id"),
    )
    op.create_index("ix_acr_app_id", "app_capability_realizations", ["app_id"])


def downgrade() -> None:
    op.drop_index("ix_acr_app_id", table_name="app_capability_realizations")
    op.drop_table("app_capability_realizations")
    op.drop_index("ix_actcl_tech_cap_id", table_name="app_capability_tech_cap_links")
    op.drop_table("app_capability_tech_cap_links")
    op.drop_index(
        "ix_bcacl_app_capability_id", table_name="business_capability_app_capability_links"
    )
    op.drop_table("business_capability_app_capability_links")
    op.execute("DROP INDEX IF EXISTS uq_app_cap_sibling_name")
    op.drop_table("application_capabilities")
