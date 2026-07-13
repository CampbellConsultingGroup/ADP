"""Tests for the layout position router (T044b — ADP-SPEC-009).

Uses FastAPI TestClient — no Docker required; in-process store.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adp.api.routers import layouts


@pytest.fixture(autouse=True)
def _clear_layout_store() -> None:
    """Reset the in-process layout store between tests."""
    layouts._layout_store.clear()


@pytest.fixture()
def app() -> FastAPI:
    from adp.api.app import create_app
    return create_app()


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def architect_client(app: FastAPI) -> TestClient:
    """Override the role dependency to return 'architect'."""

    def _architect_role() -> str:
        return "architect"

    app.dependency_overrides[layouts._get_token_role] = _architect_role
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def viewer_client(app: FastAPI) -> TestClient:
    """Override the role dependency to return 'viewer'."""

    def _viewer_role() -> str:
        return "viewer"

    app.dependency_overrides[layouts._get_token_role] = _viewer_role
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.clear()


class TestGetLayout:
    def test_returns_empty_positions_for_new_design(self, client: TestClient) -> None:
        resp = client.get("/api/v1/designs/D-001/layout/container")
        assert resp.status_code == 200
        body = resp.json()
        assert body["design_id"] == "D-001"
        assert body["level"] == "container"
        assert body["positions"] == {}

    def test_returns_all_three_levels(self, client: TestClient) -> None:
        for level in ("context", "container", "component"):
            resp = client.get(f"/api/v1/designs/D-001/layout/{level}")
            assert resp.status_code == 200
            assert resp.json()["level"] == level


class TestSaveLayout:
    def test_save_then_get_returns_positions(self, architect_client: TestClient) -> None:
        positions = {"ELM-001": {"x": 120, "y": 80}, "ELM-002": {"x": 350, "y": 200}}
        put_resp = architect_client.put(
            "/api/v1/designs/D-001/layout/container",
            json={"positions": positions},
        )
        assert put_resp.status_code == 200

        get_resp = architect_client.get("/api/v1/designs/D-001/layout/container")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["positions"]["ELM-001"]["x"] == 120
        assert body["positions"]["ELM-001"]["y"] == 80

    def test_viewer_cannot_save_layout(self, viewer_client: TestClient) -> None:
        resp = viewer_client.put(
            "/api/v1/designs/D-001/layout/container",
            json={"positions": {"ELM-001": {"x": 0, "y": 0}}},
        )
        assert resp.status_code == 403

    def test_put_replaces_existing_layout(self, architect_client: TestClient) -> None:
        """PUT is idempotent and replaces the full layout for that level."""
        first = {"ELM-001": {"x": 10, "y": 20}}
        architect_client.put("/api/v1/designs/D-001/layout/container", json={"positions": first})

        second = {"ELM-002": {"x": 100, "y": 200}}
        architect_client.put("/api/v1/designs/D-001/layout/container", json={"positions": second})

        resp = architect_client.get("/api/v1/designs/D-001/layout/container")
        assert resp.json()["positions"] == second  # first layout replaced

    def test_layouts_are_isolated_per_level(self, architect_client: TestClient) -> None:
        architect_client.put(
            "/api/v1/designs/D-001/layout/container",
            json={"positions": {"ELM-001": {"x": 10, "y": 10}}},
        )
        # context level has no layout
        resp = architect_client.get("/api/v1/designs/D-001/layout/context")
        assert resp.json()["positions"] == {}


class TestThemeEndpoint:
    def test_get_c4_theme_returns_baseline(self, client: TestClient) -> None:
        resp = client.get("/api/v1/theme/c4")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locked"] is True
        assert "container" in body["styles"]
        # v1.0.1: container fill updated to #2874A6 (WCAG AA compliant, SC-005)
        assert body["styles"]["container"]["fill"] == "#2874A6"

    def test_theme_has_all_element_kinds(self, client: TestClient) -> None:
        resp = client.get("/api/v1/theme/c4")
        body = resp.json()
        for kind in ("person", "system", "container", "component"):
            assert kind in body["styles"], f"Missing kind '{kind}' in theme"

    def test_theme_has_relationship_style(self, client: TestClient) -> None:
        resp = client.get("/api/v1/theme/c4")
        body = resp.json()
        assert "relationship_style" in body
        assert body["relationship_style"]["stroke"] == "#707070"
