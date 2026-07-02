"""Trace ID context variable and logging filter (ADP-SPEC-012 FR-001, FR-002).

QG-10: TraceIdFilter ensures every log record carries a trace_id field.
The ContextVar propagates automatically through asyncio Task boundaries.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Return the current trace ID for this async context."""
    return _TRACE_ID.get()


def set_trace_id(tid: str) -> None:
    """Set the trace ID for this async context."""
    _TRACE_ID.set(tid)


def generate_trace_id() -> str:
    """Generate a new UUID4 hex trace ID."""
    return uuid.uuid4().hex


class TraceIdFilter(logging.Filter):
    """Injects the current trace_id ContextVar value into every log record.

    Install once on the root logger at application startup:
        logging.getLogger().addFilter(TraceIdFilter())

    After installation every log.info/warning/error call from any module
    automatically carries record.trace_id (QG-10).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "no-trace"  # type: ignore[attr-defined]
        return True
