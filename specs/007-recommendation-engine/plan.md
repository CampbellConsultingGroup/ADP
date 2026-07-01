# Implementation Plan: AI Recommendation Engine

**Branch**: `007-recommendation-engine` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-recommendation-engine/spec.md`

## Summary

Build a five-step LangGraph orchestration pipeline that converts confirmed requirements into ranked, grounded `SolutionOption` records — retrieve relevant knowledge (ADP-SPEC-005), generate structured candidate options, analyze trade-offs per NFR and principle, rank, validate citations — and materialize design elements on explicit human acceptance. Implemented as `adp.recommendation` sub-package consumed by ADP-SPEC-003's operations router (`kind=recommendation`).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `langgraph>=0.2` (step orchestration with inspectable state), `langchain-core>=0.2` (Pydantic structured output tooling for LLM responses); same LLM client as ADP-SPEC-006 (`httpx>=0.27`, configurable endpoint); `opentelemetry-sdk>=1.25` (already in stack)  
**Storage**: `SolutionOption` records stored transiently in ADP-SPEC-003's in-process operation store (TTL 24h); accepted option materializes `Element`/`Relationship` records into ADP-SPEC-002 `DesignStore`; no additional database tables required  
**Testing**: pytest, pytest-asyncio; LLM calls mocked with `httpx.MockTransport`; LangGraph pipeline testable node-by-node with injected state; zero live LLM calls in CI  
**Target Platform**: Python library sub-package (`adp.recommendation`) consumed by ADP-SPEC-003's API layer  
**Project Type**: Python library (async orchestration pipeline)  
**Performance Goals**: Operation handle available within 2 seconds (NFR-001); recommendation results within 60 seconds for ≤ 15 requirements (SC-003)  
**Constraints**: Every step emits a telemetry span (QG-11); options without verified citations MUST be marked `advisory=True` (ART-VII / QG-12); element materialization only via explicit acceptance (QG-14); `satisfies` links required on all materialized elements (QG-16)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-007 |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ LangGraph nodes testable independently; LLM mocked |
| QG-11 | ART-VI | Each orchestration step emits span with inputs/knowledge refs/cost/latency | ✅ FR-006; five-step pipeline → five spans per job |
| QG-12 | ART-VII | AI recommendations carry grounding citations with versions | ✅ FR-003; options without citations flagged `advisory=True`; ADP-SPEC-003 citation gate enforced at confirmation |
| QG-13 | ART-IX | Model mutations write append-only audit entries with origin and actor | ✅ FR-004; element materialization writes `AuditEntry` via ADP-SPEC-004 |
| QG-14 | ART-VIII | Consequential actions require explicit, attributable human confirmation | ✅ FR-004; per-option acceptance via ADP-SPEC-003 confirmation router; `proposal_id` = `option_id` |
| QG-16 | ART-XI | Elements must trace to requirements they satisfy | ✅ FR-005; materialized elements carry `satisfies` links from the accepted option |

**ART-II compliance**: The recommendation engine proposes elements; it does not bypass the canonical model. Accepted elements are written through `DesignStore.save()` (ADP-SPEC-002) and validated against ADP-SPEC-001 schema. No parallel model representation is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/007-recommendation-engine/
├── plan.md               # This file
├── research.md           # Phase 0 — decisions and rationale
├── data-model.md         # Phase 1 — pipeline entities
├── contracts/
│   ├── orchestrator-contract.md  # Python orchestrator interface
│   └── llm-prompt-contract.md    # LLM prompt schemas
├── quickstart.md         # Phase 1 — requesting and accepting recommendations
├── checklists/
│   └── requirements.md   # Spec quality checklist
└── tasks.md              # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
└── adp/
    ├── __init__.py               # ADP-SPEC-001 (unchanged)
    ├── models.py                 # ADP-SPEC-001 (unchanged)
    ├── store/                    # ADP-SPEC-002 (unchanged)
    ├── api/                      # ADP-SPEC-003 (updated: operations router wires recommendation)
    ├── authz/                    # ADP-SPEC-004 (unchanged)
    ├── knowledge/                # ADP-SPEC-005 (unchanged)
    ├── intake/                   # ADP-SPEC-006 (unchanged)
    └── recommendation/
        ├── __init__.py           # Exports RecommendationOrchestrator, SolutionOption
        ├── models.py             # SolutionOption, TradeOffEntry, RecommendationJob,
        │                         #   RecommendationStep (telemetry), ProposedElement
        ├── prompts.py            # LLM prompt templates: generation + trade-off analysis
        ├── steps.py              # Five step functions: retrieve, generate, analyze_tradeoffs,
        │                         #   rank, validate_citations
        ├── orchestrator.py       # RecommendationOrchestrator: LangGraph StateGraph
        │                         #   wrapping the five steps + materialization helpers
        └── telemetry.py          # Step span emission (FR-006 / QG-11)

tests/
└── recommendation/
    ├── __init__.py
    ├── test_steps.py             # Individual step unit tests (mocked LLM + knowledge)
    ├── test_orchestrator.py      # Full pipeline integration tests (all mocked)
    └── test_materialization.py   # Element materialization + audit + satisfies links
```

**Structure Decision**: New `adp.recommendation` sub-package. The orchestrator is invoked by ADP-SPEC-003 when `kind=recommendation`. Acceptance routes through ADP-SPEC-003's confirmation endpoint with `option_id` in the `ConfirmationPayload` (same extension used by ADP-SPEC-006 intake).
