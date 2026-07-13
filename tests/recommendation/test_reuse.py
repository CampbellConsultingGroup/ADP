"""Tests for registry-grounded recommendations (ADP-SPEC-007 reuse candidates)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from adp.eval.fakes import NoOpTelemetry
from adp.recommendation.models import ReuseCandidate
from adp.recommendation.reuse import (
    ApplicationReuseProvider,
    relevance,
    tokenize,
)
from adp.recommendation.steps import generate_step, reuse_step

# ── Pure relevance scoring ───────────────────────────────────────────────────

def test_tokenize_drops_short_and_stopwords() -> None:
    toks = tokenize("The system must provide payment processing")
    assert "payment" in toks and "processing" in toks
    assert "the" not in toks and "must" not in toks and "system" not in toks


def test_relevance_is_fraction_of_requirement_terms_covered() -> None:
    req = tokenize("payment processing fraud detection")
    assert relevance(req, tokenize("payment gateway")) == 0.25  # 1 of 4
    assert relevance(req, tokenize("payment processing fraud detection")) == 1.0
    assert relevance(req, tokenize("unrelated content")) == 0.0
    assert relevance(set(), tokenize("anything")) == 0.0


# ── reuse_step ───────────────────────────────────────────────────────────────

class _FakeProvider:
    def __init__(self, candidates: list[ReuseCandidate]) -> None:
        self._candidates = candidates

    async def find_candidates(self, requirements: list[Any], *, limit: int = 5):
        return self._candidates[:limit]


async def test_reuse_step_populates_candidates() -> None:
    cand = ReuseCandidate(app_id="APP-1", name="Billing", relevance=0.5)
    state = {"operation_id": "op", "requirements": [SimpleNamespace(description="billing")]}
    out = await reuse_step(state, reuse_provider=_FakeProvider([cand]), telemetry=NoOpTelemetry())
    assert out["reuse_candidates"] == [cand]


async def test_reuse_step_none_provider_is_empty() -> None:
    state = {"operation_id": "op", "requirements": []}
    out = await reuse_step(state, reuse_provider=None, telemetry=NoOpTelemetry())
    assert out["reuse_candidates"] == []


async def test_reuse_step_swallows_provider_error() -> None:
    class _Boom:
        async def find_candidates(self, *a: Any, **k: Any):
            raise RuntimeError("db down")

    state = {"operation_id": "op", "requirements": []}
    out = await reuse_step(state, reuse_provider=_Boom(), telemetry=NoOpTelemetry())
    assert out["reuse_candidates"] == []


# ── generate_step validates reuse ids against the offered pool ────────────────

class _FakeLLM:
    _model = "test-model"

    def __init__(self, content: str) -> None:
        self._content = content

    async def chat(self, system: str, user: str, correlation_id: str | None = None) -> dict:
        # Assert the offered application is actually in the prompt.
        assert "APP-1" in user
        return {
            "choices": [{"message": {"content": self._content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }


async def test_generate_step_keeps_only_offered_reuse_ids() -> None:
    offered = ReuseCandidate(app_id="APP-1", name="Billing Platform", relevance=0.6)
    content = (
        '{"options": [{"title": "Reuse billing", "rationale": "reuse it", '
        '"grounded_on": [], "satisfies": ["REQ-1"], "proposed_elements": [], '
        '"reuse_candidates": ["APP-1", "APP-HALLUCINATED"]}]}'
    )
    state = {
        "operation_id": "op",
        "requirements": [SimpleNamespace(id="REQ-1", description="billing and payments")],
        "retrieved_knowledge": [],
        "reuse_candidates": [offered],
    }
    out = await generate_step(state, llm=_FakeLLM(content), telemetry=NoOpTelemetry())
    options = out["candidate_options"]
    assert len(options) == 1
    reused = options[0].reuse_candidates
    assert [c.app_id for c in reused] == ["APP-1"]  # hallucinated id dropped


# ── ApplicationReuseProvider assembles + ranks from the registry ──────────────

class _FakeSessionFactory:
    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *exc: Any) -> bool:
        return False


async def test_application_reuse_provider_scores_and_ranks(monkeypatch) -> None:
    import adp.application.store as store

    apps = [
        SimpleNamespace(id="APP-1", name="Payments Gateway",
                        description="handles payment processing",
                        time_classification=SimpleNamespace(value="invest"),
                        r_strategy=None),
        SimpleNamespace(id="APP-2", name="HR Portal", description="staff leave requests",
                        time_classification=None, r_strategy=None),
    ]
    caps = {
        "APP-1": [SimpleNamespace(capability_name="Fraud detection")],
        "APP-2": [SimpleNamespace(capability_name="Payroll")],
    }

    async def _list_apps(session: Any):
        return SimpleNamespace(items=apps, total=len(apps))

    async def _list_caps(app_id: str, session: Any):
        return SimpleNamespace(items=caps[app_id])

    monkeypatch.setattr(store, "list_applications", _list_apps)
    monkeypatch.setattr(store, "list_app_capability_links", _list_caps)

    provider = ApplicationReuseProvider(_FakeSessionFactory())
    reqs = [SimpleNamespace(description="payment processing and fraud detection")]
    found = await provider.find_candidates(reqs, limit=5)

    assert [c.app_id for c in found] == ["APP-1"]  # HR Portal scores 0, excluded
    assert found[0].capabilities == ["Fraud detection"]
    assert found[0].time_classification == "invest"
    assert found[0].relevance > 0
