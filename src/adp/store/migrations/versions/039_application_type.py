"""Application type (build-vs-buy classification) for Application Portfolio grouping (ADP-3jj).

Adds application_type (custom/cots/saas/legacy) to the applications table, mirroring migration
016's hosting_model addition line-for-line: nullable TEXT column, CHECK constraint restricting it
to the 4 allowed values, and a filter index. Independent of hosting_model (deployment location,
not build-vs-buy/vendor status) -- see specs/929-application-type-cots/spec.md Edge Cases.

Revision ID: 039
Revises: 038
Create Date: 2026-08-26
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("application_type", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_app_application_type",
        "applications",
        "application_type IS NULL OR application_type IN ('custom', 'cots', 'saas', 'legacy')",
    )
    op.create_index("ix_applications_application_type", "applications", ["application_type"])


def downgrade() -> None:
    op.drop_index("ix_applications_application_type", table_name="applications")
    op.drop_constraint("ck_app_application_type", "applications", type_="check")
    op.drop_column("applications", "application_type")
