"""Application health assessment: structured six-dimension rubric
(docs/application-health-assessment-spec.md).

Adds application_health_assessment -- one *current* row per (application,
dimension), upserted on re-assessment (no history log, per spec §2). The six
dimension keys mirror docs/health-table.md's six rows exactly.

applications.health_score itself needs no schema change (already exists,
migration 010) -- it becomes a value only ever written by the same
transaction that upserts this table's six rows (adp.application.store's
upsert_health_assessment), never editable directly via
PATCH /applications/{id} once this ships (ApplicationUpdate drops the field
in this same change -- Pydantic's extra="forbid" rejects it, no DB-level
enforcement needed).

Revision ID: 029
Revises: 028
Create Date: 2026-08-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIMENSIONS = (
    "stability_incidents",
    "technical_currency_debt",
    "security_posture",
    "support_team_capacity",
    "documentation_knowledge",
    "business_value_criticality",
)


def upgrade() -> None:
    op.create_table(
        "application_health_assessment",
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
        "ck_health_assessment_dimension",
        "application_health_assessment",
        "dimension IN ({})".format(", ".join(f"'{d}'" for d in _DIMENSIONS)),
    )
    op.create_check_constraint(
        "ck_health_assessment_score",
        "application_health_assessment",
        "score >= 1 AND score <= 5",
    )


def downgrade() -> None:
    op.drop_table("application_health_assessment")
