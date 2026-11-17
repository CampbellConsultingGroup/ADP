"""Root conftest — sets environment for all tests (ADP-SPEC-026).

ADP_AUTH_ENABLED=false disables Keycloak token validation so tests can run
without a live Keycloak instance. Individual auth tests opt back in via
monkeypatch.setenv("ADP_AUTH_ENABLED", "true").
"""

import os

# Disable auth for the entire test suite unless overridden per-test
os.environ.setdefault("ADP_AUTH_ENABLED", "false")


def pytest_addoption(parser):  # type: ignore[no-untyped-def]
    # 935-pattern-registry: regenerate golden files (developer flag; CI never passes it).
    parser.addoption(
        "--update-goldens", action="store_true", default=False,
        help="Rewrite golden files instead of comparing against them.",
    )


# ── ADP-blp.28: never load the real embedding model in a test ─────────────────
# Any write through a store indexes the entity for search, which embeds its text with
# sentence-transformers. Twenty-four test files each stubbed that by hand, and a write path that
# one of them missed loaded the real model (seconds per test, and a download when it is not
# cached). This replaces the model loader for every test outside tests/integration; a test that
# is about the loader itself opts out with @pytest.mark.real_embedding_model.

import pytest  # noqa: E402


class _FakeEmbeddingModel:
    """Stands in for a SentenceTransformer: fixed-size zero vectors, instantly."""

    def get_sentence_embedding_dimension(self) -> int:
        return 384

    def encode(self, texts, **_kwargs):  # type: ignore[no-untyped-def]
        import numpy as np

        if isinstance(texts, str):
            return np.zeros(384, dtype="float32")
        return np.zeros((len(texts), 384), dtype="float32")


def pytest_configure(config):  # type: ignore[no-untyped-def]
    config.addinivalue_line(
        "markers", "real_embedding_model: do not replace the embedding model loader for this test"
    )


@pytest.fixture(autouse=True)
def _no_real_embedding_model(request, monkeypatch):  # type: ignore[no-untyped-def]
    if "tests/integration/" in request.node.nodeid.replace("\\", "/"):
        return
    if request.node.get_closest_marker("real_embedding_model"):
        return
    from adp.knowledge import embedder

    monkeypatch.setattr(embedder, "_load_model", lambda _name: _FakeEmbeddingModel())
