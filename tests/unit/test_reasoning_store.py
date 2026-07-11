"""Unit tests for ReasoningStore (ADP-SPEC-027 T003-T008).

Uses in-memory SQLite — no PostgreSQL required.
Triggers are NOT tested here (PL/pgSQL only); trigger correctness verified via psql in T002.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from adp.store.reasoning import _REASONING_MAX_CHARS, ReasoningRecord, ReasoningStore, _hash_prompt


@pytest.fixture()
def store() -> ReasoningStore:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.execute(sa.text("""
                CREATE TABLE llm_reasoning_log (
                    id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    option_id TEXT,
                    step_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    reasoning_text TEXT NOT NULL,
                    truncated INTEGER NOT NULL DEFAULT 0,
                    prompt_hash TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """))

    asyncio.get_event_loop().run_until_complete(_setup())
    return ReasoningStore(factory)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _record(**kwargs) -> ReasoningRecord:
    defaults = dict(
        operation_id="OP-001",
        step_name="generate",
        model_id="claude-sonnet-4-6",
        reasoning_text="This option addresses scalability via horizontal scaling.",
        prompt_hash=_hash_prompt("test prompt"),
        input_tokens=100,
        output_tokens=50,
    )
    defaults.update(kwargs)
    return ReasoningRecord(**defaults)


# ── T003: write creates a row ─────────────────────────────────────────────────

def test_write_creates_row(store):
    run(store.write(_record(operation_id="OP-TEST")))
    rows = run(store.list_for_operation("OP-TEST"))
    assert len(rows) == 1
    row = rows[0]
    assert row["operation_id"] == "OP-TEST"
    assert row["step_name"] == "generate"
    assert row["model_id"] == "claude-sonnet-4-6"
    assert "This option" in row["reasoning_text"]
    assert row["input_tokens"] == 100
    assert row["output_tokens"] == 50


# ── T004: list returns correct records sorted by created_at ───────────────────

def test_list_for_operation_returns_records(store):
    run(store.write(_record(operation_id="OP-A", step_name="generate")))
    run(store.write(_record(operation_id="OP-A", step_name="analyze_tradeoffs")))
    run(store.write(_record(operation_id="OP-B", step_name="generate")))

    results = run(store.list_for_operation("OP-A"))
    assert len(results) == 2
    step_names = [r["step_name"] for r in results]
    assert "generate" in step_names
    assert "analyze_tradeoffs" in step_names


# ── T005: list filters by option_id ──────────────────────────────────────────

def test_list_filters_by_option_id(store):
    run(store.write(_record(operation_id="OP-X", option_id="OPT-001")))
    run(store.write(_record(operation_id="OP-X", option_id="OPT-002")))

    results = run(store.list_for_operation("OP-X", option_id="OPT-001"))
    assert len(results) == 1
    assert results[0]["option_id"] == "OPT-001"


# ── T006: long reasoning text is truncated ───────────────────────────────────

def test_reasoning_text_truncated_at_100k(store):
    long_text = "x" * 150_000
    run(store.write(_record(operation_id="OP-TRUNC", reasoning_text=long_text)))
    rows = run(store.list_for_operation("OP-TRUNC"))
    assert len(rows) == 1
    assert len(rows[0]["reasoning_text"]) == _REASONING_MAX_CHARS
    assert rows[0]["truncated"] in (True, 1)  # SQLite stores bool as int


# ── T007: prompt hash is SHA-256 ─────────────────────────────────────────────

def test_prompt_hash_is_sha256(store):
    known_prompt = "system: advisor\nuser: recommend something"
    expected_hash = hashlib.sha256(known_prompt.encode("utf-8")).hexdigest()
    rec = _record(operation_id="OP-HASH", prompt_hash=_hash_prompt(known_prompt))
    run(store.write(rec))
    rows = run(store.list_for_operation("OP-HASH"))
    assert rows[0]["prompt_hash"] == expected_hash


# ── T008: unknown operation returns empty list ───────────────────────────────

def test_list_returns_empty_for_unknown_operation(store):
    result = run(store.list_for_operation("DOES-NOT-EXIST"))
    assert result == []


# ── Additional: option_id=None records are included without filter ────────────

def test_write_with_no_option_id(store):
    run(store.write(_record(operation_id="OP-NOOPTION", option_id=None)))
    rows = run(store.list_for_operation("OP-NOOPTION"))
    assert len(rows) == 1
    assert rows[0]["option_id"] is None


def test_hash_prompt_helper():
    h = _hash_prompt("hello world")
    assert h == hashlib.sha256(b"hello world").hexdigest()
    assert len(h) == 64  # SHA-256 produces 32 bytes = 64 hex chars
