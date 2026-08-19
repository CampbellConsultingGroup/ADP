"""Control Mappings (Traceability Links) — COMPLY-02.

Five new tables linking a Control (COMPLY-01) to the entity it governs:
  - control_capability_mapping  — Control <-> business_capabilities
  - control_application_mapping — Control <-> applications
  - control_design_mapping      — Control <-> designs
  - control_pattern_mapping     — Control <-> knowledge_items (kind == 'pattern', app-layer checked)
  - control_organization_mapping — Control's standing, estate-wide assessment; no target leg at all
    (single-column PK on control_id — at most one estate-wide mapping per Control)

Four separate, fully FK-enforced tables rather than one polymorphic table (Clarification Session
2026-08-18; research.md D1) -- consistent with every other cross-entity link in the platform
(application_capability_links, strategic_objective_capabilities, ...): composite PK on the two
FK legs, ON DELETE CASCADE on both. control_organization_mapping has no target leg by
definition, so its PK is just control_id.

Every table shares the same compliance_status/evidence_ref/assessed_at/assessed_by/created_at shape
and a named CHECK constraint restricting compliance_status to the five fixed values (data-model.md).

design_id is sa.Text() (not String(36)) to match designs.id's actual column type
(001_initial_schema.py); pattern_id is sa.String() unbounded to match knowledge_items.id
(002_knowledge_schema.py). Every other FK leg is String(36), matching controls.id/
business_capabilities.id/applications.id.

Revision ID: 033
Revises: 032
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_VALUES = "'compliant','partial','non_compliant','not_assessed','not_applicable'"


def _status_check(name: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"compliance_status IN ({_STATUS_VALUES})", name=name)


def _mapping_columns() -> list[sa.Column]:
    """Shared columns across every mapping table (both entity-targeted and estate-wide)."""
    return [
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    # ── control_capability_mapping ──────────────────────────────────────────
    op.create_table(
        "control_capability_mapping",
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capability_id",
            sa.String(36),
            sa.ForeignKey("business_capabilities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_mapping_columns(),
        sa.PrimaryKeyConstraint("control_id", "capability_id"),
        _status_check("ck_ccm_status"),
    )
    op.create_index("ix_ccm_capability_id", "control_capability_mapping", ["capability_id"])

    # ── control_application_mapping ─────────────────────────────────────────
    op.create_table(
        "control_application_mapping",
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_mapping_columns(),
        sa.PrimaryKeyConstraint("control_id", "application_id"),
        _status_check("ck_cam_status"),
    )
    op.create_index("ix_cam_application_id", "control_application_mapping", ["application_id"])

    # ── control_design_mapping ──────────────────────────────────────────────
    op.create_table(
        "control_design_mapping",
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "design_id",
            sa.Text(),
            sa.ForeignKey("designs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_mapping_columns(),
        sa.PrimaryKeyConstraint("control_id", "design_id"),
        _status_check("ck_cdm_status"),
    )
    op.create_index("ix_cdm_design_id", "control_design_mapping", ["design_id"])

    # ── control_pattern_mapping ─────────────────────────────────────────────
    op.create_table(
        "control_pattern_mapping",
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pattern_id",
            sa.String(),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_mapping_columns(),
        sa.PrimaryKeyConstraint("control_id", "pattern_id"),
        _status_check("ck_cpm_status"),
    )
    op.create_index("ix_cpm_pattern_id", "control_pattern_mapping", ["pattern_id"])

    # ── control_organization_mapping (no target leg; research.md D1/D9) ────
    op.create_table(
        "control_organization_mapping",
        sa.Column(
            "control_id",
            sa.String(36),
            sa.ForeignKey("controls.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        *_mapping_columns(),
        _status_check("ck_com_status"),
    )


def downgrade() -> None:
    op.drop_table("control_organization_mapping")
    op.drop_index("ix_cpm_pattern_id", table_name="control_pattern_mapping")
    op.drop_table("control_pattern_mapping")
    op.drop_index("ix_cdm_design_id", table_name="control_design_mapping")
    op.drop_table("control_design_mapping")
    op.drop_index("ix_cam_application_id", table_name="control_application_mapping")
    op.drop_table("control_application_mapping")
    op.drop_index("ix_ccm_capability_id", table_name="control_capability_mapping")
    op.drop_table("control_capability_mapping")
