"""Agent traceability: automates links and agent compliance mappings.

944-agent-traceability (ADP-12x, Agentic P3). Four new tables, nothing altered:
- agent_capability_links / agent_stage_links / agent_activity_links: an agent "automates" a
  business L3 capability, a value stream stage or a value chain activity (the L3 rule is enforced
  in adp.agentic.store -- an FK can't check the far row's level);
- control_agent_mapping: the sixth COMPLY-02 mapping target (033's shape).

The FKs exist only here; the SQLAlchemy metadata declares plain columns because the targets live
on other packages' metadata (940's owning_org_unit_id precedent). The agentic risk band and an
agent's compliance status are derived on read and never stored.

Revision ID: 052
Revises: 051
Create Date: 2026-11-16
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "052"
down_revision: Union[str, None] = "051"
branch_labels = None
depends_on = None

_STATUS_VALUES = "'compliant','partial','non_compliant','not_assessed','not_applicable'"

# (table, target column, target table)
_LINKS = (
    ("agent_capability_links", "capability_id", "business_capabilities"),
    ("agent_stage_links", "stage_id", "value_stream_stages"),
    ("agent_activity_links", "activity_id", "value_chain_activities"),
)


def _fk(name: str, target: str) -> sa.Column:
    return sa.Column(
        name, sa.String(36), sa.ForeignKey(f"{target}.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    for table, col, target in _LINKS:
        op.create_table(
            table,
            _fk("agent_id", "agents"),
            _fk(col, target),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("agent_id", col),
        )
        op.create_index(f"ix_{table}_{col}", table, [col])

    op.create_table(
        "control_agent_mapping",
        _fk("control_id", "controls"),
        _fk("agent_id", "agents"),
        sa.Column("compliance_status", sa.Text(), nullable=False, server_default="not_assessed"),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.Date(), nullable=True),
        sa.Column("assessed_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("control_id", "agent_id"),
        sa.CheckConstraint(
            f"compliance_status IN ({_STATUS_VALUES})", name="ck_control_agent_mapping_status"
        ),
    )
    op.create_index("ix_control_agent_mapping_agent_id", "control_agent_mapping", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_control_agent_mapping_agent_id", table_name="control_agent_mapping")
    op.drop_table("control_agent_mapping")
    for table, col, _target in reversed(_LINKS):
        op.drop_index(f"ix_{table}_{col}", table_name=table)
        op.drop_table(table)
