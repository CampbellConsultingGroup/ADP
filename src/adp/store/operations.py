"""Persistent operation store — replaces in-process dicts (ADP-SPEC-024).

Operations (intake extractions and recommendation runs) are stored in PostgreSQL
so they survive process restarts and can be shared across multiple uvicorn workers.

Each operation row has:
  - Standard DB columns: id, type, design_id, status, actor, error, timestamps
  - payload (JSONB/TEXT): operation-type-specific data (proposals, options, etc.)

OperationStore.get() returns a flat dict merging row columns + payload contents,
matching the interface of the old in-process dicts so router code needs minimal changes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa

logger = logging.getLogger(__name__)

_TTL_HOURS = 24


def _load_payload(raw: Any) -> dict:
    """Deserialize an operation payload regardless of whether the DB returned a
    string (SQLite TEXT) or a dict (PostgreSQL JSONB auto-deserialized by asyncpg)."""
    if isinstance(raw, dict):
        return raw
    return json.loads(raw or "{}")


def _dump_payload(payload: dict) -> Any:
    """Serialize a payload for storage. asyncpg accepts both str and dict for JSONB,
    but we use json.dumps for cross-DB compatibility (SQLite needs a string)."""
    return json.dumps(payload)


class OperationStore:
    """Async PostgreSQL-backed store for transient pipeline operations."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        op_id: str,
        op_type: str,
        design_id: str,
        actor: str,
        initial_payload: dict,
    ) -> None:
        """Insert a new operation row with pending status."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=_TTL_HOURS)
        async with self._session_factory() as session:
            await session.execute(sa.text("""
                INSERT INTO operations (id, type, design_id, status, actor, payload,
                                        created_at, updated_at, expires_at)
                VALUES (:id, :type, :design_id, 'pending', :actor, :payload,
                        :now, :now, :expires)
            """), {
                "id": op_id,
                "type": op_type,
                "design_id": design_id,
                "actor": actor,
                "payload": _dump_payload(initial_payload),
                "now": now,
                "expires": expires,
            })
            await session.commit()

    async def get(self, op_id: str) -> dict | None:
        """Return the operation as a flat dict (row columns + payload merged), or None."""
        async with self._session_factory() as session:
            row = (await session.execute(
                sa.text("SELECT * FROM operations WHERE id = :id"),
                {"id": op_id},
            )).mappings().fetchone()

        if row is None:
            return None

        payload = _load_payload(row["payload"])
        return {
            "id": row["id"],
            "type": row["type"],
            "design_id": row["design_id"],
            "status": row["status"],
            "actor": row["actor"],
            "error_description": row["error"],
            **payload,
        }

    async def update(
        self,
        op_id: str,
        *,
        status: str | None = None,
        payload_patch: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Merge status/error updates and patch payload contents."""
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            # Read current payload to merge
            row = (await session.execute(
                sa.text("SELECT payload, status FROM operations WHERE id = :id"),
                {"id": op_id},
            )).mappings().fetchone()

            if row is None:
                logger.warning("OperationStore.update called for unknown op_id=%s", op_id)
                return

            current_payload: dict = _load_payload(row["payload"])
            if payload_patch:
                current_payload.update(payload_patch)

            sets = ["payload = :payload", "updated_at = :now"]
            params: dict[str, Any] = {
                "id": op_id,
                "payload": _dump_payload(current_payload),
                "now": now,
            }

            if status is not None:
                sets.append("status = :status")
                params["status"] = status

            if error is not None:
                sets.append("error = :error")
                params["error"] = error

            await session.execute(
                sa.text(f"UPDATE operations SET {', '.join(sets)} WHERE id = :id"),  # nosec B608 - sets contains only hardcoded column names, not user input
                params,
            )
            await session.commit()

    async def update_option_status(
        self,
        op_id: str,
        option_id: str,
        new_status: str,
    ) -> bool:
        """Atomically transition an option from pending to new_status.

        Returns True if the update happened (option was pending), False otherwise.
        Uses application-level optimistic concurrency: read → check → write.
        """
        async with self._session_factory() as session:
            row = (await session.execute(
                sa.text("SELECT payload FROM operations WHERE id = :id"),
                {"id": op_id},
            )).mappings().fetchone()

            if row is None:
                return False

            payload: dict = _load_payload(row["payload"])
            options: dict = payload.get("options", {})
            option = options.get(option_id)

            if option is None or option.get("status") != "pending":
                return False

            option["status"] = new_status
            payload["options"] = options

            await session.execute(
                sa.text(
                    "UPDATE operations SET payload = :payload, updated_at = :now WHERE id = :id"
                ),
                {
                    "id": op_id,
                    "payload": _dump_payload(payload),
                    "now": datetime.now(timezone.utc),
                },
            )
            await session.commit()

        return True

    async def delete_expired(self) -> int:
        """Delete all operations past their expires_at. Returns count deleted."""
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            result = await session.execute(
                sa.text("DELETE FROM operations WHERE expires_at < :now"),
                {"now": now},
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    async def mark_stale_running_as_failed(self, message: str) -> int:
        """Transition all running operations to failed — called on server startup."""
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            # For each running op, update error field AND set error_description in payload
            rows = (await session.execute(
                sa.text("SELECT id, payload FROM operations WHERE status = 'running'"),
            )).mappings().fetchall()

            count = 0
            for row in rows:
                payload = _load_payload(row["payload"])
                payload["error_description"] = message
                await session.execute(
                    sa.text("""
                        UPDATE operations
                        SET status = 'failed', error = :msg, payload = :payload,
                            updated_at = :now
                        WHERE id = :id
                    """),
                    {"id": row["id"], "msg": message,
                     "payload": _dump_payload(payload), "now": now},
                )
                count += 1

            await session.commit()
            return count
