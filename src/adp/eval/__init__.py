"""ADP AI-quality evaluation harness (ADP-SPEC-004 follow-up / recommendation review).

Measures the trustworthiness of the two AI decision surfaces that gate real work:

  * the LLM-as-Judge **gate** (does a labeled design pass/fail as expected?), and
  * recommendation **grounding** (are an option's citations valid, and do they
    match the expected knowledge?).

The harness drives the *real* product code — ``adp.validation.gate.gate`` and
``adp.recommendation.steps.validate_citations_step`` — against a golden fixture
set, so it is a regression guard on the deterministic decision logic and needs
no live LLM in CI. A live-LLM quality run scores the same metrics on real
pipeline output; see ``docs`` and ``run_suite``'s extension points.
"""

from adp.eval.models import CaseResult, EvalReport
from adp.eval.runner import load_cases, run_suite

__all__ = ["CaseResult", "EvalReport", "load_cases", "run_suite"]
