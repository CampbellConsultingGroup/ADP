"""Mapping rationale on application capability realizations.

943-mapping-rationale (ADP-55k.4, spec 4 of epic ADP-55k). Each realization (application
capability L3 <-> application) gains an optional rationale -- target / tactical / transitional /
redundant, NULL = unclassified -- and an optional geography (a region or country, NULL =
everywhere). Existing rows stay NULL/NULL; nothing is back-filled. Overlap status is derived on
read and never stored.

The FK to geographies exists only here; the SQLAlchemy metadata declares a plain column because
geographies live on the organization metadata (940's owning_org_unit_id precedent).

Revision ID: 051
Revises: 050
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels = None
depends_on = None

_TABLE = "app_capability_realizations"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("rationale", sa.Text(), nullable=True))
    op.add_column(_TABLE, sa.Column("geography_id", sa.String(36), nullable=True))
    op.create_check_constraint(
        "ck_app_cap_realization_rationale",
        _TABLE,
        "rationale IN ('target', 'tactical', 'transitional', 'redundant')",
    )
    op.create_foreign_key(
        "fk_app_cap_realization_geography",
        _TABLE,
        "geographies",
        ["geography_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_app_cap_realizations_geography_id", _TABLE, ["geography_id"])


def downgrade() -> None:
    op.drop_index("ix_app_cap_realizations_geography_id", table_name=_TABLE)
    op.drop_constraint("fk_app_cap_realization_geography", _TABLE, type_="foreignkey")
    op.drop_constraint("ck_app_cap_realization_rationale", _TABLE, type_="check")
    op.drop_column(_TABLE, "geography_id")
    op.drop_column(_TABLE, "rationale")
