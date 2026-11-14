"""Cardinality shorthand grammar for EA patterns (934, data-model.md).

Accepted forms: ``N``, ``N..M``, ``N..*``, optionally followed by ``per <role>``.
``N``/``M`` are non-negative integers with ``M >= max(N, 1)``; a bare ``0`` is
rejected because its maximum would be zero.
"""

from __future__ import annotations

import re

_ROLE = r"[a-z][a-z0-9_]{0,39}"
_PATTERN = re.compile(rf"^(\d+)(?:\.\.(\d+|\*))?(?:\s+per\s+({_ROLE}))?$")


class CardinalityError(ValueError):
    """Raised for text that is not a valid cardinality shorthand."""


def parse_cardinality(text: str) -> tuple[int, int | None, str | None]:
    """Parse shorthand into ``(min, max, per)``; ``max is None`` means unbounded."""
    m = _PATTERN.match(text.strip())
    if not m:
        raise CardinalityError(
            f"invalid cardinality {text!r}; expected e.g. '1', '0..1', '2..*', '1 per role'"
        )
    lo = int(m.group(1))
    hi_raw = m.group(2)
    if hi_raw is None:
        hi: int | None = lo
    elif hi_raw == "*":
        hi = None
    else:
        hi = int(hi_raw)
    if hi is not None and (hi < 1 or hi < lo):
        raise CardinalityError(f"invalid cardinality {text!r}; maximum must be >= 1 and >= minimum")
    return lo, hi, m.group(3)


def format_cardinality(lo: int, hi: int | None, per: str | None) -> str:
    """Inverse of :func:`parse_cardinality` — always the shorthand form."""
    if hi is None:
        core = f"{lo}..*"
    elif hi == lo:
        core = str(lo)
    else:
        core = f"{lo}..{hi}"
    return f"{core} per {per}" if per else core
