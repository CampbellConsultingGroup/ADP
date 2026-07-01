"""Self-hosted embedding provider — wraps sentence-transformers (ADP-SPEC-005).

No external API calls. The model is loaded lazily on first use.
"""

from __future__ import annotations

from typing import Any


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
