# Research: LLM-as-a-Judge Validation

**Branch**: `008-llm-as-judge` | **Date**: 2026-07-01  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: Fan-out with `asyncio.gather` Rather Than LangGraph Parallel Nodes

**Decision**: The four LLM critics run concurrently using `asyncio.gather()`, not LangGraph's conditional edges for parallel branching.

**Rationale**: LangGraph's fan-out requires conditional edges and custom state merging that adds significant boilerplate for a fan-out/fan-in pattern. `asyncio.gather()` is simpler, directly testable (each coroutine can be called independently), and produces the same concurrency model. The structural critic still runs first and can short-circuit the LLM critics via a simple conditional.

**Alternatives considered**:
- LangGraph parallel branches — correct but complex state merging; deferred to v2 if multi-stage pipelines emerge
- Sequential critics — simpler but violates NFR-001 latency target (critics would run 4x slower)

---

## Decision 2: Structural Critic Runs Before LLM Critics and Can Block Them

**Decision**: The structural critic (orphan detection + dangling-reference check) runs synchronously before `asyncio.gather()` dispatches the LLM critics. If structural failures are found, LLM critics are skipped and the verdict fails immediately.

**Rationale**: Structural integrity is a precondition for meaningful semantic validation. Running LLM critics on a structurally broken design wastes tokens and produces misleading results. The structural check is a fast, deterministic, pure Python function — no LLM needed.

---

## Decision 3: `gate()` as a Pure Function (ART-X Enforcement)

**Decision**: `gate(findings: list[Finding], thresholds: GatingThreshold) -> bool` is a pure function in `gate.py`. It has no side effects, no randomness, and no external calls. Identical inputs always produce identical output.

**Rationale**: ART-X / QG-15 is the governing article. The only way to guarantee determinism is to isolate gating as a pure function. Tests verify this by calling `gate()` twice with the same arguments and asserting equality.

**Gating algorithm**:
```
critical_count = count(f for f in findings if f.severity == "critical")
major_count = count(f for f in findings if f.severity == "major")
minor_count = count(f for f in findings if f.severity == "minor")
# advisory findings never count toward blocking

passes = (
    critical_count <= thresholds.max_critical AND
    major_count <= thresholds.max_major AND
    minor_count <= thresholds.max_minor
)
```

---

## Decision 4: Scoring Rubric in Each Critic System Prompt (Calibration)

**Decision**: Each critic's system prompt includes an explicit 5-point scoring rubric (1.0 / 0.75 / 0.5 / 0.25 / 0.0) with concrete descriptions for each score level. Combined with `temperature=0`, this keeps scores stable across model versions.

**Example rubric for standards critic**:
```
Score 1.0: Fully compliant — no deviations from any applicable standard
Score 0.75: Minor deviation acceptable — one non-critical deviation with mitigatable risk
Score 0.5: Significant gap — one major deviation that requires review
Score 0.25: Multiple gaps — two or more major deviations
Score 0.0: Clear non-compliance — explicit violation of a mandatory standard with citation
```

**Rationale**: Without rubrics, LLM scoring is subjective and drift-prone across model versions. Explicit rubrics reduce variance significantly. Combined with deterministic gating (Decision 3), a score drift that doesn't cross a threshold boundary has no effect on the gate decision.

---

## Decision 5: Finding Severity from Score + Rubric Anchors

**Decision**: Each LLM critic produces a score AND a list of findings. The mapping from score to finding severity uses fixed anchors:
- Score 0.0 → findings are `critical`
- Score 0.25 → findings are `major`
- Score 0.5 → findings are `major`
- Score 0.75 → findings are `minor`
- Score 1.0 → no findings generated

**Rationale**: Using score ranges rather than prompting the LLM to self-classify severity reduces severity inconsistency. The critic only needs to produce findings with descriptions and citations; severity is inferred deterministically from the score.

---

## Decision 6: Composite Score Calculation

**Decision**: `composite_score = mean(critic.score for critic in critic_outputs where critic.score is not None)`. Structural check does not contribute a score (it is pass/fail only). Critics that fail to run contribute `None` and are excluded from the mean; their absence is noted in the verdict metadata.

**Rationale**: Equal-weight mean is the simplest fair aggregation. Weighted aggregation is deferred to v2. If all LLM critics fail to run (e.g., LLM endpoint down), the composite score is `None` and the verdict is `indeterminate` (not `pass` or `fail`).

---

## Decision 7: Verdict Status State Machine

**Decision**: `Verdict.status` is one of `pass`, `fail`, `indeterminate`, `overridden`. State transitions:
- Initial: `pass` or `fail` or `indeterminate` (set by gating)
- `fail` → `overridden` (by human override with justification)
- `pass` → never overridden (no need; if architect wants to re-validate they submit a new job)
- `indeterminate` → cannot be overridden (must be re-run once LLM endpoint is available)

**Rationale**: Allowing override of only `fail` verdicts prevents misuse. `indeterminate` cannot be overridden because the verdict is unknown, not failing — re-running is the correct action.

---

## Decision 8: ADP-SPEC-003 Integration

**Decision**: Same pattern as ADP-SPEC-006/007 — `POST /api/v1/operations` with `kind=validation` dispatches the orchestrator as a background task. Override goes through `POST /api/v1/operations/{id}/confirm` with the verdict status in the `ConfirmationPayload`. `citations_present` is set to `True` if at least one finding has a verified citation (consistent with the ART-VII bridge established in ADP-SPEC-006/007).

---

## Decision 9: Per-Critic Telemetry Span Naming

| Critic | Span Name |
|---|---|
| Structural | `adp.validation.structural` |
| Standards | `adp.validation.standards` |
| Principles | `adp.validation.principles` |
| Pattern-fit | `adp.validation.pattern_fit` |
| Consistency | `adp.validation.consistency` |
| Aggregation | `adp.validation.aggregate` (no LLM; cost=0) |
| Gating | `adp.validation.gate` (no LLM; cost=0) |
