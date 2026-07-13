"""Pure scoring functions for eval metrics.

Kept free of I/O and product imports so they are trivially unit-testable and
reusable for both the golden-fixture run and a future live-LLM run.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GroundingScore:
    """Precision/recall of an option's *retained* (resolvable) citations against
    the expected relevant set.
    """

    precision: float
    recall: float

    @property
    def f1(self) -> float:
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * self.precision * self.recall / (self.precision + self.recall)


def grounding_score(retained: set[str], expected: set[str]) -> GroundingScore:
    """Precision/recall of retained citation ids vs. the expected relevant ids.

    precision — of the citations kept, how many were expected (no spurious cites).
    recall    — of the expected citations, how many were kept (full grounding).
    With no expected set, recall is defined as 1.0 (nothing was required).
    With no retained citations, precision is defined as 1.0 (nothing spurious).
    """
    hits = len(retained & expected)
    precision = 1.0 if not retained else hits / len(retained)
    recall = 1.0 if not expected else hits / len(expected)
    return GroundingScore(precision=precision, recall=recall)


def verdict_agrees(actual: str, expected: str) -> bool:
    """True when the judge's gate decision matches the labeled expectation."""
    return actual == expected


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 1.0
