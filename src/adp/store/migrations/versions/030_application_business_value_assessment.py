"""Application business value assessment: structured six-dimension
weighted rubric (docs/application-business-value-assessment-spec.md).

Adds application_business_value_assessment -- same shape as migration 029's
application_health_assessment (one *current* row per (application,
dimension), upserted on re-assessment, no history). The six dimension keys
mirror docs/business_value.md's six rows.

Unlike Health (health_score = MIN of six scores), business_value is a
weighted average of the same six rows, soft-capped by the
evidence_measurability score -- see adp.application.store's
compute_business_value_score() for the pure aggregation function. The
weights and cap table are hardcoded application-layer constants, not
stored data (docs/application-business-value-assessment-spec.md SS5.1 --
an editable-weights UI is a deliberately deferred follow-on, ADP-68z).

applications.business_value itself needs no schema change (already exists,
migration 010) -- same treatment as health_score in migration 029: written
only by the transaction that upserts this table's six rows, never editable
directly via PATCH /applications/{id} once this ships (ApplicationUpdate
drops the field in this same change).

Revision ID: 030
Revises: 029
Create Date: 2026-08-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIMENSIONS = (
    "strategic_alignment",
    "revenue_cost_impact",
    "customer_stakeholder_impact",
    "competitive_differentiation",
    "risk_compliance_contribution",
    "evidence_measurability",
)


def upgrade() -> None:
    op.create_table(
        "application_business_value_assessment",
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("dimension", sa.Text(), primary_key=True),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessed_by", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_business_value_assessment_dimension",
        "application_business_value_assessment",
        "dimension IN ({})".format(", ".join(f"'{d}'" for d in _DIMENSIONS)),
    )
    op.create_check_constraint(
        "ck_business_value_assessment_score",
        "application_business_value_assessment",
        "score >= 1 AND score <= 5",
    )


def downgrade() -> None:
    op.drop_table("application_business_value_assessment")
