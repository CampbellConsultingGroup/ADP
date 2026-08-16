"""Unit tests for IntakeCaptureStore / RecommendationCaptureStore / ValidationCaptureStore
(ADP-3ei.2).

Uses in-memory SQLite via aiosqlite — no PostgreSQL required. JSON columns are
plain TEXT here (SQLite has no JSONB type); the store always round-trips them
through json.dumps()/json.loads(), matching migration 031's Postgres JSONB
columns functionally.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.store.ai_capture import (
    IntakeCaptureStore,
    OptionRecord,
    ProposalRecord,
    RecommendationCaptureStore,
    RunRecord,
    SubmissionRecord,
    ValidationCaptureStore,
)
from adp.validation.models import (
    CriticOutput,
    Finding,
    FindingSeverity,
    GatingThreshold,
    Verdict,
    VerdictStatus,
)

_SCHEMA = """
CREATE TABLE intake_submissions (
    id TEXT PRIMARY KEY, design_id TEXT NOT NULL, operation_id TEXT NOT NULL,
    mode TEXT NOT NULL, source_text TEXT NOT NULL DEFAULT '',
    source_char_count INTEGER NOT NULL DEFAULT 0,
    source_truncated INTEGER NOT NULL DEFAULT 0,
    business_problem TEXT, desired_outcome TEXT, model_id TEXT,
    submitted_by TEXT NOT NULL, submitted_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE intake_proposals (
    id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, design_id TEXT NOT NULL,
    operation_id TEXT NOT NULL, draft_statement TEXT NOT NULL, kind TEXT NOT NULL,
    source_excerpt TEXT NOT NULL DEFAULT '', verification_status TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0, proposed_links TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending', confirmed_statement TEXT,
    decided_by TEXT, decided_at TEXT, requirement_id TEXT, audit_entry_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE recommendation_runs (
    id TEXT PRIMARY KEY, design_id TEXT NOT NULL, requirement_ids TEXT NOT NULL DEFAULT '[]',
    model_id TEXT, actor TEXT NOT NULL, correlation_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending', option_count INTEGER NOT NULL DEFAULT 0,
    citations_present INTEGER NOT NULL DEFAULT 0, result_summary TEXT, error_description TEXT,
    started_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE recommendation_options (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, design_id TEXT NOT NULL,
    rank INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '',
    advisory INTEGER NOT NULL DEFAULT 0, grounded_on TEXT NOT NULL DEFAULT '[]',
    satisfies TEXT NOT NULL DEFAULT '[]', trade_offs TEXT NOT NULL DEFAULT '[]',
    proposed_elements TEXT NOT NULL DEFAULT '[]', reuse_candidates TEXT NOT NULL DEFAULT '[]',
    ranking_score REAL NOT NULL DEFAULT 0, coverage_score REAL NOT NULL DEFAULT 0,
    principle_score REAL NOT NULL DEFAULT 0, tradeoff_score REAL NOT NULL DEFAULT 0,
    history_score REAL NOT NULL DEFAULT 0, knowledge_source TEXT NOT NULL DEFAULT 'knowledge_base',
    status TEXT NOT NULL DEFAULT 'pending', decided_by TEXT, decided_at TEXT,
    decision_reason TEXT, confirmation_id TEXT, advisory_acknowledged INTEGER NOT NULL DEFAULT 0,
    audit_entry_id TEXT, created_element_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE validation_verdicts (
    id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE, design_id TEXT NOT NULL,
    design_version INTEGER NOT NULL, status TEXT NOT NULL, composite_score REAL,
    citations_present INTEGER NOT NULL DEFAULT 0, thresholds_snapshot TEXT NOT NULL DEFAULT '{}',
    critic_outputs TEXT NOT NULL DEFAULT '[]', model_id TEXT,
    finding_count INTEGER NOT NULL DEFAULT 0, blocking_finding_count INTEGER NOT NULL DEFAULT 0,
    overridden_by TEXT, override_at TEXT, override_justification TEXT, audit_entry_id TEXT,
    actor TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE validation_findings (
    id TEXT PRIMARY KEY, verdict_id TEXT NOT NULL, design_id TEXT NOT NULL,
    operation_id TEXT NOT NULL, critic_name TEXT NOT NULL, severity TEXT NOT NULL,
    description TEXT NOT NULL, element_id TEXT, citation_item_id TEXT,
    citation_item_version TEXT, score REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@pytest.fixture()
def factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _setup():
        async with engine.begin() as conn:
            for stmt in _SCHEMA.strip().split(";"):
                if stmt.strip():
                    await conn.execute(sa.text(stmt))

    asyncio.get_event_loop().run_until_complete(_setup())
    return session_factory


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _now():
    return datetime.now(timezone.utc)


# ── IntakeCaptureStore ────────────────────────────────────────────────────────

def test_record_submission_persists_source_text(factory):
    store = IntakeCaptureStore(factory)
    run(store.record_submission(SubmissionRecord(
        submission_id="SUB-1", design_id="DSN-001", operation_id="OP-1",
        mode="bulk_text", source_text="the full pasted requirements text",
        business_problem="reduce churn", desired_outcome="fewer tickets",
        model_id="claude-sonnet-4-6", submitted_by="alice", submitted_at=_now(),
    )))

    async def _fetch():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT * FROM intake_submissions WHERE id = :id"), {"id": "SUB-1"}
            )).mappings().fetchone()

    row = run(_fetch())
    assert row["source_text"] == "the full pasted requirements text"
    assert row["design_id"] == "DSN-001"
    assert row["model_id"] == "claude-sonnet-4-6"
    assert row["source_truncated"] in (0, False)


def test_record_proposals_and_decision_round_trip(factory):
    intake = IntakeCaptureStore(factory)
    run(intake.record_submission(SubmissionRecord(
        submission_id="SUB-2", design_id="DSN-001", operation_id="OP-2",
        mode="bulk_text", source_text="text", business_problem=None, desired_outcome=None,
        model_id="claude-sonnet-4-6", submitted_by="alice", submitted_at=_now(),
    )))
    run(intake.record_proposals([ProposalRecord(
        proposal_id="PROP-1", submission_id="SUB-2", design_id="DSN-001",
        operation_id="OP-2", draft_statement="System shall do X", kind="functional",
        source_excerpt="do X", verification_status="verified", confidence=0.9,
    )]))

    updated = run(intake.record_decision(
        "PROP-1", status="confirmed", decided_by="bob", decided_at=_now(),
        confirmed_statement="System shall do X (edited)", requirement_id="REQ-001",
        audit_entry_id="AUD-001",
    ))
    assert updated is True

    async def _fetch():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT * FROM intake_proposals WHERE id = :id"), {"id": "PROP-1"}
            )).mappings().fetchone()

    row = run(_fetch())
    assert row["status"] == "confirmed"
    assert row["requirement_id"] == "REQ-001"
    assert row["decided_by"] == "bob"


def test_record_decision_returns_false_when_not_pending(factory):
    intake = IntakeCaptureStore(factory)
    run(intake.record_submission(SubmissionRecord(
        submission_id="SUB-3", design_id="DSN-001", operation_id="OP-3",
        mode="bulk_text", source_text="", business_problem=None, desired_outcome=None,
        model_id=None, submitted_by="alice", submitted_at=_now(),
    )))
    run(intake.record_proposals([ProposalRecord(
        proposal_id="PROP-2", submission_id="SUB-3", design_id="DSN-001",
        operation_id="OP-3", draft_statement="X", kind="functional",
        source_excerpt="", verification_status="unverified", confidence=0.5,
    )]))
    first = run(intake.record_decision(
        "PROP-2", status="rejected", decided_by="bob", decided_at=_now(),
    ))
    second = run(intake.record_decision(
        "PROP-2", status="confirmed", decided_by="carol", decided_at=_now(),
    ))
    assert first is True
    assert second is False


def test_record_submission_truncates_long_source_text(factory):
    from adp.store.ai_capture import _SOURCE_TEXT_MAX_CHARS
    store = IntakeCaptureStore(factory)
    long_text = "x" * (_SOURCE_TEXT_MAX_CHARS + 500)
    run(store.record_submission(SubmissionRecord(
        submission_id="SUB-LONG", design_id="DSN-001", operation_id="OP-1",
        mode="bulk_text", source_text=long_text, business_problem=None,
        desired_outcome=None, model_id=None, submitted_by="alice", submitted_at=_now(),
    )))

    async def _fetch():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT source_text, source_truncated, source_char_count "
                        "FROM intake_submissions WHERE id = :id"), {"id": "SUB-LONG"}
            )).mappings().fetchone()

    row = run(_fetch())
    assert len(row["source_text"]) == _SOURCE_TEXT_MAX_CHARS
    assert row["source_truncated"] in (1, True)
    assert row["source_char_count"] == len(long_text)


