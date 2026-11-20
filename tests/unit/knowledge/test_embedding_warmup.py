"""Startup preload of the embedding model.

The first create of a searchable record after the API started waited for the model to load
(about 17 s locally), so Add looked as if it did nothing. start_warmup() loads it in a thread
at startup instead.
"""

from __future__ import annotations

from adp.knowledge import embedder


def test_warmup_loads_the_search_model_and_the_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    loaded: list[str] = []
    monkeypatch.setattr(embedder, "_load_model", lambda name: loaded.append(name))
    monkeypatch.setenv("ADP_EMBEDDING_WARMUP", "1")
    monkeypatch.setenv("ADP_EMBEDDING_MODEL", "custom-model")

    thread = embedder.start_warmup()
    assert thread is not None
    thread.join(timeout=5)

    assert loaded == ["custom-model", embedder.DEFAULT_MODEL]


def test_warmup_loads_one_model_when_both_names_match(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    loaded: list[str] = []
    monkeypatch.setattr(embedder, "_load_model", lambda name: loaded.append(name))
    monkeypatch.setenv("ADP_EMBEDDING_WARMUP", "1")
    monkeypatch.delenv("ADP_EMBEDDING_MODEL", raising=False)

    thread = embedder.start_warmup()
    assert thread is not None
    thread.join(timeout=5)

    assert loaded == [embedder.DEFAULT_MODEL]


def test_warmup_can_be_turned_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADP_EMBEDDING_WARMUP", "off")
    assert embedder.start_warmup() is None


def test_a_failed_load_is_logged_not_raised(monkeypatch, caplog) -> None:  # type: ignore[no-untyped-def]
    def boom(_name: str) -> None:
        raise RuntimeError("no model files")

    monkeypatch.setattr(embedder, "_load_model", boom)
    embedder._warm(["m"])
    assert "not preloaded" in caplog.text
