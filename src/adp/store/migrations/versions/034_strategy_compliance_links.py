"""Strategy Domain Linkage — COMPLY-05.

Six new tables linking the Compliance domain (COMPLY-01/02: RegulatoryFramework/Control/
ControlMapping) back to the existing Strategy domain (StrategicObjective/StrategyInitiative):

  - objective_control_links — StrategicObjective <-> Control ("why does this objective exist" — a
    bare link, no compliance_status of its own; mirrors objective_design_links'/
    objective_application_links' exact shape, migration 028)
  - initiative_control_capability_mapping   — StrategyInitiative <-> control_capability_mapping row
  - initiative_control_application_mapping  — StrategyInitiative <-> control_application_mapping row
  - initiative_control_design_mapping       — StrategyInitiative <-> control_design_mapping row
  - initiative_control_pattern_mapping      — StrategyInitiative <-> control_pattern_mapping row
  - initiative_control_organization_mapping — StrategyInitiative <-> control_organization_mapping

The five initiative_control_*_mapping tables are "the remediation loop" (spec.md US1): a
StrategyInitiative linked to a *specific, already-assessed* ControlMapping row (a Control in the
context of one target), not to the abstract Control alone. The bundle's own proposal described this
as one `control_mapping_id` FK, but COMPLY-02 has no such column -- ControlMapping is five separate
physical tables with composite PKs and no synthetic id (research.md D1). Resolved by mirroring
COMPLY-02's own five-parallel-tables shape one level up: each new table carries a **composite**
ForeignKeyConstraint against its corresponding control_*_mapping table's own composite PK (Postgres
supports FK(a, b) REFERENCES t(a, b)), plus a plain single-column FK to strategy_initiatives.id.
ON DELETE CASCADE on every leg of every table -- deleting the underlying ControlMapping row (via
COMPLY-02's existing delete_*_mapping functions) cascades to remove the initiative link with zero
adp.compliance.store code changes.

No new columns on any existing table; no synthetic id column added to any control_*_mapping table
(research.md D1's rejected alternative).

Revision ID: 034
Revises: 033
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ObjectiveControlMapping ──────────────────────────────────────────────
    op.create_table(
        "objective_control_links",
        sa.Column(
            "objective_id",
            sa.String(36),
            sa.ForeignKey("strategic_objectives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ocl_control_id", "objective_control_links", ["control_id"])

    # ── InitiativeControlMapping — five parallel tables, one per ControlMapping
    #    target shape (research.md D1). Each carries a composite FK against the
    #    *composite primary key* of its corresponding control_*_mapping table
    #    (migration 033).
    op.create_table(
        "initiative_control_capability_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("capability_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "capability_id"],
            ["control_capability_mapping.control_id", "control_capability_mapping.capability_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_iccm_mapping", "initiative_control_capability_mapping", ["control_id", "capability_id"]
    )

    op.create_table(
        "initiative_control_application_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "application_id"],
            [
                "control_application_mapping.control_id",
                "control_application_mapping.application_id",
            ],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icam_mapping",
        "initiative_control_application_mapping",
        ["control_id", "application_id"],
    )

    op.create_table(
        "initiative_control_design_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        # TEXT, not String(36) -- matches control_design_mapping.design_id's actual column type
        # (designs.id is a DSN-NNN string, migration 033 / 001_initial_schema.py).
        sa.Column("design_id", sa.Text(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "design_id"],
            ["control_design_mapping.control_id", "control_design_mapping.design_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icdm_mapping", "initiative_control_design_mapping", ["control_id", "design_id"]
    )

    op.create_table(
        "initiative_control_pattern_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        # Unbounded VARCHAR, not String(36) -- matches control_pattern_mapping.pattern_id's actual
        # column type (knowledge_items.id, migration 033 / 002_knowledge_schema.py).
        sa.Column("pattern_id", sa.String(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id", "pattern_id"],
            ["control_pattern_mapping.control_id", "control_pattern_mapping.pattern_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icpm_mapping", "initiative_control_pattern_mapping", ["control_id", "pattern_id"]
    )

    op.create_table(
        "initiative_control_organization_mapping",
        sa.Column(
            "initiative_id",
            sa.String(36),
            sa.ForeignKey("strategy_initiatives.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("control_id", sa.String(36), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["control_organization_mapping.control_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_icom_mapping", "initiative_control_organization_mapping", ["control_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_icom_mapping", table_name="initiative_control_organization_mapping")
    op.drop_table("initiative_control_organization_mapping")
    op.drop_index("ix_icpm_mapping", table_name="initiative_control_pattern_mapping")
    op.drop_table("initiative_control_pattern_mapping")
    op.drop_index("ix_icdm_mapping", table_name="initiative_control_design_mapping")
    op.drop_table("initiative_control_design_mapping")
    op.drop_index("ix_icam_mapping", table_name="initiative_control_application_mapping")
    op.drop_table("initiative_control_application_mapping")
    op.drop_index("ix_iccm_mapping", table_name="initiative_control_capability_mapping")
    op.drop_table("initiative_control_capability_mapping")
    op.drop_index("ix_ocl_control_id", table_name="objective_control_links")
    op.drop_table("objective_control_links")
