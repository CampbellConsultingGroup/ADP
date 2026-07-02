"""Canonical telemetry contract constants for ADP-SPEC-012.

ALL span attribute names, log field names, and metric names MUST be imported
from this file. Hard-coded strings are prohibited (enforces consistent naming
across adp.intake, adp.recommendation, adp.validation, and future specs).

This module has ZERO imports from adp.* to prevent circular imports.
"""

# ── AI step span attributes (FR-003 / QG-11) ─────────────────────────────────
SPAN_ATTR_STEP_NAME = "adp.step_name"
SPAN_ATTR_INPUT_TOKENS = "adp.input_tokens"
SPAN_ATTR_OUTPUT_TOKENS = "adp.output_tokens"
SPAN_ATTR_ESTIMATED_COST_USD = "adp.estimated_cost_usd"
SPAN_ATTR_LATENCY_MS = "adp.latency_ms"
SPAN_ATTR_KNOWLEDGE_ITEM_IDS = "adp.knowledge_item_ids"  # JSON-serialized list
SPAN_ATTR_DESIGN_ID = "adp.design_id"
SPAN_ATTR_OPERATION_ID = "adp.operation_id"

# OTel semantic conventions for errors
SPAN_ATTR_ERROR_TYPE = "error.type"
SPAN_ATTR_ERROR_MSG = "error.message"

# OTel semantic conventions for HTTP service spans
SPAN_ATTR_HTTP_METHOD = "http.method"
SPAN_ATTR_HTTP_ROUTE = "http.route"
SPAN_ATTR_HTTP_STATUS = "http.status_code"

# ── Log field names (FR-001 / QG-10) ─────────────────────────────────────────
LOG_FIELD_TRACE_ID = "trace_id"
LOG_FIELD_EVENT = "event"
LOG_FIELD_LEVEL = "level"
LOG_FIELD_TIMESTAMP = "timestamp"
LOG_FIELD_MODULE = "module"

# ── Prometheus metric names (FR-004) ─────────────────────────────────────────
METRIC_REQUEST_TOTAL = "adp_request_total"
METRIC_ERROR_TOTAL = "adp_error_total"
METRIC_REQUEST_LATENCY = "adp_request_latency_seconds"
METRIC_SATURATION = "adp_active_requests"

# AI step cost/token metrics
METRIC_AI_TOKENS_INPUT = "adp_ai_input_tokens_total"
METRIC_AI_TOKENS_OUTPUT = "adp_ai_output_tokens_total"
METRIC_AI_COST_USD = "adp_ai_estimated_cost_usd_total"

# ── Span attribute value limits ───────────────────────────────────────────────
MAX_SPAN_ATTR_LEN: int = 1024  # string attributes truncated at this length
MAX_ERROR_MSG_LEN: int = 256   # error.message truncated more aggressively
