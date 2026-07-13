"""Result and report types for the eval harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseResult:
    """Outcome of a single golden case."""

    case_id: str
    kind: str  # "judge" | "grounding"
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalReport:
    """Aggregate result of an eval suite run."""

    results: list[CaseResult] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True when every case passed."""
        return all(r.passed for r in self.results)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def failed(self) -> list[CaseResult]:
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "total": self.total,
            "failed": len(self.failed),
            "metrics": self.metrics,
            "results": [
                {
                    "case_id": r.case_id,
                    "kind": r.kind,
                    "passed": r.passed,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }
