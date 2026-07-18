"""APM US7: ownership & governance (ADP-SPEC-038).

Adds a 1:1 ``application_contracts`` table (cascade-deletes with the
application): vendor contract terms, renewal date, SLA, business sponsor,
IT owner, and decision rights.

Revision ID: 018
Revises: 017
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_contracts",
        sa.Column(
            "app_id",
            sa.String(36),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("contract_terms", sa.Text(), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("sla", sa.Text(), nullable=True),
        sa.Column("business_sponsor", sa.String(255), nullable=True),
        sa.Column("it_owner", sa.String(255), nullable=True),
        sa.Column("decision_rights", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_app_contracts_renewal",
        "application_contracts",
        ["renewal_date"],
        postgresql_where=sa.text("renewal_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_app_contracts_renewal", table_name="application_contracts")
    op.drop_table("application_contracts")
