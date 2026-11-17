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


# ── ADP-blp.6: only the login flow's paths are forwarded ──────────────────────

import pytest  # noqa: E402


@pytest.mark.parametrize(
    "path",
    [
        "/auth/realms/ADPRealm/protocol/openid-connect/token",
        "/auth/realms/ADPRealm/.well-known/openid-configuration",
        "/auth/resources/abc12/login/keycloak.v2/css/styles.css",
        "/auth/js/keycloak.js",
    ],
)
def test_login_flow_paths_are_forwarded(monkeypatch, path) -> None:
    assert _client(monkeypatch).get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/auth/admin/master/console/",
        "/auth/admin/realms/ADPRealm/users",
        "/auth/realms/master/protocol/openid-connect/token",
        "/auth/realms/ADPRealmX/account",
        "/auth/realms",
        "/auth/",
        "/auth/metrics",
        "/auth/realms/ADPRealm/%2e%2e/master/account",
    ],
)
def test_everything_else_is_refused(monkeypatch, path) -> None:
    resp = _client(monkeypatch).get(path)
    assert resp.status_code == 404
    assert resp.text != "<html>login</html>"


def test_dot_segments_are_refused() -> None:
    assert not auth_proxy._is_allowed("realms/ADPRealm/../master/account")
    assert not auth_proxy._is_allowed("resources/../admin")
    assert auth_proxy._is_allowed("realms/ADPRealm")


def test_realm_follows_the_configured_issuer(monkeypatch) -> None:
    monkeypatch.setenv("ADP_KEYCLOAK_ISSUER", "https://x.example/auth/realms/Other/")
    assert auth_proxy._is_allowed("realms/Other/account")
    assert not auth_proxy._is_allowed("realms/ADPRealm/account")
