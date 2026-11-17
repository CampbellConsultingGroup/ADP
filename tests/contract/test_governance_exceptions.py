"""ADP-blp.19: the Governance exceptions report covers every design, not one page."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient


def _design(n: int, severity: str):
    return SimpleNamespace(
        id=f"DSN-{n:03d}",
        title=f"Design {n}",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        findings=[
            SimpleNamespace(id=f"F-{n}", summary="s", severity=severity, source="judge")
        ],
    )


def test_exceptions_cover_every_design():
    from adp.api.app import create_app
    from adp.api.routers import governance

    designs = [_design(n, "critical" if n % 2 else "warning") for n in range(1, 61)]
    designs.append(_design(99, "info"))  # not an exception
    calls: list[dict] = []

    class Store:
        async def list_all(self, page: int = 1, page_size: int | None = 50, status=None):
            calls.append({"page": page, "page_size": page_size})
            return designs if page_size is None else designs[:page_size]

    app = create_app()

    async def _store():
        return Store()

    app.dependency_overrides[governance._get_design_store] = _store
    resp = TestClient(app).get("/api/v1/governance/exceptions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert calls == [{"page": 1, "page_size": None}]
    assert body["total"] == 60  # was capped at the first 50 designs
    assert body["exceptions"][0]["severity"] == "FAIL"
