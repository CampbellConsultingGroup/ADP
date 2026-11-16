"""Capability <-> org unit mappings.

941-capability-org-mappings (ADP-55k.2, spec 2 of epic ADP-55k). One table links a business
capability to an org unit with a role: owner (L1/L2, at most one per capability), performer (L3,
optional geography) or contributor (L3). Level rules live in the store (an FK can't check the
far row's level). Effective owner, findings and footprints are derived on read, never stored.

Revision ID: 049
Revises: 048
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capability_org_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_unit_id",
            sa.String(36),
            sa.ForeignKey("org_units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "geography_id",
            sa.String(36),
            sa.ForeignKey("geographies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'performer', 'contributor')", name="ck_cap_org_mapping_role"
        ),
        sa.CheckConstraint(
            "role = 'performer' OR geography_id IS NULL",
            name="ck_cap_org_mapping_geo_performer_only",
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_cap_org_mapping_owner ON capability_org_mappings (capability_id)"
        " WHERE role = 'owner'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_cap_org_mapping ON capability_org_mappings"
        " (capability_id, org_unit_id, role, COALESCE(geography_id, ''))"
    )
    op.create_index("ix_cap_org_mapping_org_unit", "capability_org_mappings", ["org_unit_id"])
    op.create_index("ix_cap_org_mapping_capability", "capability_org_mappings", ["capability_id"])


def downgrade() -> None:
    op.drop_index("ix_cap_org_mapping_capability", table_name="capability_org_mappings")
    op.drop_index("ix_cap_org_mapping_org_unit", table_name="capability_org_mappings")
    op.execute("DROP INDEX IF EXISTS uq_cap_org_mapping")
    op.execute("DROP INDEX IF EXISTS uq_cap_org_mapping_owner")
    op.drop_table("capability_org_mappings")
