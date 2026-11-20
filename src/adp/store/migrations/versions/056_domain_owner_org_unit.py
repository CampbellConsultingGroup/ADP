"""Business domain owner: a link to a division (level-2 org unit).

A business domain recorded its organization as free text (``org_unit``). It now links to the
division that owns it, ``owner_org_unit_id`` (FK to org_units, ON DELETE SET NULL). Existing
free text is matched to a division by name, ignoring case; a match sets the link and clears the
text. Text that matches no division is kept, so nothing is lost; the form asks for a division.

Revision ID: 056
Revises: 055
Create Date: 2026-11-20
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("business_domains", sa.Column("owner_org_unit_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_business_domains_owner_org_unit",
        "business_domains",
        "org_units",
        ["owner_org_unit_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_business_domains_owner_org_unit_id", "business_domains", ["owner_org_unit_id"]
    )
    # Link by exact (case-insensitive) name, only where exactly one division has that name.
    op.execute(
        """
        UPDATE business_domains d
           SET owner_org_unit_id = m.id, org_unit = NULL
          FROM (
                SELECT lower(name) AS lname, min(id) AS id
                  FROM org_units
                 WHERE level = 2
              GROUP BY lower(name)
                HAVING count(*) = 1
               ) m
         WHERE d.org_unit IS NOT NULL
           AND lower(trim(d.org_unit)) = m.lname
        """
    )


def downgrade() -> None:
    # Put a linked division's name back into the free text before dropping the link.
    op.execute(
        """
        UPDATE business_domains d
           SET org_unit = o.name
          FROM org_units o
         WHERE d.owner_org_unit_id = o.id
           AND d.org_unit IS NULL
        """
    )
    op.drop_index("ix_business_domains_owner_org_unit_id", table_name="business_domains")
    op.drop_constraint(
        "fk_business_domains_owner_org_unit", "business_domains", type_="foreignkey"
    )
    op.drop_column("business_domains", "owner_org_unit_id")
