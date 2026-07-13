"""Performance timing tests for SC-002 and SC-003 (T038)."""

from __future__ import annotations

import time

from adp.theme.loader import ThemeLoader


def test_sc003_theme_validation_under_2s():
    """SC-003: theme validation must complete in ≤ 2 seconds."""
    loader = ThemeLoader()
    t0 = time.perf_counter()
    loader.load_and_validate()
    elapsed = time.perf_counter() - t0
    assert elapsed <= 2.0, f"SC-003 violated: validation took {elapsed:.3f}s (limit 2s)"
