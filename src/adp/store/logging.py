"""Structured log helpers for store operations (ART-VI / QG-10).

Content fields (ArchitectureDescription JSON) and credentials are never logged.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Generator

_logger = logging.getLogger("adp.store")


def log_operation(
    operation: str,
    design_id: str,
    *,
    version_num: int | None = None,
    actor: str | None = None,
    duration_ms: float | None = None,
    error: Exception | None = None,
) -> None:
    """Emit a structured JSON log entry for one store operation."""
    record: dict[str, object] = {"operation": operation, "design_id": design_id}
    if version_num is not None:
        record["version_num"] = version_num
    if actor is not None:
        record["actor"] = actor
    if duration_ms is not None:
        record["duration_ms"] = round(duration_ms, 2)
    if error is not None:
        record["error"] = str(error)
        _logger.error(json.dumps(record))
    else:
        record["error"] = None
        _logger.info(json.dumps(record))


@contextmanager
def timed_operation(
    operation: str,
    design_id: str,
    **kwargs: object,
) -> Generator[None, None, None]:
    """Context manager that logs an operation with its duration."""
    start = time.perf_counter()
    error: Exception | None = None
    try:
        yield
    except Exception as exc:
        error = exc
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_operation(operation, design_id, duration_ms=elapsed_ms, error=error, **kwargs)  # type: ignore[arg-type]
