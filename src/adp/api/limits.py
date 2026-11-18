"""Request limits: body size and LLM call rate (ADP-blp.5).

Two cheap protections that were missing entirely:

* A cap on request body size, for every route. Free-text bodies (chat messages, intake text,
  SVG for export, design import) were unbounded, so one large POST could exhaust memory or run
  up a model bill. ``ADP_MAX_REQUEST_BYTES`` (default 2 MiB); 0 turns it off.

* A per-user rate limit on the routes that call the model. Chat is granted to every role, so
  any signed-in user could loop requests. ``ADP_LLM_RATE_LIMIT_PER_MINUTE`` (default 30);
  0 turns it off.

The rate limit is counted per worker process, in memory: with two workers a user can reach
twice the configured number. That is acceptable for stopping a runaway loop; a shared store
would be needed for an exact quota.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_logger = logging.getLogger("adp.api.limits")

DEFAULT_MAX_REQUEST_BYTES = 2 * 1024 * 1024
DEFAULT_LLM_RATE_PER_MINUTE = 30
_WINDOW_SECONDS = 60.0

# POST routes that start a model call.
_LLM_ROUTE = re.compile(
    r"^/api/v1/("
    r"chat/conversations/[^/]+/messages"
    r"|designs/[^/]+/(intake|recommend|validate)"
    r"|business/capabilities/(?:[^/]+/)?agent-review"
    r")$"
)


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        _logger.warning("%s=%r is not a number; using %d", name, raw, default)
        return default


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Refuse a request whose body is larger than the limit with 413.

    Checks the Content-Length header first, then counts the bytes actually received, so a
    chunked upload with no declared length is stopped as well.
    """

    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self._max_bytes = max_bytes

    def _limit(self) -> int:
        if self._max_bytes is not None:
            return self._max_bytes
        return _int_env("ADP_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = self._limit()
        if scope["type"] != "http" or limit <= 0:
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > limit:
                    await self._reject(send, limit)
                    return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(send, limit)

    @staticmethod
    async def _reject(send: Send, limit: int) -> None:
        body = (
            b'{"detail":"Request body is too large (limit ' + str(limit).encode() + b' bytes)."}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


class RateLimiter:
    """Sliding one-minute window per key. One instance per application."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, now: float | None = None) -> float | None:
        """Record a call. Returns None when allowed, else the seconds until a slot frees up."""
        now = time.monotonic() if now is None else now
        hits = self._hits[key]
        while hits and now - hits[0] >= _WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return _WINDOW_SECONDS - (now - hits[0])
        hits.append(now)
        return None


def is_llm_route(method: str, path: str) -> bool:
    return method == "POST" and _LLM_ROUTE.match(path) is not None


async def enforce_llm_rate_limit(request: Request) -> None:
    """App-level dependency: 429 when one user starts too many model calls in a minute."""
    if not is_llm_route(request.method, request.url.path):
        return
    limit = _int_env("ADP_LLM_RATE_LIMIT_PER_MINUTE", DEFAULT_LLM_RATE_PER_MINUTE)
    if limit <= 0:
        return
    limiter = getattr(request.app.state, "llm_rate_limiter", None)
    if limiter is None:
        limiter = request.app.state.llm_rate_limiter = RateLimiter()
    user = getattr(request.state, "user", None)
    key = getattr(user, "sub", None) or (request.client.host if request.client else "anonymous")
    retry_after = limiter.check(key, limit)
    if retry_after is not None:
        _logger.warning("llm rate limit reached for user %s on %s", key, request.url.path)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many AI requests: the limit is {limit} per minute. "
                f"Try again in {int(retry_after) + 1} seconds."
            ),
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


async def refresh_llm_settings(request: Request) -> None:
    """App-level dependency (ADP-blp.13): before a request that calls a model, read the model
    choices from the database, so a change made through another worker applies here too."""
    if is_llm_route(request.method, request.url.path):
        from adp.llm import settings as llm_settings

        await llm_settings.refresh()
