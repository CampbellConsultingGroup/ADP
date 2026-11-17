"""ADP-blp.16: the search index skips unchanged text and embeds off the event loop."""

from __future__ import annotations

import threading

from adp.knowledge import embedder as embedder_module
from adp.search.index import SearchIndex


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Session:
    """Answers the 'stored text' lookup, records everything else."""

    def __init__(self, stored_text):
        self.stored_text = stored_text
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Result(self.stored_text)


class _Embedder:
    def __init__(self):
        self.calls = []
        self.threads = []

    def embed(self, text):
        self.calls.append(text)
        self.threads.append(threading.current_thread())
        return [0.0] * 384


async def test_unchanged_text_is_not_re_embedded_or_written():
    embedder = _Embedder()
    session = _Session(stored_text="Process Payment")
    await SearchIndex(embedder).upsert("business_capability", "c1", "Process Payment", session)
    assert embedder.calls == []
    assert len(session.statements) == 1  # only the lookup


async def test_changed_or_new_text_is_embedded_in_a_worker_thread():
    for stored in ("Old name", None):
        embedder = _Embedder()
        session = _Session(stored_text=stored)
        await SearchIndex(embedder).upsert("business_capability", "c1", "New name", session)
        assert embedder.calls == ["New name"]
        assert embedder.threads[0] is not threading.main_thread()
        assert len(session.statements) == 2  # lookup + upsert


def test_providers_share_one_loaded_model(monkeypatch):
    """Each provider used to load its own copy of the model."""
    loads = []

    class _FakeModel:
        def __init__(self, name):
            loads.append(name)

    import sys
    import types

    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = _FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    monkeypatch.setattr(embedder_module, "_models", {})

    first = embedder_module.EmbeddingProvider("m1")._get_model()
    second = embedder_module.EmbeddingProvider("m1")._get_model()
    embedder_module.EmbeddingProvider("m2")._get_model()
    assert first is second
    assert loads == ["m1", "m2"]
