"""The shared router helpers (ADP-blp.27)."""

from __future__ import annotations

import sys
import types

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from adp.api.common import named_path_param, session_dependency
from adp.compliance.models import MappingTargetType
from adp.strategy import router as srouter


class _Session:
    closed = False

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True


def _fake_store(monkeypatch, name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.opened = []  # type: ignore[attr-defined]

    def _get_session_factory():
        def factory() -> _Session:
            session = _Session()
            module.opened.append(session)  # type: ignore[attr-defined]
            return session

        return factory

    module._get_session_factory = _get_session_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, module)
    return module


def test_session_dependency_opens_and_closes_a_session_per_request(monkeypatch) -> None:
    store = _fake_store(monkeypatch, "adp_test_fake_store")
    get_session = session_dependency("adp_test_fake_store")
    app = FastAPI()

    @app.get("/x")
    async def x(session: _Session = Depends(get_session)) -> dict[str, bool]:
        return {"open": not session.closed}

    assert TestClient(app).get("/x").json() == {"open": True}
    assert [s.closed for s in store.opened] == [True]


def test_each_session_dependency_is_its_own_override_key(monkeypatch) -> None:
    _fake_store(monkeypatch, "adp_test_fake_store")
    first = session_dependency("adp_test_fake_store")
    second = session_dependency("adp_test_fake_store")
    app = FastAPI()

    @app.get("/x")
    async def x(a: object = Depends(first), b: object = Depends(second)) -> dict[str, str]:
        return {"a": str(a), "b": type(b).__name__}

    app.dependency_overrides[first] = lambda: "overridden"
    assert TestClient(app).get("/x").json() == {"a": "overridden", "b": "_Session"}


def test_named_path_param_publishes_the_specific_name() -> None:
    async def handler(owner_id: str, target_id: str, limit: int = 5) -> dict[str, object]:
        return {"owner": owner_id, "target": target_id, "limit": limit}

    router = APIRouter()
    router.add_api_route(
        "/owners/{owner_id}/widgets/{widget_id}",
        named_path_param(handler, "target_id", "widget_id"),
        methods=["GET"],
        name="get_widget",
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    assert client.get("/owners/o1/widgets/w9?limit=2").json() == {
        "owner": "o1", "target": "w9", "limit": 2,
    }
    params = app.openapi()["paths"]["/owners/{owner_id}/widgets/{widget_id}"]["get"]["parameters"]
    assert [p["name"] for p in params] == ["owner_id", "widget_id", "limit"]
    assert client.get("/owners/o1/widgets/w9?limit=nope").status_code == 422


def test_initiative_mapping_routes_cover_every_entity_target() -> None:
    routed = {route[0] for route in srouter._INITIATIVE_MAPPING_ROUTES}
    assert routed == set(MappingTargetType) - {MappingTargetType.ORGANIZATION}

    names = {route.name for route in srouter.router.routes}
    for target_type in MappingTargetType:
        assert f"link_initiative_{target_type.value}_mapping" in names
        assert f"unlink_initiative_{target_type.value}_mapping" in names
