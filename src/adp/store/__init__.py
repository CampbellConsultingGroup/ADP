"""ADP design store — PostgreSQL-backed persistence for ArchitectureDescription."""

from adp.store.operations import OperationStore
from adp.store.reasoning import ReasoningRecord, ReasoningStore, _hash_prompt
from adp.store.records import DesignRecord, DesignVersion, VerdictChain
from adp.store.store import (
    AuditIntegrityError,
    ConcurrencyConflictError,
    DesignNotFoundError,
    DesignStore,
    EntityNotFoundError,
    SchemaValidationError,
    StoreError,
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
    "AuditIntegrityError",
    "OperationStore",
    "ReasoningStore",
    "ReasoningRecord",
    "_hash_prompt",
]