# ── RecommendationCaptureStore ───────────────────────────────────────────────

def test_record_run_options_and_accept_decision(factory):
    rec = RecommendationCaptureStore(factory)
    run(rec.record_run(RunRecord(
        run_id="OP-REC-1", design_id="DSN-001", requirement_ids=["REQ-001"],
        model_id="claude-sonnet-4-6", actor="alice", correlation_id="C-1", started_at=_now(),
    )))
    run(rec.record_options([OptionRecord(
        option_id="OPT-1", run_id="OP-REC-1", design_id="DSN-001", rank=1,
        title="Option A", rationale="because", advisory=False, grounded_on=[],
        satisfies=["REQ-001"], trade_offs=[], proposed_elements=[], reuse_candidates=[],
        ranking_score=0.8, coverage_score=0.7, principle_score=0.9, tradeoff_score=0.6,
        history_score=0.5, knowledge_source="knowledge_base",
    )]))
    run(rec.complete_run("OP-REC-1", status="completed", option_count=1, result_summary="1 option"))

    updated = run(rec.record_option_decision(
        "OPT-1", status="accepted", decided_by="bob", decided_at=_now(),
        decision_reason="looks good", confirmation_id="CONF-1",
        created_element_ids=["EL-1", "EL-2"],
    ))
    assert updated is True

    async def _fetch_run():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT * FROM recommendation_runs WHERE id = :id"),
                {"id": "OP-REC-1"},
            )).mappings().fetchone()

    async def _fetch_option():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT * FROM recommendation_options WHERE id = :id"),
                {"id": "OPT-1"},
            )).mappings().fetchone()

    run_row = run(_fetch_run())
    option_row = run(_fetch_option())
    assert run_row["status"] == "completed"
    assert run_row["option_count"] == 1
    assert option_row["status"] == "accepted"
    assert option_row["confirmation_id"] == "CONF-1"


