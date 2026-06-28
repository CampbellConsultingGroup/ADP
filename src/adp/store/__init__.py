"""ADP design store — PostgreSQL-backed persistence for ArchitectureDescription."""

from adp.store.records import DesignRecord, DesignVersion, VerdictChain
from adp.store.store import (
    ConcurrencyConflictError,
    DesignNotFoundError,
    EntityNotFoundError,
    SchemaValidationError,
    StoreError,
    DesignStore,
)

__all__ = [
    "DesignStore",
    "DesignRecord",
    "DesignVersion",
    "VerdictChain",
    "StoreError",
    "DesignNotFoundError",
    "EntityNotFoundError",
    "SchemaValidationError",
    "ConcurrencyConflictError",
]
