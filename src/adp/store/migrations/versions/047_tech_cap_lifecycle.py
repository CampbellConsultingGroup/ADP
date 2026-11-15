"""Technical capability lifecycle: status and optional end-of-life date.

938-capability-model-analysis (ADP-6et.2, FR-001). Impact analysis and technology exposure start
from these. Existing rows become 'current' with no date. Everything the analysis computes from
them (effective lifecycle band, exposure, impact) is derived on read and never stored.

Revision ID: 047
Revises: 046
Create Date: 2026-11-15
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels = None
depends_on = None

_CHECK = "ck_tech_cap_lifecycle_status"


def upgrade() -> None:
    op.add_column(
        "technical_capabilities",
        sa.Column("lifecycle_status", sa.Text(), nullable=False, server_default="current"),
    )
    op.add_column("technical_capabilities", sa.Column("end_of_life_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        _CHECK,
        "technical_capabilities",
        "lifecycle_status IN ('emerging', 'current', 'contained', 'retiring', 'retired')",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK, "technical_capabilities", type_="check")
    op.drop_column("technical_capabilities", "end_of_life_date")
    op.drop_column("technical_capabilities", "lifecycle_status")
