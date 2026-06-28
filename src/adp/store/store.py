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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

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
                if existing is not None:
                    await session.execute(
                        designs.update()
                        .where(designs.c.id == description.id)
                        .values(current_version=new_version, updated_at=now,
                                title=description.title)
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
                        )
                    )

                # Write audit entries atomically (FR-003).
                for entry in description.audit_log:
                    await session.execute(
                        audit_entries.insert().values(
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
                    )

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

    async def dispose(self) -> None:
        """Release database connections."""
        await self._engine.dispose()
