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
from fastapi import APIRouter, Request, Response

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


@router.api_route(
    "/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_to_keycloak(path: str, request: Request) -> Response:
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

    response_headers = {
        k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
