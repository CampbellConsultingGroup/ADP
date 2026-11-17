"""Who is making this request, for audit and log lines (ADP-blp.27).

Twenty routers each carried their own copy of this lookup. The rule: the signed-in user's
username; with authentication switched off (local development, tests) the ``X-Actor`` header,
else a default. Routers keep their ``_get_actor`` name and call this.
"""

from __future__ import annotations

from fastapi import Request

from adp.auth.models import UNAUTHENTICATED_USER

DEFAULT_ACTOR = "architect"


def actor_of(request: Request, default: str = DEFAULT_ACTOR) -> str:
    user = getattr(request.state, "user", UNAUTHENTICATED_USER)
    if user is not UNAUTHENTICATED_USER:
        return str(user.username)
    return request.headers.get("X-Actor", default)
