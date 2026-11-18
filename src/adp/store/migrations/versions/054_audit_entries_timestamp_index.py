"""Index audit_entries.timestamp (ADP-blp.29).

The Governance activity feed and the audit CSV export filter on a date range of ``timestamp`` and
sort by it. The table was indexed only on (design_id, design_version), so both scanned every row.
No column or constraint changes.

Revision ID: 054
Revises: 053
Create Date: 2026-11-18
"""

from __future__ import annotations

from typing import Union

from alembic import op

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_audit_entries_timestamp", "audit_entries", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_entries_timestamp", table_name="audit_entries")
