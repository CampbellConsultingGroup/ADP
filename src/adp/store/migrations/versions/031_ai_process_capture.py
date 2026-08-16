"""AI process capture: durable, design-linked history of Intake, Recommendation,
and Validation (LLM-as-Judge) pipeline activity, for later reporting/visualization.

Six new tables:
  - intake_submissions / intake_proposals
  - recommendation_runs / recommendation_options
  - validation_verdicts / validation_findings

Plus one additive column: llm_reasoning_log.design_id (nullable — the table's
existing triggers, migration 004, forbid UPDATE, so historical rows cannot be
backfilled; this also fixes governance.py's /status endpoint, which today joins
operations -> llm_reasoning_log by operation_id and silently loses reasoning
counts once the 24h operations TTL purges the row).

Deliberate deviation from llm_reasoning_log/audit_entries: these six tables are
NOT trigger-enforced append-only. They carry mutable decision columns (status
pending -> confirmed/accepted/rejected, decided_by, decided_at, decision_reason)
that require UPDATE after the row is created. They follow migration 023's
convention-only append pattern instead: application code never issues DELETE,
and only the decision columns are ever updated post-insert.

design_id columns carry no FK to designs.id (designs.id is TEXT, 'DSN-NNN'
values, not a UUID) -- same loose-coupling convention operations.design_id
already uses, per CLAUDE.md.

Revision ID: 031
Revises: 030
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── intake_submissions ─────────────────────────────────────────────────
    op.create_table(
        "intake_submissions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_truncated", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("business_problem", sa.Text(), nullable=True),
        sa.Column("desired_outcome", sa.Text(), nullable=True),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_intake_submissions_mode",
        "intake_submissions",
        "mode IN ('bulk_text', 'structured_form')",
    )
    op.create_index(
        "ix_intake_submissions_design",
        "intake_submissions",
        ["design_id", "submitted_at"],
    )
    op.create_index(
        "ix_intake_submissions_operation",
        "intake_submissions",
        ["operation_id"],
    )

    # ── intake_proposals ───────────────────────────────────────────────────
    op.create_table(
        "intake_proposals",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "submission_id", sa.Text(),
            sa.ForeignKey("intake_submissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("draft_statement", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=False, server_default=""),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("proposed_links", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("confirmed_statement", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requirement_id", sa.Text(), nullable=True),
        sa.Column("audit_entry_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_intake_proposals_kind",
        "intake_proposals",
        "kind IN ('functional', 'non_functional', 'constraint', 'driver')",
    )
    op.create_check_constraint(
        "ck_intake_proposals_verification_status",
        "intake_proposals",
        "verification_status IN ('verified', 'unverified')",
    )
    op.create_check_constraint(
        "ck_intake_proposals_status",
        "intake_proposals",
        "status IN ('pending', 'confirmed', 'edited_confirmed', 'rejected', 'expired')",
    )
    op.create_index(
        "ix_intake_proposals_design",
        "intake_proposals",
        ["design_id", "created_at"],
    )
    op.create_index(
        "ix_intake_proposals_submission",
        "intake_proposals",
        ["submission_id"],
    )
    op.create_index(
        "ix_intake_proposals_operation",
        "intake_proposals",
        ["operation_id"],
    )

    # ── recommendation_runs ────────────────────────────────────────────────
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("requirement_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("option_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citations_present", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_description", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_recommendation_runs_status",
        "recommendation_runs",
        "status IN ('pending', 'running', 'completed', 'failed')",
    )
    op.create_index(
        "ix_recommendation_runs_design",
        "recommendation_runs",
        ["design_id", "started_at"],
    )

    # ── recommendation_options ─────────────────────────────────────────────
    op.create_table(
        "recommendation_options",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "run_id", sa.Text(),
            sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("advisory", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("grounded_on", JSONB(), nullable=False, server_default="[]"),
        sa.Column("satisfies", JSONB(), nullable=False, server_default="[]"),
        sa.Column("trade_offs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("proposed_elements", JSONB(), nullable=False, server_default="[]"),
        sa.Column("reuse_candidates", JSONB(), nullable=False, server_default="[]"),
        sa.Column("ranking_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("coverage_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("principle_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tradeoff_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("history_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("knowledge_source", sa.Text(), nullable=False, server_default="knowledge_base"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("confirmation_id", sa.Text(), nullable=True),
        sa.Column("advisory_acknowledged", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("audit_entry_id", sa.Text(), nullable=True),
        sa.Column("created_element_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_recommendation_options_status",
        "recommendation_options",
        "status IN ('pending', 'accepted', 'rejected')",
    )
    op.create_index(
        "ix_recommendation_options_run",
        "recommendation_options",
        ["run_id"],
    )
    op.create_index(
        "ix_recommendation_options_design",
        "recommendation_options",
        ["design_id", "created_at"],
    )
    op.create_index(
        "ix_recommendation_options_status",
        "recommendation_options",
        ["design_id", "status"],
    )

    # ── validation_verdicts ────────────────────────────────────────────────
    op.create_table(
        "validation_verdicts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("design_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("citations_present", sa.Boolean(), nullable=False, server_default="FALSE"),
        sa.Column("thresholds_snapshot", JSONB(), nullable=False, server_default="{}"),
        sa.Column("critic_outputs", JSONB(), nullable=False, server_default="[]"),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking_finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overridden_by", sa.Text(), nullable=True),
        sa.Column("override_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_justification", sa.Text(), nullable=True),
        sa.Column("audit_entry_id", sa.Text(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operation_id", name="uq_validation_verdicts_operation"),
    )
    op.create_check_constraint(
        "ck_validation_verdicts_status",
        "validation_verdicts",
        "status IN ('pass', 'fail', 'indeterminate', 'overridden')",
    )
    op.create_index(
        "ix_validation_verdicts_design",
        "validation_verdicts",
        ["design_id", "created_at"],
    )

    # ── validation_findings ────────────────────────────────────────────────
    op.create_table(
        "validation_findings",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column(
            "verdict_id", sa.Text(),
            sa.ForeignKey("validation_verdicts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("design_id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("critic_name", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("element_id", sa.Text(), nullable=True),
        sa.Column("citation_item_id", sa.Text(), nullable=True),
        sa.Column("citation_item_version", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_validation_findings_severity",
        "validation_findings",
        "severity IN ('critical', 'major', 'minor', 'advisory')",
    )
    op.create_index(
        "ix_validation_findings_verdict",
        "validation_findings",
        ["verdict_id"],
    )
    op.create_index(
        "ix_validation_findings_design_severity",
        "validation_findings",
        ["design_id", "severity"],
    )

    # ── llm_reasoning_log.design_id (additive; no backfill, table is append-only) ──
    op.add_column("llm_reasoning_log", sa.Column("design_id", sa.Text(), nullable=True))
    op.create_index(
        "ix_reasoning_design",
        "llm_reasoning_log",
        ["design_id"],
        postgresql_where=sa.text("design_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_reasoning_design", table_name="llm_reasoning_log")
    op.drop_column("llm_reasoning_log", "design_id")

    op.drop_index("ix_validation_findings_design_severity", table_name="validation_findings")
    op.drop_index("ix_validation_findings_verdict", table_name="validation_findings")
    op.drop_table("validation_findings")

    op.drop_index("ix_validation_verdicts_design", table_name="validation_verdicts")
    op.drop_table("validation_verdicts")

    op.drop_index("ix_recommendation_options_status", table_name="recommendation_options")
    op.drop_index("ix_recommendation_options_design", table_name="recommendation_options")
    op.drop_index("ix_recommendation_options_run", table_name="recommendation_options")
    op.drop_table("recommendation_options")

    op.drop_index("ix_recommendation_runs_design", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")

    op.drop_index("ix_intake_proposals_operation", table_name="intake_proposals")
    op.drop_index("ix_intake_proposals_submission", table_name="intake_proposals")
    op.drop_index("ix_intake_proposals_design", table_name="intake_proposals")
    op.drop_table("intake_proposals")

    op.drop_index("ix_intake_submissions_operation", table_name="intake_submissions")
    op.drop_index("ix_intake_submissions_design", table_name="intake_submissions")
    op.drop_table("intake_submissions")
