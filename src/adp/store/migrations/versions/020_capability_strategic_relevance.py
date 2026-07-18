"""ADP-33v: strategic relevance classification for capabilities.

Adds strategic_relevance (1=Strategic, 2=Core, 3=Supporting) to BOTH
business_capabilities (ADP-SPEC-033/035) and technical_capabilities
(ADP-SPEC-036). Distinct from the existing 'level' column (hierarchy depth,
1-3) on both tables and from the maturity_level column added by ADP-4ga
(migration 021, business_capabilities only, 1-5) -- three separate numeric
axes that must not be confused.

Revision ID: 020
Revises: 019
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_capabilities",
        sa.Column("strategic_relevance", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_biz_cap_strategic_relevance",
        "business_capabilities",
        "strategic_relevance IS NULL OR strategic_relevance BETWEEN 1 AND 3",
    )
    op.add_column(
        "technical_capabilities",
        sa.Column("strategic_relevance", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tech_cap_strategic_relevance",
        "technical_capabilities",
        "strategic_relevance IS NULL OR strategic_relevance BETWEEN 1 AND 3",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tech_cap_strategic_relevance", "technical_capabilities", type_="check")
    op.drop_column("technical_capabilities", "strategic_relevance")
    op.drop_constraint("ck_biz_cap_strategic_relevance", "business_capabilities", type_="check")
    op.drop_column("business_capabilities", "strategic_relevance")
