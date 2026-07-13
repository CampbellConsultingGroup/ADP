"""FastAPI authentication middleware (ADP-SPEC-026).

Intercepts all /api/v1/ requests. When ADP_AUTH_ENABLED=true:
  - Requires a valid Bearer token in the Authorization header
  - Validates the token against Keycloak's JWKS endpoint
  - Injects AuthenticatedUser into request.state.user

Returns:
  401 — missing or invalid token
  503 — Keycloak JWKS unreachable (first-time fetch only)

When ADP_AUTH_ENABLED=false (default for tests/dev):
  - Skips all validation
  - Sets request.state.user = UNAUTHENTICATED_USER
"""

from __future__ import annotations

import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from adp.auth.models import UNAUTHENTICATED_USER, TokenExpiredError, TokenValidationError
from adp.auth.tokens import decode_token

_logger = logging.getLogger("adp.auth")

_AUTH_ENABLED_DEFAULT = "true"
_PROTECTED_PREFIX = "/api/v1/"

# Paths exempt from auth even when enabled (health, metrics)
_EXEMPT_PATHS = {"/health", "/metrics"}


def _auth_enabled() -> bool:
    return os.environ.get("ADP_AUTH_ENABLED", _AUTH_ENABLED_DEFAULT).lower() == "true"


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer token validation middleware for ADP FastAPI routes."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Always set a default user so request.state.user is always defined
        request.state.user = UNAUTHENTICATED_USER

        # Skip auth for non-API paths and exempt paths
        path = request.url.path
        if not path.startswith(_PROTECTED_PREFIX) or path in _EXEMPT_PATHS:
            return await call_next(request)

        # Auth disabled — proceed with unauthenticated sentinel
        if not _auth_enabled():
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required. Include Authorization: Bearer <token>"},  # noqa: E501
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[len("Bearer "):]

        try:
            user = await decode_token(token)
            request.state.user = user
            _logger.debug("auth: %s (%s) → %s", user.username, user.role, path)
        except TokenExpiredError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired. Please sign in again."},
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        except TokenValidationError as exc:
            _logger.warning("auth: token validation failed for %s: %s", path, exc)
            # Check if this is a JWKS fetch failure (service unavailable)
            if "Cannot fetch JWKS" in str(exc):
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Authentication service unavailable. Please try again later."},  # noqa: E501
                )
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token."},
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )
        except Exception as exc:
            _logger.error("auth: unexpected error validating token: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication failed."},
            )

        return await call_next(request)
