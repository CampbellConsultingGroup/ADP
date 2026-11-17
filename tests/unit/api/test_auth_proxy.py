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


# ── ADP-blp.64: the client cannot choose the forwarding headers Keycloak trusts ──


def _capturing_client(monkeypatch) -> tuple[TestClient, dict[str, str]]:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(200, content=b"ok")

    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setenv("ADP_KEYCLOAK_INTERNAL_URL", "http://keycloak.internal")
    monkeypatch.setenv("ADP_KEYCLOAK_ISSUER", "https://adp.example.com/auth/realms/ADPRealm")
    monkeypatch.setattr(auth_proxy.httpx, "AsyncClient", fake_async_client)
    app = FastAPI()
    app.include_router(auth_proxy.router)
    return TestClient(app), seen


def test_client_supplied_forwarding_headers_are_replaced(monkeypatch) -> None:
    client, seen = _capturing_client(monkeypatch)
    client.get(
        "/auth/realms/ADPRealm/account",
        headers={
            # Spoofed by the caller; the last entry is the one the ingress appended.
            "X-Forwarded-For": "127.0.0.1, 203.0.113.9",
            "X-Forwarded-Host": "evil.example",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Port": "81",
            "Forwarded": "for=127.0.0.1;host=evil.example;proto=http",
            "X-Real-IP": "127.0.0.1",
        },
    )

    assert seen["x-forwarded-for"] == "203.0.113.9"
    assert seen["x-forwarded-host"] == "adp.example.com"
    assert seen["x-forwarded-proto"] == "https"
    assert "forwarded" not in seen
    assert "x-forwarded-port" not in seen
    assert "x-real-ip" not in seen


def test_without_an_ingress_the_socket_peer_is_forwarded(monkeypatch) -> None:
    client, seen = _capturing_client(monkeypatch)
    client.get("/auth/realms/ADPRealm/account")

    assert seen["x-forwarded-for"] == "testclient"
    assert seen["x-forwarded-proto"] == "https"


def test_other_request_headers_still_reach_keycloak(monkeypatch) -> None:
    client, seen = _capturing_client(monkeypatch)
    client.get("/auth/realms/ADPRealm/account", headers={"Cookie": "AUTH_SESSION_ID=abc"})

    assert seen["cookie"] == "AUTH_SESSION_ID=abc"
