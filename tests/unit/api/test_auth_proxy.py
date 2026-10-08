"""The /auth Keycloak proxy must relay each upstream Set-Cookie separately.

Regression: folding Keycloak's three login-page cookies into one comma-joined
Set-Cookie header lost the auth session in real browsers, so every login
failed with "login timeout".
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adp.api.routers import auth_proxy

_COOKIES = [
    "AUTH_SESSION_ID=abc;Version=1;Path=/auth/realms/ADPRealm/;Secure;HttpOnly;SameSite=None",
    "KC_AUTH_SESSION_HASH=def;Version=1;Path=/auth/realms/ADPRealm/;Max-Age=60;Secure",
    "KC_RESTART=ghi;Version=1;Path=/auth/realms/ADPRealm/;Secure;HttpOnly",
]


def _client(monkeypatch) -> TestClient:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = [("content-type", "text/html")] + [("set-cookie", c) for c in _COOKIES]
        return httpx.Response(200, headers=headers, content=b"<html>login</html>")

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setenv("ADP_KEYCLOAK_INTERNAL_URL", "http://keycloak.internal")
    monkeypatch.setattr(auth_proxy.httpx, "AsyncClient", fake_async_client)
    app = FastAPI()
    app.include_router(auth_proxy.router)
    return TestClient(app)


def test_each_set_cookie_relayed_as_its_own_header(monkeypatch) -> None:
    resp = _client(monkeypatch).get("/auth/realms/ADPRealm/protocol/openid-connect/auth")

    assert resp.status_code == 200
    assert resp.headers.get_list("set-cookie") == _COOKIES


def test_non_cookie_headers_still_relayed(monkeypatch) -> None:
    resp = _client(monkeypatch).get("/auth/realms/ADPRealm/account")

    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == "<html>login</html>"
