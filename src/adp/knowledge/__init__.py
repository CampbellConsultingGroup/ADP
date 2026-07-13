"""ADP knowledge base — indexing and hybrid retrieval for grounded AI (ADP-SPEC-005)."""

from adp.knowledge.retrieval import KnowledgeRetrieval
from adp.knowledge.schema import (
    CitationRef,
    CitationResolutionError,
    IndexingError,
    KnowledgeError,
    KnowledgeItem,
    KnowledgeType,
    RetrievalError,
    RetrievalQuery,
    RetrievalResult,
    RetrievalResultEntry,
    SchemaValidationError,
)

__all__ = [
    "KnowledgeRetrieval",
    "KnowledgeItem",
    "KnowledgeType",
    "CitationRef",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalResultEntry",
    "KnowledgeError",
    "RetrievalError",
    "IndexingError",
    "SchemaValidationError",
    "CitationResolutionError",
]
