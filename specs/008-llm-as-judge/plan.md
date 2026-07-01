# Implementation Plan: LLM-as-a-Judge Validation

**Branch**: `008-llm-as-judge` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-llm-as-judge/spec.md`

## Summary

Build an LLM-as-a-Judge validation pipeline as `adp.validation` — a structural pre-check (orphan/dangling-ref detection), four parallel LLM critics (standards, principles, pattern-fit, consistency) each grounded in ADP-SPEC-005 knowledge, deterministic gating against explicit thresholds, verdict storage, and human override with audit. Consumed by ADP-SPEC-003's operations router (`kind=validation`).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `langgraph>=0.2` (already in stack from ADP-SPEC-007); same LLM client as ADP-SPEC-006/007 (`httpx>=0.27`); `opentelemetry-sdk>=1.25` (already in stack); `asyncio.gather` for critic fan-out (no additional deps)  
**Storage**: `Verdict` stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); on human acceptance, verdict is optionally persisted to ADP-SPEC-002's design store as a design annotation; raw source text is NEVER stored  
**Testing**: pytest, pytest-asyncio; LLM critics mocked with `AsyncMock`; gating logic is pure Python (no mocks needed); zero live LLM calls in CI  
**Target Platform**: Python library sub-package (`adp.validation`) consumed by ADP-SPEC-003's API layer  
**Project Type**: Python library (async fan-out orchestration)  
**Performance Goals**: Operation handle within 2 seconds (NFR-001); full fan-out within 120 seconds for ≤500 elements (SC-003)  
**Constraints**: Deterministic gating — same scores + same thresholds → same decision, always (ART-X / QG-15); every finding cites a knowledge item (ART-VII / QG-12); structural check blocks LLM critics on failure

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-008 |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ Gating logic is pure Python (100% testable); critics mocked |
| QG-11 | ART-VI | Each critic emits span with inputs/knowledge refs/cost/latency | ✅ FR-007; one span per critic per job |
| QG-12 | ART-VII | Findings carry grounding citations with versions | ✅ FR-002; uncited findings are advisory-only; never block |
| QG-13 | ART-IX | Override writes audit entry with origin and actor | ✅ FR-006; override goes through ADP-SPEC-004 `write_audit_record` |
| QG-15 | ART-X | Validation gating is deterministic given critic scores | ✅ FR-004; `gate()` is a pure function — same inputs → same output always |
| QG-16 | ART-XI | Referential integrity; no orphan elements | ✅ FR-005; structural critic checks this before LLM critics run |

**ART-X note**: QG-15 is the primary article this spec implements. The `gate()` function takes `(findings: list[Finding], thresholds: GatingThreshold) → bool` and is a deterministic pure function. It MUST have no side effects and MUST be tested with fixed inputs.

**Constitution Alignment**: ART-II — Verdict is written to the ADP-SPEC-003 operation store; the design model is read-only during validation. ART-VIII — Human override is a consequential action via ADP-SPEC-003 confirmation router.

## Project Structure

### Documentation (this feature)

```text
specs/008-llm-as-judge/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — validation pipeline entities
├── contracts/
│   ├── orchestrator-contract.md  # Python orchestrator interface
│   └── critic-prompt-contract.md  # LLM prompt schemas per critic
├── quickstart.md        # Phase 1 — running and reviewing validation
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # ADP-SPEC-001 (unchanged)
    ├── models.py                 # ADP-SPEC-001 (unchanged)
    ├── store/                    # ADP-SPEC-002 (unchanged)
    ├── api/                      # ADP-SPEC-003 (updated: operations router wires validation)
    ├── authz/                    # ADP-SPEC-004 (unchanged)
    ├── knowledge/                # ADP-SPEC-005 (unchanged)
    ├── intake/                   # ADP-SPEC-006 (unchanged)
    ├── recommendation/           # ADP-SPEC-007 (unchanged)
    └── validation/
        ├── __init__.py           # Exports ValidationOrchestrator, Verdict, Finding
        ├── models.py             # Finding, Verdict, CriticOutput, GatingThreshold, ValidationJob
        ├── prompts.py            # LLM prompt templates: 4 critic prompts + scoring rubrics
        ├── critics.py            # 5 critic functions: structural + 4 LLM critics
        ├── aggregator.py         # aggregate(critic_outputs) → Verdict components
        ├── gate.py               # gate(findings, thresholds) → bool (pure, deterministic)
        ├── orchestrator.py       # ValidationOrchestrator — fan-out + aggregation + verdict
        └── telemetry.py          # Per-critic span emission (FR-007 / QG-11)

tests/
└── validation/
    ├── __init__.py
    ├── test_critics.py           # Individual critic tests (mocked LLM + knowledge)
    ├── test_gate.py              # Gating determinism tests (pure Python, no mocks)
    ├── test_aggregator.py        # Aggregation + composite score tests
    └── test_orchestrator.py      # Full pipeline tests (all mocked)
```

**Structure Decision**: New `adp.validation` sub-package. The `gate()` function in `gate.py` is a pure Python function — no classes, no side effects. This makes ART-X compliance straightforward to verify. Critics run with `asyncio.gather()` (simpler and testable) rather than LangGraph fan-out.
