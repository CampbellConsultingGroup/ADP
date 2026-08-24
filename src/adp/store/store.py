"""DesignStore — PostgreSQL-backed persistence for ArchitectureDescription.

This is the primary interface for saving, retrieving, versioning, and querying
architecture designs. All operations are typed (ART-XIII); no raw dicts cross
the store boundary.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pydantic
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from adp.models import SCHEMA_VERSION, ArchitectureDescription
from adp.store.logging import log_operation, timed_operation
from adp.store.queries import (
    query_by_provenance,
    query_orphan_requirements,
    query_relationships,
    query_satisfies,
    query_verdict_chain,
)
from adp.store.records import (
    DesignRecord,
    DesignVersion,
    VerdictChain,
    audit_entries,
    design_versions,
    designs,
)

if TYPE_CHECKING:
    pass


# ── Exception hierarchy ───────────────────────────────────────────────────────


class StoreError(Exception):
    def __init__(self, design_id: str, message: str) -> None:
        self.design_id = design_id
        super().__init__(message)


class DesignNotFoundError(StoreError):
    pass


class EntityNotFoundError(StoreError):
    pass


class SchemaValidationError(StoreError):
    pass


class ConcurrencyConflictError(StoreError):
    pass


class AuditIntegrityError(StoreError):
    """A save's audit_log carries an entry whose id collides with an existing,
    differently-contented audit_entries row for the same design (ADP-4qv).

    next_audit_id()'s max+1 logic should make this impossible in the single-
    writer case; this is a defense-in-depth guard against a stale-read race
    between two concurrent writers on the same design (write_audit_record's
    own save() call doesn't pass expected_version), which could otherwise
    independently compute the same next AUD-NNN id for two genuinely
    different entries and silently lose one of them.
    """


# ── DesignStore ───────────────────────────────────────────────────────────────


class DesignStore:
    """Typed async store for ArchitectureDescription persistence."""

    def __init__(self, database_url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save(
        self,
        description: ArchitectureDescription,
        actor: str,
        expected_version: int | None = None,
    ) -> DesignRecord:
        """Persist a new version atomically with all audit entries.

        Raises SchemaValidationError if the description fails re-validation.
        Raises ConcurrencyConflictError if expected_version doesn't match.
        """
        # Re-validate to enforce FR-006 (schema validation on write).
        try:
            ArchitectureDescription.model_validate(description.model_dump())
        except pydantic.ValidationError as exc:
            raise SchemaValidationError(description.id, f"Schema validation failed: {exc}") from exc

        now = datetime.now(timezone.utc)

        async with self._session_factory() as session:
            async with session.begin():
                # Optimistic concurrency check.
                current_row = await session.execute(
                    sa.select(designs.c.current_version).where(designs.c.id == description.id)
                )
                existing = current_row.fetchone()

                if existing is not None:
                    current_ver: int = existing[0]
                    if expected_version is not None and current_ver != expected_version:
                        raise ConcurrencyConflictError(
                            description.id,
                            f"Concurrency conflict: expected version {expected_version}, "
                            f"current is {current_ver}",
                        )
                    new_version = current_ver + 1
                else:
                    if expected_version is not None and expected_version != 0:
                        raise ConcurrencyConflictError(
                            description.id,
                            "Design does not exist; expected_version must be 0 or None"
                            " for first save",
                        )
                    new_version = 1

                content_json = json.loads(description.model_dump_json())

                # Insert new version (immutable once written).
                await session.execute(
                    design_versions.insert().values(
                        design_id=description.id,
                        version_num=new_version,
                        schema_version=description.schema_version,
                        content=content_json,
                        created_at=now,
                        created_by=actor,
                    )
                )

                # Upsert designs pointer.
                # Lifecycle fields to sync to the `designs` table (ADP-SPEC-030)
                lifecycle_vals = {
                    "lifecycle_status": description.lifecycle_status.value,
                    "proposed_date": description.proposed_date,
                    "current_since": description.current_since,
                    "review_due": description.review_due,
                    "retirement_date": description.retirement_date,
                }

                if existing is not None:
                    await session.execute(
                        designs.update()
                        .where(designs.c.id == description.id)
                        .values(
                            current_version=new_version,
                            updated_at=now,
                            title=description.title,
                            **lifecycle_vals,
                        )
                    )
                else:
                    await session.execute(
                        designs.insert().values(
                            id=description.id,
                            current_version=new_version,
                            title=description.title,
                            schema_version_at_creation=description.schema_version,
                            created_at=now,
                            updated_at=now,
                            **lifecycle_vals,
                        )
                    )

                # Write audit entries atomically (FR-003).
                # Use INSERT ... ON CONFLICT ... DO UPDATE ... WHERE <content differs>
                # because audit_log accumulates all historical entries — prior entries
                # already exist in the table from previous saves and, when unchanged,
                # must silently no-op rather than re-insert. Conflict target is
                # (design_id, id), not id alone (ADP-a64) — id (AUD-NNN) is only
                # unique within its own design, the scope next_audit_id() generates
                # it at; a global id-only target caused every design after the first
                # to silently lose its own AUD-001, AUD-002, ... to a same-numbered
                # entry from an unrelated design.
                #
                # The DO UPDATE (rather than DO NOTHING) is deliberate (ADP-4qv): when
                # the WHERE predicate finds the conflicting row's content genuinely
                # differs from the entry being (re-)saved — a real same-design id
                # collision, not legitimate re-accumulation of an unchanged entry —
                # Postgres attempts the UPDATE, which the append-only trigger
                # (deny_audit_mutation(), migration 001) unconditionally rejects.
                # That raises loudly and rolls back the whole save, including the
                # design_versions insert, instead of silently losing one entry.
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                for entry in description.audit_log:
                    stmt = pg_insert(audit_entries).values(
                        id=entry.id,
                        design_id=description.id,
                        design_version=new_version,
                        actor=entry.actor,
                        action=entry.action,
                        affected_entity=entry.affected_entity,
                        summary=entry.summary,
                        timestamp=entry.timestamp,
                        origin=entry.origin,
                        created_at=now,
                    )
                    try:
                        await session.execute(
                            stmt.on_conflict_do_update(
                                index_elements=["design_id", "id"],
                                # Value is irrelevant — attempting any UPDATE at all
                                # on this table always raises, per the trigger above.
                                # This branch is only reached when WHERE is true.
                                set_={"actor": stmt.excluded.actor},
                                where=(
                                    (audit_entries.c.actor != stmt.excluded.actor)
                                    | (audit_entries.c.action != stmt.excluded.action)
                                    | (audit_entries.c.affected_entity
                                       != stmt.excluded.affected_entity)
                                    | (audit_entries.c.summary != stmt.excluded.summary)
                                    | (audit_entries.c.timestamp != stmt.excluded.timestamp)
                                    | (audit_entries.c.origin != stmt.excluded.origin)
                                ),
                            )
                        )
                    except sa.exc.DBAPIError as exc:
                        raise AuditIntegrityError(
                            description.id,
                            f"audit entry {entry.id!r} collides with an existing, "
                            "differently-contented entry for this design",
                        ) from exc

        log_operation("save", description.id, version_num=new_version, actor=actor)
        return DesignRecord(
            design_id=description.id,
            current_version=new_version,
            title=description.title,
            created_at=description.created_at,
            updated_at=description.updated_at,
        )

    async def get(
        self, design_id: str, version: int | None = None
    ) -> ArchitectureDescription:
        """Retrieve a stored design. Defaults to the latest version."""
        async with self._session_factory() as session:
            if version is None:
                # Join to get current version number.
                row = await session.execute(
                    sa.select(design_versions.c.content, design_versions.c.schema_version,
                               design_versions.c.version_num)
                    .join(designs, (designs.c.id == design_versions.c.design_id) &
                          (designs.c.current_version == design_versions.c.version_num))
                    .where(designs.c.id == design_id)
                )
            else:
                row = await session.execute(
                    sa.select(design_versions.c.content, design_versions.c.schema_version,
                               design_versions.c.version_num)
                    .where(
                        (design_versions.c.design_id == design_id) &
                        (design_versions.c.version_num == version)
                    )
                )

            result = row.fetchone()
            if result is None:
                raise DesignNotFoundError(
                    design_id,
                    f"Design {design_id!r} (version {version}) not found",
                )

            content, stored_schema_version, version_num = result
            description = ArchitectureDescription.model_validate(content)

            # NFR-002 detection clause: log warning on schema version mismatch.
            if stored_schema_version != SCHEMA_VERSION:
                import logging
                logging.getLogger("adp.store").warning(
                    json.dumps({
                        "schema_mismatch": True,
                        "stored_version": stored_schema_version,
                        "live_version": SCHEMA_VERSION,
                        "design_id": design_id,
                    })
                )

        log_operation("get", design_id, version_num=version_num)
        return description

    async def list_versions(self, design_id: str) -> list[DesignVersion]:
        """Return metadata for all versions of a design, ordered ascending."""
        async with self._session_factory() as session:
            # Verify design exists.
            exists = await session.execute(
                sa.select(designs.c.id).where(designs.c.id == design_id)
            )
            if exists.fetchone() is None:
                raise DesignNotFoundError(design_id, f"Design {design_id!r} not found")

            rows = await session.execute(
                sa.select(
                    design_versions.c.design_id,
                    design_versions.c.version_num,
                    design_versions.c.schema_version,
                    design_versions.c.created_at,
                    design_versions.c.created_by,
                )
                .where(design_versions.c.design_id == design_id)
                .order_by(design_versions.c.version_num.asc())
            )

        log_operation("list_versions", design_id)
        return [
            DesignVersion(
                design_id=row.design_id,
                version_num=row.version_num,
                schema_version=row.schema_version,
                created_at=row.created_at,
                created_by=row.created_by,
            )
            for row in rows
        ]

    async def query_satisfies(self, design_id: str, requirement_id: str) -> list:  # type: ignore[type-arg]
        """Return elements satisfying requirement_id in the latest version."""
        description = await self.get(design_id)
        content = json.loads(description.model_dump_json())
        with timed_operation("query_satisfies", design_id):
            result = query_satisfies(content, requirement_id)
        return result

    async def query_orphan_requirements(self, design_id: str) -> list:  # type: ignore[type-arg]
        """Return requirements satisfied by no element and no option."""
        description = await self.get(design_id)
        content = json.loads(description.model_dump_json())
        with timed_operation("query_orphan_requirements", design_id):
            result = query_orphan_requirements(content)
        return result

    async def query_verdict_chain(self, design_id: str, option_id: str) -> VerdictChain:
        """Return full traceability chain for one SolutionOption."""
        description = await self.get(design_id)
        content = json.loads(description.model_dump_json())
        with timed_operation("query_verdict_chain", design_id):
            result = query_verdict_chain(content, option_id)
        return result

    async def query_by_provenance(
        self, design_id: str, provenance_value: str
    ) -> list:  # type: ignore[type-arg]
        """Return elements and options with matching provenance."""
        description = await self.get(design_id)
        content = json.loads(description.model_dump_json())
        with timed_operation("query_by_provenance", design_id):
            result = query_by_provenance(content, provenance_value)
        return result

    async def query_relationships(self, design_id: str, element_id: str) -> list:  # type: ignore[type-arg]
        """Return all relationships where source or target equals element_id."""
        description = await self.get(design_id)
        content = json.loads(description.model_dump_json())
        with timed_operation("query_relationships", design_id):
            result = query_relationships(content, element_id)
        return result

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> list[ArchitectureDescription]:
        """Return a paginated list of the latest version of each design (ADP-SPEC-025/030).

        Loads the full ArchitectureDescription for each design so callers can
        compute element/requirement counts from the canonical model.
        Sorted by created_at descending (most recent first).
        Optionally filtered by lifecycle_status (ADP-SPEC-030).
        """
        offset = (page - 1) * page_size
        async with self._session_factory() as session:
            q = sa.select(designs.c.id).order_by(designs.c.created_at.desc())
            if status is not None:
                q = q.where(designs.c.lifecycle_status == status)
            rows = await session.execute(q.limit(page_size).offset(offset))
            design_ids = [r[0] for r in rows.fetchall()]

        result: list[ArchitectureDescription] = []
        for did in design_ids:
            try:
                result.append(await self.get(did))
            except DesignNotFoundError:
                pass  # race: design deleted between list and get
        return result

    async def count_all(self, status: str | None = None) -> int:
        """Return total count of designs (ADP-SPEC-025/030).

        Optionally filtered by lifecycle_status (ADP-SPEC-030).
        """
        async with self._session_factory() as session:
            q = sa.select(sa.func.count()).select_from(designs)
            if status is not None:
                q = q.where(designs.c.lifecycle_status == status)
            row = await session.execute(q)
            return int(row.scalar() or 0)

    async def next_design_id(self) -> str:
        """Generate the next DSN-NNN id atomically (ADP-SPEC-025)."""
        import re

        async with self._session_factory() as session:
            rows = await session.execute(sa.select(designs.c.id))
            all_ids = [r[0] for r in rows.fetchall()]

        max_n = 0
        for did in all_ids:
            m = re.match(r"^DSN-(\d+)$", did)
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"DSN-{max_n + 1:03d}"

    async def dispose(self) -> None:
        """Release database connections."""
        await self._engine.dispose()
