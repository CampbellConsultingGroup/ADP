"""CLI entry point for the eval harness: ``adp-eval`` / ``python -m adp.eval``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from adp.eval.models import EvalReport
from adp.eval.runner import run_suite


def _print_human(report: EvalReport) -> None:
    for r in report.results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"  [{mark}] {r.kind:9} {r.case_id}")
        if not r.passed:
            print(f"         {r.detail}")
    print()
    print("Metrics:")
    for name, value in report.metrics.items():
        print(f"  {name:28} {value:.3f}")
    print()
    status = "PASSED" if report.passed else "FAILED"
    print(f"{status}: {report.total - len(report.failed)}/{report.total} cases passed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adp-eval",
        description="Run the ADP AI-quality eval harness (judge gate + recommendation grounding).",
    )
    parser.add_argument(
        "--evals-dir", default="evals", help="Directory of golden case YAML files (default: evals)"
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Exit non-zero if any case fails (use in CI)",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(run_suite(args.evals_dir))

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_human(report)

    if args.gate and not report.passed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
