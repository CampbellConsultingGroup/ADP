"""ADP-blp.62: the caller's role and granted actions, from the server's own permission table."""

from __future__ import annotations

from fastapi.testclient import TestClient

from adp.auth.deps import get_current_user
from adp.auth.models import AuthenticatedUser
from adp.authz.permissions import PERMISSION_GRANTS, PERMISSIONS_VERSION
from adp.authz.roles import ActionType, PersonaRole


def _client(role: PersonaRole) -> TestClient:
    from adp.api.app import create_app

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        sub="u", username="u", email="u@localhost", role=role, groups=[]
    )
    return TestClient(app)


def test_permissions_match_the_grant_table_for_every_role():
    for role in PersonaRole:
        body = _client(role).get("/api/v1/auth/permissions").json()
        assert body["role"] == role.value
        assert body["permissions_version"] == PERMISSIONS_VERSION
        assert set(body["actions"]) == {a.value for a in PERMISSION_GRANTS.get(role, frozenset())}
        assert body["actions"] == sorted(body["actions"])


def test_reviewer_cannot_write_but_an_architect_can():
    reviewer = _client(PersonaRole.REVIEWER).get("/api/v1/auth/permissions").json()["actions"]
    architect = _client(PersonaRole.SOLUTION_ARCHITECT).get("/api/v1/auth/permissions").json()
    assert ActionType.WRITE_BUSINESS_ARCH.value not in reviewer
    assert ActionType.WRITE_BUSINESS_ARCH.value in architect["actions"]


def test_estate_counts_come_from_one_query():
    """ADP-blp.39: the Overview page's totals without downloading six collections."""
    from unittest.mock import AsyncMock, MagicMock

    from adp.api.app import create_app
    from adp.api.deps import get_kb_session

    row = {
        "capabilities": 40, "value_streams": 4, "domains": 9, "technical_capabilities": 12,
        "knowledge_items": 31, "integrations": None,
    }
    result = MagicMock()
    result.mappings.return_value.one.return_value = row
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    async def _session():
        yield session

    app = create_app()
    app.dependency_overrides[get_kb_session] = _session
    body = TestClient(app).get("/api/v1/portfolio/counts").json()
    assert body == {**row, "integrations": 0}
    assert session.execute.await_count == 1
