"""Immutable LLM reasoning store (ADP-SPEC-027).

Writes reasoning records to `llm_reasoning_log` — an append-only table protected by
DB-level triggers that reject UPDATE and DELETE. Records persist beyond the 24h TTL
of the `operations` table, providing a permanent AI decision provenance trail.

Writes are fire-and-forget: callers should wrap in asyncio.create_task() so that
DB latency never blocks pipeline responses.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

_logger = logging.getLogger("adp.store.reasoning")

_REASONING_MAX_CHARS = 100_000

# ── SQLAlchemy table definition (mirrors migration 004) ───────────────────────

_metadata = sa.MetaData()

llm_reasoning_log = sa.Table(
    "llm_reasoning_log",
    _metadata,
    sa.Column("id", sa.Text(), primary_key=True),
    sa.Column("operation_id", sa.Text(), nullable=False),
    sa.Column("option_id", sa.Text(), nullable=True),
    sa.Column("step_name", sa.Text(), nullable=False),
    sa.Column("model_id", sa.Text(), nullable=False),
    sa.Column("reasoning_text", sa.Text(), nullable=False),
    sa.Column("truncated", sa.Boolean(), nullable=False, default=False),
    sa.Column("prompt_hash", sa.Text(), nullable=False),
    sa.Column("input_tokens", sa.Integer(), nullable=False, default=0),
    sa.Column("output_tokens", sa.Integer(), nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


# ── Domain model ──────────────────────────────────────────────────────────────

@dataclass
class ReasoningRecord:
    """Data to write to llm_reasoning_log. id and created_at are DB-generated."""

    operation_id: str
    step_name: str          # 'generate' | 'analyze_tradeoffs' | 'extract'
    model_id: str
    reasoning_text: str
    prompt_hash: str        # SHA-256 hex of the full prompt; never store the raw prompt
    input_tokens: int = 0
    output_tokens: int = 0
    option_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_prompt(prompt: str) -> str:
    """Return the SHA-256 hex digest of the prompt string encoded as UTF-8."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _truncate(text: str) -> tuple[str, bool]:
    """Truncate text to _REASONING_MAX_CHARS. Returns (text, was_truncated)."""
    if len(text) <= _REASONING_MAX_CHARS:
        return text, False
    return text[:_REASONING_MAX_CHARS], True


# ── Store ─────────────────────────────────────────────────────────────────────

class ReasoningStore:
    """Async store for immutable LLM reasoning records."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def write(self, record: ReasoningRecord) -> None:
        """Append one reasoning record. Silently drops on any error."""
        text, truncated = _truncate(record.reasoning_text)
        row_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        try:
            async with self._session_factory() as session:
                await session.execute(
                    llm_reasoning_log.insert().values(
                        id=row_id,
                        operation_id=record.operation_id,
                        option_id=record.option_id,
                        step_name=record.step_name,
                        model_id=record.model_id,
                        reasoning_text=text,
                        truncated=truncated,
                        prompt_hash=record.prompt_hash,
                        input_tokens=record.input_tokens,
                        output_tokens=record.output_tokens,
                        created_at=now,
                    )
                )
                await session.commit()
        except Exception as exc:
            _logger.warning("ReasoningStore.write failed (non-fatal): %s", exc)

    async def list_for_operation(
        self,
        operation_id: str,
        option_id: str | None = None,
    ) -> list[dict]:
        """Return reasoning records for an operation, sorted by created_at asc."""
        q = (
            sa.select(llm_reasoning_log)
            .where(llm_reasoning_log.c.operation_id == operation_id)
            .order_by(llm_reasoning_log.c.created_at.asc())
        )
        if option_id is not None:
            q = q.where(llm_reasoning_log.c.option_id == option_id)

        try:
            async with self._session_factory() as session:
                rows = (await session.execute(q)).mappings().fetchall()
            return [dict(r) for r in rows]
        except Exception as exc:
            _logger.warning("ReasoningStore.list_for_operation failed: %s", exc)
            return []
