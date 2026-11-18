"""ADP-blp.28: tests share one app. These check the sharing cannot leak between tests."""

from __future__ import annotations

from adp.api.app import create_app


def _dependency() -> None:
    return None


def test_each_call_returns_the_app_clean():
    app = create_app()
    app.dependency_overrides[_dependency] = lambda: "set by a test"
    app.state.something = 1

    again = create_app()
    assert again is app  # the saving: its routes are analysed once for the whole run
    assert again.dependency_overrides == {}
    assert not hasattr(again.state, "something")


def test_a_different_configuration_gets_its_own_app(monkeypatch):
    default = create_app()
    monkeypatch.setenv("ADP_MAX_REQUEST_BYTES", "123")
    assert create_app() is not default


def test_an_app_a_test_added_a_route_to_is_not_reused(request):
    import tests.conftest as root

    app = create_app()

    @app.get("/only-for-this-test")
    def _extra() -> dict:
        return {}

    # What the autouse fixture does after every test.
    for key, shared in list(root._shared_apps.items()):
        if root._app_shape(shared) != root._shape.get(id(shared)):
            del root._shared_apps[key]
    fresh = create_app()
    assert fresh is not app
    assert all(getattr(r, "path", None) != "/only-for-this-test" for r in fresh.router.routes)


def test_the_real_factory_is_still_reachable():
    # For a test that must build its own app.
    assert create_app.__wrapped__() is not create_app()
