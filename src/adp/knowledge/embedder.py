"""Self-hosted embedding provider — wraps sentence-transformers (ADP-SPEC-005).

No external API calls. The model is loaded lazily on first use.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


# One loaded model per name for the whole process (ADP-blp.16). Each EmbeddingProvider used to
# load its own copy, so the search index and the knowledge writer held two, and a CALM import
# built a provider -- and reloaded the model from disk -- on every request.
_models: dict[str, Any] = {}
_models_lock = threading.Lock()


def _load_model(model_name: str) -> Any:
    with _models_lock:  # embedding now runs in worker threads: load once, not once per thread
        model = _models.get(model_name)
        if model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for embedding generation. "
                    "Install it with: pip install sentence-transformers"
                ) from exc
            model = _models[model_name] = SentenceTransformer(model_name)
        return model


def _warm(model_names: list[str]) -> None:
    for name in model_names:
        try:
            _load_model(name)
            logger.info("embedding model %s loaded", name)
        except Exception as exc:  # noqa: BLE001 - warm-up is best effort; first use retries
            logger.warning("embedding model %s not preloaded: %s", name, exc)


def start_warmup() -> threading.Thread | None:
    """Load the embedding models in a background thread at startup.

    Every create or rename of a searchable record embeds its text while the request waits, and
    the first one after the process starts also loaded the model: about 17 s locally, longer on
    a cold Azure replica. The UI looked as if Add did nothing. Startup does not wait for this
    thread; a request that arrives before it finishes waits on the model lock as before.
    ADP_EMBEDDING_WARMUP=0 (or false/no/off) turns it off.
    """
    import os

    if os.environ.get("ADP_EMBEDDING_WARMUP", "").strip().lower() in {"0", "false", "no", "off"}:
        return None
    search_model = os.environ.get("ADP_EMBEDDING_MODEL", DEFAULT_MODEL)
    names = list(dict.fromkeys([search_model, DEFAULT_MODEL]))
    thread = threading.Thread(target=_warm, args=(names,), name="embedding-warmup", daemon=True)
    thread.start()
    return thread


class EmbeddingProvider:
    """Wraps a sentence-transformers model for local embedding generation."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None  # lazy-loaded on first embed call

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = _load_model(self._model_name)
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

    async def aembed(self, text: str) -> list[float]:
        """embed() in a worker thread, for async callers: encoding is CPU-bound and would
        otherwise stall every other request on the event loop (ADP-blp.16)."""
        return await asyncio.to_thread(self.embed, text)

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


async def aembed_or_zero(title: str, full_text: str) -> list[float]:
    """embed_or_zero() in a worker thread, for async request handlers (ADP-blp.16)."""
    return await asyncio.to_thread(embed_or_zero, title, full_text)
