"""Root conftest — sets environment for all tests (ADP-SPEC-026).

ADP_AUTH_ENABLED=false disables Keycloak token validation so tests can run
without a live Keycloak instance. Individual auth tests opt back in via
monkeypatch.setenv("ADP_AUTH_ENABLED", "true").
"""

import os

# Disable auth for the entire test suite unless overridden per-test
os.environ.setdefault("ADP_AUTH_ENABLED", "false")
