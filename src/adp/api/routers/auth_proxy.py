"""Reverse proxy for Keycloak, mounted at /auth (ADP-cm9).

Keycloak's Container App has internal-only ingress (adp-keycloak.internal...),
unreachable from a real user's browser. But keycloak-js's standard login flow
redirects the browser itself to Keycloak's authorization endpoint -- it can't
go through a server-side call. This router makes adp-api (which is externally
reachable) transparently forward everything under /auth/* to the internal
Keycloak instance, so the browser only ever talks to the one public hostname.

Keycloak is configured (KC_HOSTNAME + --http-relative-path=/auth, see
infra/azure/modules/keycloak.bicep) to already believe its own public base URL
is https://<api-fqdn>/auth -- so it generates correct absolute URLs, redirect
targets, and issuer claims on its own. This proxy does no path rewriting or
URL substitution; it's a transparent pass-through.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter(tags=["auth-proxy"])

# Headers that are connection-scoped or describe a body encoding/length that
# no longer applies once relayed through this proxy -- passing them through
# verbatim would let the browser/httpx disagree with the actual bytes sent.
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "content-encoding",
    "content-length",
    "host",
}


# ADP-blp.6: this proxy is reachable without a token (the browser needs it to log in), so it must
# not expose all of Keycloak. Only the application realm's own endpoints and the static assets
# its login pages load are forwarded. The admin console and REST API (/auth/admin/...) and the
# master realm (/auth/realms/master/...), whose login is the Keycloak administrator's, are not.
_STATIC_PREFIXES = ("resources/", "js/")


def _realm() -> str:
    issuer = os.environ.get("ADP_KEYCLOAK_ISSUER", "http://127.0.0.1:8080/realms/ADPRealm")
    return issuer.rstrip("/").rsplit("/realms/", 1)[-1]


def _is_allowed(path: str) -> bool:
    # No dot segments or backslashes: "/auth/../x" would otherwise be normalised by the HTTP
    # client into a path outside /auth on the internal host.
    segments = path.split("/")
    if any(segment in ("..", ".") for segment in segments) or "\\" in path:
        return False
    realm_root = f"realms/{_realm()}"
    if path == realm_root or path.startswith(realm_root + "/"):
        return True
    return path.startswith(_STATIC_PREFIXES)


@router.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_to_keycloak(path: str, request: Request) -> Response:
    if not _is_allowed(path):
        raise HTTPException(status_code=404, detail="Not found")
    internal_url = os.environ["ADP_KEYCLOAK_INTERNAL_URL"].rstrip("/")
    target = f"{internal_url}/auth/{path}"

    forward_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    body = await request.body()

    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        upstream = await client.request(
            request.method,
            target,
            params=request.query_params,
            headers=forward_headers,
            content=body,
        )

    # Set-Cookie must be relayed as separate headers, never folded into one.
    # httpx's headers.items() comma-joins repeated headers, and browsers don't
    # split a combined Set-Cookie back apart -- Keycloak sets three session
    # cookies on the login page, so folding them loses the session and the
    # login form submit fails with "login timeout".
    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "set-cookie"
    }
    response = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)
    return response