def test_reject_decision_is_durable_and_cannot_double_decide(factory):
    rec = RecommendationCaptureStore(factory)
    run(rec.record_run(RunRecord(
        run_id="OP-REC-2", design_id="DSN-001", requirement_ids=[], model_id=None,
        actor="alice", correlation_id=None, started_at=_now(),
    )))
    run(rec.record_options([OptionRecord(
        option_id="OPT-2", run_id="OP-REC-2", design_id="DSN-001", rank=1, title="B",
        rationale="", advisory=False, grounded_on=[], satisfies=[], trade_offs=[],
        proposed_elements=[], reuse_candidates=[], ranking_score=0, coverage_score=0,
        principle_score=0, tradeoff_score=0, history_score=0, knowledge_source="knowledge_base",
    )]))

    first = run(rec.record_option_decision(
        "OPT-2", status="rejected", decided_by="bob", decided_at=_now(),
        decision_reason="not aligned",
    ))
    second = run(rec.record_option_decision(
        "OPT-2", status="accepted", decided_by="carol", decided_at=_now(),
    ))
    assert first is True
    assert second is False

    async def _fetch():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT status, decision_reason FROM recommendation_options "
                        "WHERE id = :id"),
                {"id": "OPT-2"},
            )).mappings().fetchone()

    row = run(_fetch())
    assert row["status"] == "rejected"
    assert row["decision_reason"] == "not aligned"


# ── ValidationCaptureStore ────────────────────────────────────────────────────

def _verdict(**kwargs) -> Verdict:
    defaults = dict(
        verdict_id="VER-1", operation_id="OP-VAL-1", design_id="DSN-001",
        design_version=3, status=VerdictStatus.FAIL, composite_score=0.4,
        findings=[
            Finding(
                finding_id="FIND-1", operation_id="OP-VAL-1", critic_name="standards",
                severity=FindingSeverity.CRITICAL, description="missing citation",
                element_id="EL-1", citation=None, score=0.1,
            ),
        ],
        thresholds_snapshot=GatingThreshold(),
        critic_outputs=[
            CriticOutput(critic_name="standards", score=0.4, input_tokens=100, output_tokens=50),
        ],
        citations_present=False,
    )
    defaults.update(kwargs)
    return Verdict(**defaults)


def test_record_verdict_writes_verdict_and_findings(factory):
    store = ValidationCaptureStore(factory)
    run(store.record_verdict(
        _verdict(), design_id="DSN-001", actor="alice", model_id="claude-sonnet-4-6",
    ))

    async def _fetch():
        async with factory() as session:
            verdict_row = (await session.execute(
                sa.text("SELECT * FROM validation_verdicts WHERE id = :id"), {"id": "VER-1"}
            )).mappings().fetchone()
            finding_rows = (await session.execute(
                sa.text("SELECT * FROM validation_findings WHERE verdict_id = :id"), {"id": "VER-1"}
            )).mappings().fetchall()
            return verdict_row, finding_rows

    verdict_row, finding_rows = run(_fetch())
    assert verdict_row["status"] == "fail"
    assert verdict_row["finding_count"] == 1
    assert verdict_row["blocking_finding_count"] == 1
    assert len(finding_rows) == 1
    assert finding_rows[0]["severity"] == "critical"


def test_record_override_transitions_fail_to_overridden(factory):
    store = ValidationCaptureStore(factory)
    run(store.record_verdict(_verdict(), design_id="DSN-001", actor="alice", model_id=None))

    updated = run(store.record_override(
        "VER-1", overridden_by="bob", override_at=_now(),
        justification="accepted risk", audit_entry_id="AUD-9",
    ))
    assert updated is True

    async def _fetch():
        async with factory() as session:
            return (await session.execute(
                sa.text("SELECT * FROM validation_verdicts WHERE id = :id"), {"id": "VER-1"}
            )).mappings().fetchone()

    row = run(_fetch())
    assert row["status"] == "overridden"
    assert row["overridden_by"] == "bob"
    assert row["override_justification"] == "accepted risk"


def test_record_override_only_applies_to_fail_status(factory):
    store = ValidationCaptureStore(factory)
    run(store.record_verdict(
        _verdict(status=VerdictStatus.PASS), design_id="DSN-001", actor="alice", model_id=None,
    ))

    updated = run(store.record_override(
        "VER-1", overridden_by="bob", override_at=_now(), justification="n/a", audit_entry_id=None,
    ))
    assert updated is False
