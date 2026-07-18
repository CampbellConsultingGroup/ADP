"""ADP-4ga: business capability maturity assessment (1-5 CMMI-style ladder).

Adds maturity_level to business_capabilities only (the ladder is
business-process oriented; technical_capabilities maturity is an open
question, not addressed here). NULL = not yet assessed (distinct from L1
Ad hoc, which is an active assessment). Distinct axis from the existing
'level' column (1-3 hierarchy depth) and from strategic_relevance (1-3,
ADP-33v, migration 020, both capability tables) -- three separate numeric
axes kept under distinct names.

Revision ID: 021
Revises: 020
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_capabilities",
        sa.Column("maturity_level", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_biz_cap_maturity_level",
        "business_capabilities",
        "maturity_level IS NULL OR maturity_level BETWEEN 1 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_biz_cap_maturity_level", "business_capabilities", type_="check")
    op.drop_column("business_capabilities", "maturity_level")
