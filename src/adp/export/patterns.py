"""Continuous export of current EA pattern versions to YAML files (935-pattern-registry US6).

Writes ``<root>/patterns/<key>@<version>.yaml`` for every ``current`` version, byte-identical to
``GET /api/v1/patterns/{key}/versions/{version}/yaml`` (both are ``to_canonical_yaml`` of the
stored definition), so there is no ``exported_at`` stamp — the shared ``_write_entity_file`` is
for JSON documents and is deliberately not used. Files are rewritten only when their bytes change,
and files for versions that stopped being current are removed (only ``*.yaml`` files; anything
else in the folder is left alone).

Filenames come from the validated key and semver grammar only, never free text (spec GT-7): the
shared ``[A-Za-z0-9_-]`` id rule would reject the dots that pattern keys legitimately contain.

Shares ADP_BUSINESS_ARCH_EXPORT_ROOT / _INTERVAL_SECONDS with the other export domains.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from adp.export import common
from adp.export.common import _write_file_atomic
from adp.patterns import store as pstore
from adp.patterns.parse import to_canonical_yaml
from adp.patterns.registry_models import PatternLifecycle

_logger = logging.getLogger("adp.export.patterns")

_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*){1,4}$")
_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def pattern_filename(key: str, version: str) -> str:
    """``<key>@<version>.yaml``, raising ValueError unless both match the pattern grammars."""
    if not _KEY_RE.match(key) or not _SEMVER_RE.match(version):
        raise ValueError(f"Unsafe pattern key/version for a file path: {key!r}@{version!r}")
    return f"{key}@{version}.yaml"


def _write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    _write_file_atomic(path, content)


async def run_reconciliation_cycle(export_root: Path | str, session: AsyncSession) -> None:
    """One full pass. Failures are logged and swallowed so the background loop keeps going."""
    try:
        v = pstore._versions
        rows = (
            await session.execute(
                sa.select(v.c.pattern_key, v.c.version, v.c.definition).where(
                    v.c.lifecycle == PatternLifecycle.CURRENT.value
                )
            )
        ).all()
        root = Path(export_root) / "patterns"
        live: set[str] = set()
        for row in rows:
            name = pattern_filename(row.pattern_key, row.version)
            live.add(name)
            text = to_canonical_yaml(pstore.definition_from_db(row.definition))
            _write_if_changed(root / name, text)
        if root.is_dir():
            for path in root.glob("*.yaml"):
                if path.name not in live:
                    path.unlink()
    except Exception:
        _logger.warning("patterns_export.cycle_failed", exc_info=True)


def start_background_sync(
    export_root: str | None,
    interval_seconds: float,
    session_factory: Callable[[], Any],
) -> asyncio.Task[None] | None:
    """Start the periodic reconciliation loop; a no-op when ``export_root`` is falsy."""
    return common.start_background_sync(
        export_root,
        interval_seconds,
        session_factory,
        run_reconciliation_cycle,
        logger_name="adp.export.patterns",
    )


async def stop_background_sync(task: asyncio.Task[None] | None) -> None:
    await common.stop_background_sync(task)
