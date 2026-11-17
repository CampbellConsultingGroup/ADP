"""ADP-blp.5 (request limits) and ADP-blp.9 (metric labels)."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from adp.api import limits
from adp.api.limits import BodySizeLimitMiddleware, RateLimiter, enforce_llm_rate_limit


def _app(max_bytes: int | None = None) -> FastAPI:
    app = FastAPI(dependencies=[Depends(enforce_llm_rate_limit)])
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        return {"bytes": len(await request.body())}

    @app.post("/api/v1/chat/conversations/{conversation_id}/messages")
    async def send(conversation_id: str) -> dict:
        return {"ok": True}

    @app.get("/api/v1/chat/conversations/{conversation_id}/messages")
    async def read(conversation_id: str) -> dict:
        return {"ok": True}

    return app


def test_body_under_the_limit_passes():
    assert TestClient(_app(100)).post("/echo", content=b"x" * 100).json() == {"bytes": 100}


def test_declared_oversize_body_is_refused():
    resp = TestClient(_app(100)).post("/echo", content=b"x" * 101)
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]


def test_chunked_oversize_body_is_refused():
    """No Content-Length: the bytes actually received are counted."""

    def chunks():
        for _ in range(5):
            yield b"x" * 40

    assert TestClient(_app(100)).post("/echo", content=chunks()).status_code == 413


def test_limit_from_env_and_zero_disables(monkeypatch):
    monkeypatch.setenv("ADP_MAX_REQUEST_BYTES", "10")
    assert TestClient(_app()).post("/echo", content=b"x" * 11).status_code == 413
    monkeypatch.setenv("ADP_MAX_REQUEST_BYTES", "0")
    assert TestClient(_app()).post("/echo", content=b"x" * 5000).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/chat/conversations/c1/messages",
        "/api/v1/designs/DSN-1/intake",
        "/api/v1/designs/DSN-1/recommend",
        "/api/v1/designs/DSN-1/validate",
        "/api/v1/business/capabilities/agent-review",
        "/api/v1/business/capabilities/cap-1/agent-review",
    ],
)
def test_llm_routes_are_recognised(path):
    assert limits.is_llm_route("POST", path)
    assert not limits.is_llm_route("GET", path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/chat/conversations",
        "/api/v1/designs/DSN-1/validate/op-1/override",
        "/api/v1/designs/DSN-1/intake/op-1/proposals/p-1/confirm",
        "/api/v1/patterns/validate",
        "/api/v1/applications",
    ],
)
def test_other_routes_are_not_rate_limited(path):
    assert not limits.is_llm_route("POST", path)


def test_rate_limiter_window():
    limiter = RateLimiter()
    assert limiter.check("u", 2, now=0.0) is None
    assert limiter.check("u", 2, now=1.0) is None
    assert limiter.check("u", 2, now=2.0) == pytest.approx(58.0)
    assert limiter.check("other", 2, now=2.0) is None  # per user
    assert limiter.check("u", 2, now=60.5) is None  # the first call has aged out


def test_llm_route_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("ADP_LLM_RATE_LIMIT_PER_MINUTE", "2")
    client = TestClient(_app())
    url = "/api/v1/chat/conversations/c1/messages"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
    blocked = client.post(url)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    assert "2 per minute" in blocked.json()["detail"]
    assert client.get(url).status_code == 200  # reads are never limited

    monkeypatch.setenv("ADP_LLM_RATE_LIMIT_PER_MINUTE", "0")
    assert client.post(url).status_code == 200


def test_metrics_are_labelled_by_route_template(monkeypatch):
    """ADP-blp.9: ids and made-up paths must not become metric labels."""
    monkeypatch.setenv("ADP_AUTH_ENABLED", "false")
    from adp.api.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    for n in range(5):
        client.get(f"/no-such-path-{n}")
        client.get(f"/auth/admin/DSN-PROBE-{n}")  # matches /auth/{path:path}, refused there
    metrics = client.get("/metrics").text
    assert "no-such-path" not in metrics
    assert "DSN-PROBE" not in metrics
    assert 'route="unmatched"' in metrics
    assert 'route="/auth/{path:path}"' in metrics


def test_chat_message_length_is_capped():
    from pydantic import ValidationError

    from adp.chat.models import SendMessageRequest

    SendMessageRequest(content="x" * 20_000)
    with pytest.raises(ValidationError):
        SendMessageRequest(content="x" * 20_001)
    with pytest.raises(ValidationError):
        SendMessageRequest(content="hi", diagram_context="x" * 200_001)


def test_svg_export_dimension_cap():
    from fastapi import HTTPException

    from adp.diagrams.router import _check_svg_dimensions

    _check_svg_dimensions('<svg width="800" height="600" viewBox="0 0 800 600"></svg>')
    _check_svg_dimensions("not svg at all")
    for svg in (
        '<svg width="100000" height="10"></svg>',
        "<svg height='20000'></svg>",
        '<svg viewBox="0 0 50000 50000"></svg>',
    ):
        with pytest.raises(HTTPException) as err:
            _check_svg_dimensions(svg)
        assert err.value.status_code == 422
