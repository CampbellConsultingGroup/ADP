"""Shared, domain-agnostic export helpers (ADP-SPEC-045 / ADP-81p.2, research.md
Decision 5).

Extracted from `adp.export.business_arch` (ADP-SPEC-044), which was the first
of what the parent epic (ADP-81p) always anticipated as multiple continuous-
export domains. Everything here is deliberately domain-agnostic: path safety,
atomic file writes, content-diff-aware writes (skip if unchanged), orphan
file/directory cleanup, and the background reconciliation-loop lifecycle.
What to fetch, how to serialize it, and the exported file-tree shape stay in
each domain's own module (e.g. `adp.export.business_arch`,
`adp.export.application_arch`) — only the mechanics below are shared.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

# File/directory names are always derived from an entity's own internal ID,
# never its user-editable name -- defense-in-depth against a crafted name
# being used to construct a path-traversal write (Threat Model, both domains).
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_path_component(entity_id: str) -> str:
    """Validate entity_id is safe to use as a path component (directory or
    filename stem), raising if not."""
    if not _SAFE_ID_RE.match(entity_id):
        raise ValueError(f"Unsafe entity id for a file path: {entity_id!r}")
    return entity_id


def _safe_filename(entity_id: str) -> str:
    """Return f"{entity_id}.json", raising if entity_id isn't a safe path
    component."""
    return f"{_safe_path_component(entity_id)}.json"


def _write_file_atomic(path: Path, content: str) -> None:
    """Write `content` to `path` via temp-file-then-`os.replace` -- a crash or
    failure mid-write never leaves a partially-written file in place of a
    previously-good one. The temp file lives in the SAME directory as `path`
    so the final `os.replace` is a same-filesystem rename (atomic), not a
    cross-filesystem copy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _write_entity_file(path: Path, data: dict[str, Any], now: datetime) -> None:
    """Stamp `exported_at` and write via `_write_file_atomic` -- unless the
    file already exists with identical content (ignoring `exported_at`), in
    which case do nothing at all, not even touch its mtime."""
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None:
            existing.pop("exported_at", None)
            if existing == data:
                return
    stamped = {**data, "exported_at": now.isoformat()}
    content = json.dumps(stamped, indent=2, sort_keys=True) + "\n"
    _write_file_atomic(path, content)


def _cleanup_orphan_files(dir_path: Path, live_ids: set[str]) -> None:
    """Remove any `<id>.json` file in `dir_path` whose id is no longer live.
    A no-op if `dir_path` doesn't exist."""
    if not dir_path.is_dir():
        return
    for f in dir_path.glob("*.json"):
        if f.stem not in live_ids:
            f.unlink()


def _cleanup_orphan_dirs(parent_dir: Path, live_ids: set[str]) -> None:
    """Remove any immediate subdirectory of `parent_dir` whose name (an
    entity id) is no longer live -- used when an entity type has its own
    subdirectory holding a nested tree (e.g. a value stream's stages/), so a
    deleted parent's whole subtree is removed in one step."""
    if not parent_dir.is_dir():
        return
    for d in parent_dir.iterdir():
        if d.is_dir() and d.name not in live_ids:
            shutil.rmtree(d)


# ── Background task lifecycle ─────────────────────────────────────────────────
# No module-level task handle -- the caller (adp.api.app's lifespan) owns the
# returned Task and passes it back to stop_background_sync, so there's no
# shared mutable state to reset between app instances/tests.

ReconcileFn = Callable[[Path, AsyncSession], Awaitable[None]]


async def _background_loop(
    export_root: Path,
    interval_seconds: float,
    session_factory: Callable[[], Any],
    reconcile_fn: ReconcileFn,
) -> None:
    while True:
        async with session_factory() as session:
            await reconcile_fn(export_root, session)
        await asyncio.sleep(interval_seconds)


def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
    reconcile_fn: ReconcileFn,
    *,
    logger_name: str,
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop for one domain. A no-op
    (returns None, starts nothing, writes nothing) when `export_root` is
    falsy -- every domain built on this module is opt-in, never a silent
    default write to some assumed path."""
    if not export_root:
        import logging

        logging.getLogger(logger_name).info(
            "export.disabled (ADP_BUSINESS_ARCH_EXPORT_ROOT not set)"
        )
        return None
    return asyncio.create_task(
        _background_loop(Path(export_root), interval_seconds, session_factory, reconcile_fn)
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    """Cancel and await a background task started by start_background_sync.
    A no-op if `task` is None (the feature was never started)."""
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
