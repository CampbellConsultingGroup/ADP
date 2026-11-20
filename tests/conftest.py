"""Root conftest — sets environment for all tests (ADP-SPEC-026).

ADP_AUTH_ENABLED=false disables Keycloak token validation so tests can run
without a live Keycloak instance. Individual auth tests opt back in via
monkeypatch.setenv("ADP_AUTH_ENABLED", "true").
"""

import os

# Disable auth for the entire test suite unless overridden per-test
os.environ.setdefault("ADP_AUTH_ENABLED", "false")
# The app's startup preloads the embedding model in a thread; in tests that thread could outlive
# the fake-loader patch below and load the real model. tests/unit/knowledge/test_embedding_warmup.py
# turns it back on where it is the subject.
os.environ.setdefault("ADP_EMBEDDING_WARMUP", "0")


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


# ── ADP-blp.28: one app for the whole run, not one per test ───────────────────
# create_app() itself is cheap, but FastAPI works out every route's dependencies on an app's
# first request -- about half a second for this app's 370 routes -- and nearly every contract
# test built its own app, so that cost was paid a thousand times over. Tests still call
# create_app(); it now hands back one shared app (per configuration), cleaned of whatever the
# previous test set on it. This runs at import, before any test module binds the name.
#
# The shared app is NOT used when a test changes the app's structure: an app whose routes,
# middleware or exception handlers differ after a test is thrown away.

import adp.api.app as _app_module  # noqa: E402

_real_create_app = _app_module.create_app
_shared_apps: dict[tuple, object] = {}
_shape: dict[int, tuple] = {}
# Read on every request or by the lifespan, not when the app is built, so they need no new app.
_CALL_TIME_ENV = (
    "ADP_DATABASE_URL",
    "ADP_BUSINESS_ARCH_EXPORT_ROOT",
    "ADP_BUSINESS_ARCH_EXPORT_INTERVAL_SECONDS",
)


def _app_shape(app) -> tuple:  # type: ignore[no-untyped-def]
    return (len(app.router.routes), len(app.user_middleware), len(app.exception_handlers))


def _shared_create_app():  # type: ignore[no-untyped-def]
    key = tuple(
        sorted(
            (name, value)
            for name, value in os.environ.items()
            if name.startswith("ADP_") and name not in _CALL_TIME_ENV
        )
    )
    app = _shared_apps.get(key)
    if app is None:
        if len(_shared_apps) >= 8:  # a test run uses a handful of configurations
            _shared_apps.pop(next(iter(_shared_apps)))
        app = _shared_apps[key] = _real_create_app()
        _shape[id(app)] = _app_shape(app)
    # What a previous test left behind.
    app.dependency_overrides.clear()  # type: ignore[attr-defined]
    app.state._state.clear()  # type: ignore[attr-defined]
    return app


_shared_create_app.__wrapped__ = _real_create_app  # type: ignore[attr-defined]
_app_module.create_app = _shared_create_app  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _discard_changed_apps():  # type: ignore[no-untyped-def]
    yield
    for key, app in list(_shared_apps.items()):
        if _app_shape(app) != _shape.get(id(app)):
            del _shared_apps[key]


# ── ADP-blp.13: no model choice leaks from one test to the next ────────────────
# A worker keeps the last model choices it read from the database (adp.llm.settings).


@pytest.fixture(autouse=True)
def _fresh_llm_settings():  # type: ignore[no-untyped-def]
    from adp.llm import settings as llm_settings

    llm_settings.reset_for_tests()
    yield
    llm_settings.reset_for_tests()
