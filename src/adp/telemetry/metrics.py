"""Prometheus metrics for ADP services (ADP-SPEC-012 FR-004).

All metric names are imported from adp.telemetry.contract (no hard-coded strings).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

from adp.telemetry.contract import (
    METRIC_AI_COST_USD,
    METRIC_AI_TOKENS_INPUT,
    METRIC_AI_TOKENS_OUTPUT,
    METRIC_ERROR_TOTAL,
    METRIC_REQUEST_LATENCY,
    METRIC_REQUEST_TOTAL,
    METRIC_SATURATION,
)

REQUEST_COUNTER = Counter(
    METRIC_REQUEST_TOTAL,
    "Total number of HTTP requests received",
    ["method", "route", "status"],
)

ERROR_COUNTER = Counter(
    METRIC_ERROR_TOTAL,
    "Total number of HTTP error responses (4xx/5xx)",
    ["route"],
)

REQUEST_LATENCY = Histogram(
    METRIC_REQUEST_LATENCY,
    "HTTP request latency in seconds",
    ["route"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_REQUESTS = Gauge(
    METRIC_SATURATION,
    "Number of HTTP requests currently being processed",
)

AI_INPUT_TOKENS = Counter(
    METRIC_AI_TOKENS_INPUT,
    "Total AI input tokens consumed across all steps",
    ["step"],
)

AI_OUTPUT_TOKENS = Counter(
    METRIC_AI_TOKENS_OUTPUT,
    "Total AI output tokens produced across all steps",
    ["step"],
)

AI_COST = Counter(
    METRIC_AI_COST_USD,
    "Total estimated AI cost in USD across all steps",
)
