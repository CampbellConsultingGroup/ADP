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
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
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


# What this process last saw on disk for each exported file: (digest of the entity data, file
# mtime, file size). ADP-blp.18: every cycle used to read and JSON-parse every existing file to
# decide whether it had changed -- thousands of blocking reads a minute on the event loop for a
# large registry. Now a file whose data digest matches, and which is still the same file on disk
# (same mtime and size), is skipped with a single stat(). Anything else -- first sight after a
# restart, changed data, a file edited or replaced by someone else -- takes the full path below.
_seen: dict[Path, tuple[str, int, int]] = {}


def _digest(data: dict[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _remember(path: Path, digest: str) -> None:
    try:
        stat = path.stat()
    except OSError:
        _seen.pop(path, None)
        return
    _seen[path] = (digest, stat.st_mtime_ns, stat.st_size)


def _write_entity_file(path: Path, data: dict[str, Any], now: datetime) -> None:
    """Stamp `exported_at` and write via `_write_file_atomic` -- unless the
    file already exists with identical content (ignoring `exported_at`), in
    which case do nothing at all, not even touch its mtime."""
    digest = _digest(data)
    seen = _seen.get(path)
    if seen is not None and seen[0] == digest:
        try:
            stat = path.stat()
        except OSError:
            stat = None
        if stat is not None and (stat.st_mtime_ns, stat.st_size) == seen[1:]:
            return
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
        if existing is not None:
            existing.pop("exported_at", None)
            if existing == data:
                _remember(path, digest)
                return
    stamped = {**data, "exported_at": now.isoformat()}
    content = json.dumps(stamped, indent=2, sort_keys=True) + "\n"
    _write_file_atomic(path, content)
    _remember(path, digest)


def _cleanup_orphan_files(dir_path: Path, live_ids: set[str]) -> None:
    """Remove any `<id>.json` file in `dir_path` whose id is no longer live.
    A no-op if `dir_path` doesn't exist."""
    if not dir_path.is_dir():
        return
    for f in dir_path.glob("*.json"):
        if f.stem not in live_ids:
            f.unlink(missing_ok=True)  # another worker may have removed it first
            _seen.pop(f, None)


def _cleanup_orphan_dirs(parent_dir: Path, live_ids: set[str]) -> None:
    """Remove any immediate subdirectory of `parent_dir` whose name (an
    entity id) is no longer live -- used when an entity type has its own
    subdirectory holding a nested tree (e.g. a value stream's stages/), so a
    deleted parent's whole subtree is removed in one step."""
    if not parent_dir.is_dir():
        return
    for d in parent_dir.iterdir():
        if d.is_dir() and d.name not in live_ids:
            shutil.rmtree(d, ignore_errors=True)  # another worker may be removing it too
            for path in [p for p in _seen if d in p.parents]:
                _seen.pop(path, None)


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
            if await _try_cycle_lock(session, reconcile_fn):
                await reconcile_fn(export_root, session)
        await asyncio.sleep(interval_seconds)


async def _try_cycle_lock(session: AsyncSession, reconcile_fn: ReconcileFn) -> bool:
    """True when this worker may run the cycle (ADP-blp.18).

    The API runs several worker processes and each starts every export loop, so each cycle ran
    once per worker against the same directory: doubled work, and two workers cleaning up the
    same orphan files at once. On Postgres a transaction-level advisory lock, keyed by the
    domain, lets one worker run a cycle while any other that arrives during it skips that cycle.
    The lock is released when the cycle's session closes. Other databases (tests) always run.
    """
    try:
        if session.get_bind().dialect.name != "postgresql":
            return True
        module = getattr(reconcile_fn, "__module__", "")
        key = f"adp.export:{module}.{getattr(reconcile_fn, '__qualname__', '')}"
        result = await session.execute(
            sa.text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"), {"key": key}
        )
        return bool(result.scalar())
    except Exception as exc:  # noqa: BLE001 - never let the lock stop the export loop
        logging.getLogger("adp.export").warning(
            "export cycle lock unavailable, running the cycle anyway: %s", exc
        )
        return True


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
