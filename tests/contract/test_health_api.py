"""Contract tests for GET /health, GET /metrics, and X-Trace-ID propagation (T007, T016-T018)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from adp.api.app import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "version" in body
    assert body["status"] in ("healthy", "unhealthy")


def test_metrics_endpoint_has_required_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "adp_request_total" in text
    assert "adp_error_total" in text
    assert "adp_request_latency_seconds" in text
    assert "adp_active_requests" in text


def test_request_counter_increments(client):
    """After making requests, adp_request_total must be > 0 (FR-004)."""
    client.get("/health")
    client.get("/health")
    resp = client.get("/metrics")
    text = resp.text

    # Find any adp_request_total line with a non-zero value
    # Prometheus counters are process-wide — other tests may have already incremented them
    total = 0.0
    for line in text.splitlines():
        if line.startswith("adp_request_total") and not line.startswith("#"):
            try:
                total += float(line.split()[-1])
            except (ValueError, IndexError):
                pass

    assert total > 0, (
        f"adp_request_total must be > 0 after making requests; found {total}"
    )


def test_x_trace_id_header_propagated(client):
    resp = client.get("/health", headers={"X-Trace-ID": "my-trace-abc"})
    assert resp.headers.get("X-Trace-ID") == "my-trace-abc"


def test_x_trace_id_generated_when_absent(client):
    resp = client.get("/health")
    trace_id = resp.headers.get("X-Trace-ID")
    assert trace_id is not None
    assert len(trace_id) > 0
