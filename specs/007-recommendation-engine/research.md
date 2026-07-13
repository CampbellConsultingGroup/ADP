# Research: AI Recommendation Engine

**Branch**: `007-recommendation-engine` | **Date**: 2026-07-01  
**Phase**: 0 — Decisions and rationale before design begins

## Decision 1: LangGraph for Orchestration

**Decision**: Use LangGraph (`langgraph>=0.2`) to implement the five-step recommendation pipeline as a `StateGraph`.

**Rationale**: LangGraph is explicitly named in the source spec's dependencies. It provides: (a) a typed state object that is threaded through all steps — enabling NFR-002's step-by-step inspectability without custom plumbing; (b) native async support compatible with our asyncio stack; (c) node-level testing where each step can be invoked with a test state dict without running the full pipeline. The graph structure makes the workflow visible and auditable.

**Pipeline as StateGraph**:
```
START → retrieve → generate → analyze_tradeoffs → rank → validate_citations → END
```
Each node reads from and writes to a shared `RecommendationState` TypedDict.

**Alternatives considered**:
- Plain asyncio sequential calls — simpler but loses inspectability and the ability to test nodes in isolation; contradicts NFR-002
- Celery / task queue — appropriate for large-scale distributed work; over-engineered for a single-service pipeline where all steps run in-process
- Temporal / Prefect — heavy infrastructure; violates our "no new services" principle for v1

---

## Decision 2: Structured LLM Output for Option Generation

**Decision**: The option generation step uses a structured output prompt that instructs the LLM to return a JSON object matching the `SolutionOption` schema. The generation prompt includes: the confirmed requirements, a summary of the retrieved knowledge items (titles, kinds, and excerpts — NOT full text), and the target output schema.

**Rationale**: Structured output (JSON mode / function calling) produces reliable, parseable responses without post-processing string extraction. Providing only knowledge summaries (not full text) keeps the prompt within context limits for large knowledge bases. The LLM is explicitly told which knowledge item ids to cite.

**Knowledge summary format in prompt**:
```
[K-001] Pattern: "API Gateway Pattern" — Provides a single entry point for client requests.
[K-002] Standard: "TLS 1.3 Requirement" — All services must use TLS 1.3.
```

---

## Decision 3: Trade-off Analysis as a Separate Step

**Decision**: Trade-off analysis runs as a dedicated step after option generation, not inline. For each candidate option, the LLM is called once with the option's description and a list of applicable NFRs and principles; it returns a `list[TradeOffEntry]`.

**Rationale**: Separating generation from trade-off analysis allows each to be tested, inspected, and retried independently. It also produces cleaner prompts — the generation step focuses on "what to build", the trade-off step focuses on "how well does it hold up". Each step emits its own telemetry span (QG-11).

**Trade-off prompt gives the LLM**: the option's rationale + generated elements + the list of NFR/principle ids + their definitions; the LLM returns stance + rationale per criterion.

---

## Decision 4: Citation Validation Strategy

**Decision**: After generation and trade-off analysis, a citation validation step checks each option's `grounded_on` list against ADP-SPEC-005's `resolve_citation()` method. Any citation that cannot be resolved marks the option `advisory=True`. This step does NOT call the LLM; it is a pure database lookup.

**Rationale**: The LLM may hallucinate citation ids. Validating citations against the live knowledge index ensures every committed recommendation references real, version-locked knowledge. Advisory-only marking (not blocking) preserves usability for edge cases where the knowledge base is sparse.

---

## Decision 5: Ranking Algorithm

**Decision**: Options are ranked by a weighted sum of three normalized scores:
1. **Requirement coverage score** (0–1): fraction of input confirmed requirements covered by the option's `satisfies` list
2. **Principle alignment score** (0–1): mean retrieval relevance score of the principle knowledge items the option cites
3. **Trade-off score** (0–1): fraction of applicable NFRs/principles assessed as `meets` (vs `partially_meets` or `does_not_meet`)

Weights: `(w_req, w_principle, w_tradeoff)` — default `(0.4, 0.3, 0.3)`, configurable via `ADP_REC_RANKING_WEIGHTS`.

**Rationale**: Requirement coverage is the most critical criterion (architects must address their requirements). Principle alignment rewards options that directly cite relevant standards. Trade-off score rewards options that are least likely to fail against NFRs. The weighted sum is deterministic — no LLM call in the ranking step — making it reproducible and auditable.

---

## Decision 6: Element Materialization from Accepted Option

**Decision**: The recommendation engine's generation step produces `ProposedElement` records — partial `Element` descriptions (name, kind, description, satisfies) — embedded in the `SolutionOption`. On acceptance, the orchestrator's `materialize()` method converts each `ProposedElement` into a canonical `Element` (ADP-SPEC-001) with a new `ElementId`, sets `provenance=option_id`, validates against the ADP-SPEC-001 schema, and saves via ADP-SPEC-002.

**ProposedElement** (in the generation prompt response):
```json
{"name": "API Gateway", "kind": "container", "description": "...", "satisfies": ["REQ-001"]}
```

**Rationale**: Embedding element proposals in the option (rather than generating them separately at acceptance time) allows architects to evaluate what would be materialized before accepting. The id assignment happens at materialization time to avoid collisions.

---

## Decision 7: ADP-SPEC-003 Integration Point

**Decision**: Same as ADP-SPEC-006 intake — the orchestrator is invoked by ADP-SPEC-003's operations router when `kind=recommendation`. The `ConfirmationPayload.option_id` field (same extension as `proposal_id` from ADP-SPEC-006) routes acceptance to `orchestrator.materialize_option()`.

**Rationale**: Reuses the existing async operation infrastructure (submit → poll → confirm). No new API endpoints needed; only a new `kind` value and a new orchestrator behind the existing confirmation flow.

---

## Decision 8: Step Telemetry Span Structure

**Decision**: Each step emits one OTel span via `adp.recommendation.telemetry`. The five spans per job share a parent span `adp.recommendation.pipeline` that carries the job-level attributes. Each step span carries:
- `step_name`: e.g., `retrieve`, `generate`, `analyze_tradeoffs`, `rank`, `validate_citations`
- `retrieved_knowledge_refs`: comma-separated `item_id@version` strings
- `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`
- `option_count` (generation step): number of candidates produced
- `correlation_id`: from the originating API request

**Rationale**: Step-level spans allow the ADP-SPEC-012 telemetry pipeline to reconstruct the full pipeline trace, identify which step is slow or expensive, and audit what knowledge items were used in each generation.
