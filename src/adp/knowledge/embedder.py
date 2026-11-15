"""Self-hosted embedding provider — wraps sentence-transformers (ADP-SPEC-005).

No external API calls. The model is loaded lazily on first use.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingProvider:
    """Wraps a sentence-transformers model for local embedding generation."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None  # lazy-loaded on first embed call

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for embedding generation. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding vector dimension for the configured model."""
        dim: Any = self._get_model().get_sentence_embedding_dimension()
        return int(dim)

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Use embed_batch for efficiency."""
        result: Any = self._get_model().encode(text, convert_to_numpy=True)
        return result.tolist()  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts in one forward pass (preferred for indexing)."""
        if not texts:
            return []
        embeddings: Any = self._get_model().encode(texts, convert_to_numpy=True, batch_size=32)
        return [e.tolist() for e in embeddings]

# ── Shared write-path helper (935-pattern-registry research D6) ───────────────

_shared: EmbeddingProvider | None = None


def _shared_provider() -> EmbeddingProvider:
    global _shared
    if _shared is None:
        _shared = EmbeddingProvider(DEFAULT_MODEL)
    return _shared


def embed_or_zero(title: str, full_text: str) -> list[float]:
    """Embed title + full_text for a knowledge item; zero vector on any failure.

    The single embedding path for knowledge writes (the knowledge API and the pattern
    registry's knowledge projection). Synchronous CPU work: async callers should run it via
    asyncio.to_thread.
    """
    try:
        return _shared_provider().embed(f"{title}\n{full_text}")
    except Exception as exc:  # noqa: BLE001 - documented zero-vector fallback
        logger.warning("Embedding generation failed, using zero vector: %s", exc)
        return [0.0] * EMBEDDING_DIM
