# Implementation Plan: Requirements Intake & Normalization

**Branch**: `006-requirements-intake` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-requirements-intake/spec.md`

## Summary

Build the AI-assisted requirements extraction pipeline as `adp.intake` — an async orchestrator that accepts raw text submissions, sends them to a configurable OpenAI-compatible LLM endpoint for structured extraction, validates each proposal against the canonical schema, flags hallucinations via source-excerpt verification, proposes knowledge-base links, emits mandatory telemetry spans, and surfaces proposals for human confirmation before any requirement enters the model. Consumed by ADP-SPEC-003's operations router (kind=`intake`).

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: `httpx>=0.27` (async HTTP client for configurable LLM endpoint), `opentelemetry-sdk>=1.25` (telemetry span emission per ADP-SPEC-012), `tiktoken>=0.7` (token counting for cost estimation); existing stack: Pydantic v2, SQLAlchemy 2 async, FastAPI (ADP-SPEC-003)  
**Storage**: `ExtractedProposal` records stored transiently in-memory (same in-process store as ADP-SPEC-003 operation results, TTL 24h); confirmed requirements written to the canonical store via ADP-SPEC-002 `DesignStore`; raw source text is NEVER persisted  
**Testing**: pytest, pytest-asyncio; LLM endpoint mocked with `httpx.MockTransport`; zero live LLM calls in CI  
**Target Platform**: Python library sub-package (`adp.intake`) consumed by ADP-SPEC-003's API layer  
**Project Type**: Python library (async pipeline orchestrator)  
**Performance Goals**: Operation handle returned within 2 seconds of submission (NFR-001); extraction completes within 60 seconds for ≤ 5,000-character inputs (SC-003)  
**Constraints**: Configurable LLM endpoint (supports on-premise for data residency); source text NEVER stored; raw text NOT retained after extraction; per-proposal confirmation gate mandatory (FR-003); one span per job (FR-006)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Article(s) | Requirement | Status |
|------|-----------|-------------|--------|
| QG-01 | ART-I, ART-XVI | PR references approved spec/task IDs | ✅ All tasks will reference ADP-SPEC-006 |
| QG-03 | ART-III, ART-XIII | All proposals validate against the `Requirement` schema before confirmation; typed contracts at every boundary | ✅ NFR-002; `ExtractedProposal` is validated against ADP-SPEC-001 schema before presenting to human |
| QG-04 | ART-IV | Tests before implementation; ≥ 85% coverage | ✅ LLM mocked; full pipeline testable without real endpoint |
| QG-11 | ART-VI | AI extraction step MUST emit span with inputs/outputs/cost/latency | ✅ FR-006; `adp.intake.telemetry` emits one span per job per ADP-SPEC-012 |
| QG-13 | ART-IX | Model mutations write append-only audit entries with origin and actor | ✅ FR-004; confirmation writes `AuditEntry` via ADP-SPEC-002 store |
| QG-14 | ART-VIII | Consequential actions require explicit, attributable human confirmation | ✅ FR-003; per-proposal confirmation gate in ADP-SPEC-003's confirmation router |
| QG-16 | ART-XI | Referential integrity; no orphan elements; traceability end-to-end | ✅ FR-002; each confirmed `Requirement` has a stable id and becomes the anchor for downstream traceability |

**ART-VII note**: Extracted requirements MUST cite a source excerpt (FR-007). This is ADP's grounding mechanism for intake — the LLM's output is grounded in the submitted text, not in general world knowledge. Proposals without a verifiable source excerpt are flagged (not blocked) to preserve usability while surfacing the risk.

**Constitution Alignment**: ART-II (model is the single source of truth) — raw text is input-only, never stored; only the normalized `Requirement` enters the model. ART-V — configurable endpoint enables data-residency-sensitive deployments.

## Project Structure

### Documentation (this feature)

```text
specs/006-requirements-intake/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions and rationale
├── data-model.md        # Phase 1 — intake pipeline entities
├── contracts/
│   ├── orchestrator-contract.md  # Python orchestrator interface
│   └── llm-prompt-contract.md    # LLM prompt/response schema
├── quickstart.md        # Phase 1 — submitting and confirming requirements
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
    ├── api/                      # ADP-SPEC-003 (updated: operations router wires intake)
    ├── authz/                    # ADP-SPEC-004 (unchanged)
    ├── knowledge/                # ADP-SPEC-005 (unchanged)
    └── intake/
        ├── __init__.py           # Exports ExtractionOrchestrator, IntakeSubmission, ExtractedProposal
        ├── models.py             # IntakeSubmission, ExtractionJob, ExtractedProposal dataclasses
        ├── llm.py                # LLMClient — configurable OpenAI-compatible HTTP caller
        ├── parser.py             # LLMResponseParser — JSON response → list[ExtractedProposal]
        ├── verifier.py           # SourceExcerptVerifier — verifies verbatim substring (FR-007)
        ├── linker.py             # KnowledgeLinker — matches text → knowledge base ids (FR-005)
        ├── telemetry.py          # IntakeTelemetry — emits one span per job (FR-006 / QG-11)
        └── orchestrator.py       # ExtractionOrchestrator — coordinates the full pipeline

tests/
└── intake/
    ├── __init__.py
    ├── test_parser.py             # JSON response parsing (pure Python, no mocks needed)
    ├── test_verifier.py           # Source excerpt verification (pure Python)
    ├── test_linker.py             # Knowledge linker (mock KnowledgeRetrieval)
    ├── test_telemetry.py          # Span emission (mock OTel exporter)
    └── test_orchestrator.py       # Full pipeline (mock LLM + mock store)
```

**Structure Decision**: New `adp.intake` sub-package. The orchestrator is called by ADP-SPEC-003's operations router when `kind=intake` is submitted. The orchestrator is a pure Python async class — no HTTP surface. The API layer (ADP-SPEC-003) handles authentication, operation polling, and confirmation routing.
