"""ADP-blp.27: one actor lookup for audit and log lines."""

from __future__ import annotations

from types import SimpleNamespace

from adp.auth.actor import actor_of
from adp.auth.models import UNAUTHENTICATED_USER, AuthenticatedUser
from adp.authz.roles import PersonaRole


def _request(user, headers=None):
    return SimpleNamespace(state=SimpleNamespace(user=user), headers=headers or {})


def test_signed_in_user_wins_over_the_header():
    user = AuthenticatedUser(
        sub="s", username="alice", email="a@x", role=PersonaRole.REVIEWER, groups=[]
    )
    assert actor_of(_request(user, {"X-Actor": "mallory"})) == "alice"


def test_header_then_default_when_auth_is_off():
    assert actor_of(_request(UNAUTHENTICATED_USER, {"X-Actor": "seed-script"})) == "seed-script"
    assert actor_of(_request(UNAUTHENTICATED_USER)) == "architect"
    assert actor_of(_request(UNAUTHENTICATED_USER), default="unknown") == "unknown"


def test_request_with_no_user_set():
    assert actor_of(SimpleNamespace(state=SimpleNamespace(), headers={})) == "architect"


def test_export_records_the_signed_in_user():
    from adp.api.routers.export_router import _get_actor

    user = AuthenticatedUser(
        sub="s", username="alice", email="a@x", role=PersonaRole.ENTERPRISE_ARCHITECT, groups=[]
    )
    assert _get_actor(_request(user)) == "alice"
    assert _get_actor(_request(UNAUTHENTICATED_USER)) == "unknown"
