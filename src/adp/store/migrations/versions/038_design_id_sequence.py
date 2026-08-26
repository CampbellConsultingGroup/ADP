"""Design ID sequence -- structural fix for next_design_id() races (ADP-3fh, follow-up to ADP-twl).

Replaces the "SELECT max(DSN-NNN) + 1, then INSERT elsewhere" scan DesignStore.next_design_id()
always used -- confirmed reproducible under real concurrent load (a handful of concurrent
POST /api/v1/designs collide reliably; 8-10 simultaneous requests can exhaust create_design()'s
5-attempt retry loop, added in ADP-twl, and surface a 503) -- with a real Postgres SEQUENCE.
nextval() is atomic and lock-free by construction: this removes the race structurally instead of
retrying around it. ADP-twl's retry loop in create_design() (src/adp/api/routers/designs.py) is
left in place as harmless defense-in-depth; it should simply never trigger for this cause again.

Seeded to start one past the current max numeric DSN-NNN id already in the table, so it never
collides with an existing row. Named, non-numeric seed ids (DSN-CHECKOUT, DSN-OMS, DSN-POS, etc. --
scripts/seed_retail.py) never matched next_design_id()'s own ^DSN-(\\d+)$ pattern, so they don't
participate in this scheme either way -- confirmed via a direct grep that nothing in this codebase
inserts a numeric DSN-NNN id outside next_design_id() itself.

Revision ID: 038
Revises: 037
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE design_id_seq")
    # setval(..., is_called=false) means the *next* nextval() call returns this value exactly
    # (not value + 1) -- so seeding to max+1 here means the first id issued post-migration is
    # correctly max+1, matching next_design_id()'s own prior "max_n + 1" semantics exactly.
    op.execute(
        """
        SELECT setval(
            'design_id_seq',
            COALESCE(
                (SELECT MAX((substring(id from 5))::int) FROM designs WHERE id ~ '^DSN-[0-9]+$'),
                0
            ) + 1,
            false
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE design_id_seq")
