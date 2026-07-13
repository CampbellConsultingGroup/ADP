# Feature Specification: AI Recommendation Engine

**Feature Branch**: `007-recommendation-engine`  
**Created**: 2026-07-01  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-007 — AI Recommendation Engine"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — The Model is the Single Source of Truth: in scope; accepted options materialize `Element` and `Relationship` records into the canonical model (ADP-SPEC-001); no parallel element store is created
- **ART-IV** — Test-Driven Development: always applies; every orchestration step and acceptance path requires a test before implementation
- **ART-VI** — Observability is Not Optional: central concern; every orchestration step MUST emit a telemetry span with retrieved-knowledge references, inputs, outputs, cost, and latency (FR-006 / QG-11)
- **ART-VII** — Grounded AI Only: the primary governance constraint on this spec; every `SolutionOption` MUST cite the knowledge items it was grounded on; options without citations MUST be treated as advisory and MUST NOT be committed (FR-003 / QG-12)
- **ART-VIII** — Human-in-the-Loop for Consequence: accepting a recommended option and materializing elements is a consequential action; it MUST be an explicit, per-option human action; no auto-acceptance (FR-004 / QG-14)
- **ART-IX** — Provenance and Auditability: materialized elements MUST carry `provenance` linking back to the accepted `SolutionOption`; the acceptance is recorded in the audit trail (FR-004 / FR-005 / QG-13)
- **ART-XI** — Traceability End to End: elements materialized from an accepted option MUST carry `satisfies` links to the requirements they address; this closes the requirement → option → element traceability thread (FR-005 / QG-16)
- **ART-XIII** — Typed Contracts Everywhere: `SolutionOption` is a typed entity; every output of the recommendation pipeline is validated against the canonical schema before being offered to the architect

## Threat Model *(mandatory — ART-V)*

The recommendation engine is a critical governance boundary — AI-generated content that passes through it could, if not properly gated, introduce ungrounded or hallucinated architectural decisions into the canonical model.

**Assets at risk**: The canonical model (could be corrupted by ungrounded AI recommendations); the organizational knowledge base used for grounding (if poisoned, recommendations are poisoned); the audit trail (could be bypassed if acceptance is not properly gated).

**Trust boundaries crossed**: Architect → Platform API → recommendation orchestrator → LLM (same configurable endpoint as ADP-SPEC-006); recommendation orchestrator → ADP-SPEC-005 knowledge retrieval.

**Abuse cases**:
- **Ungrounded option acceptance**: An AI-generated option without valid knowledge citations is accepted, introducing fabricated architectural patterns → Mitigation: FR-003 (options without citations are advisory-only); the ADP-SPEC-003 confirmation router enforces `citations_present=True` before acceptance
- **Hallucinated knowledge references**: The LLM fabricates citation ids for items that don't exist in the knowledge base → Mitigation: citation ids are validated against the ADP-SPEC-005 index before the option is finalized; invalid citations downgrade the option to advisory
- **Silent element materialization**: Elements are created from a recommendation without explicit human approval → Mitigation: FR-004; acceptance is always an explicit per-option human action through ADP-SPEC-003's confirmation router
- **Knowledge base poisoning influencing recommendations**: A malicious actor introduces bad content into the knowledge base that is then cited by recommendations → Mitigation: ADP-SPEC-005 validates knowledge items against their schemas; this spec requires citations to be resolvable; it does not prevent all KB attacks, but makes them visible in the audit trail

**Residual risk**: An architect may confirm a recommendation they did not read carefully (confirmed but unvetted). Mitigated by surfacing citations, trade-offs, and the `advisory` flag prominently in the confirmation step.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate Grounded Solution Options for Confirmed Requirements (Priority: P1)

An architect has a set of confirmed requirements for a design. They request recommendations. The engine retrieves relevant patterns, standards, principles, and prior solutions from the knowledge base, generates 3 candidate `SolutionOption` records grounded in those knowledge items, ranks them, and returns them for review — each with citations, trade-off assessment, and rationale.

**Why this priority**: Grounded option generation is the entire purpose of this spec. All other stories build on this foundation.

**Independent Test**: Submit a set of known requirements against a pre-loaded knowledge base; assert 3 options are returned; assert each option has at least one verified citation; assert options are ordered by rank; assert no option was committed to the canonical model.

**Acceptance Scenarios**:

1. **Given** a set of confirmed requirements, **When** a recommendation job completes, **Then** the result contains 1–5 ranked `SolutionOption` records each carrying: a title, a rationale, a trade-off assessment, a list of knowledge citation references (each with id and version), a list of satisfied requirement ids, and a rank
2. **Given** a recommendation job, **When** the engine retrieves knowledge, **Then** it MUST use the ADP-SPEC-005 retrieval interface and MUST cite the retrieved items; options MUST draw on retrieved knowledge, not generate ungrounded architecture
3. **Given** multiple options, **When** ranked, **Then** the ranking accounts for coverage of the input requirements, alignment with relevant principles, and trade-off profile against applicable NFRs; the ranking criteria and scores are visible alongside each option

---

### User Story 2 - Review Trade-Off Analysis for Each Option (Priority: P1)

The architect reviews the ranked options. Each option includes an explicit assessment of how it addresses (or fails to address) the relevant non-functional requirements and principles. The architect can compare options side by side before deciding which to accept, reject, or defer.

**Why this priority**: Without trade-off transparency, the recommendation is a black box. Architects need to understand WHY an option is ranked where it is. Builds on US1 (options must exist).

**Independent Test**: Submit a known set of NFRs and principles alongside requirements; assert each returned option carries a trade-off entry for every applicable NFR and principle; assert the trade-off entries include a stance (`meets`, `partially_meets`, `does_not_meet`) and a rationale string.

**Acceptance Scenarios**:

1. **Given** a recommendation result with multiple options, **When** an architect views an option, **Then** the trade-off assessment lists every applicable NFR and principle with a stance (`meets`, `partially_meets`, `does_not_meet`) and a one-sentence rationale
2. **Given** two options with different rankings, **When** their trade-off assessments are compared, **Then** the higher-ranked option demonstrably scores better on the dominant trade-off criteria
3. **Given** an option that cannot address an NFR, **When** the trade-off assessment is generated, **Then** the `does_not_meet` stance is surfaced explicitly rather than omitted

---

### User Story 3 - Accept an Option to Materialize Design Elements (Priority: P2)

The architect selects a recommended option and explicitly accepts it. The system materializes the `Element` and `Relationship` records described by the option into the design's canonical model, each carrying `provenance` linking back to the accepted option and `satisfies` links to the requirements addressed.

**Why this priority**: Acceptance is the consequential action that makes recommendations actionable. Builds on US1/US2; the option must exist and be grounded before it can be accepted.

**Independent Test**: Accept a specific option from a completed recommendation job; assert the design now contains new `Element` records with `provenance = option_id`; assert those elements carry `satisfies` links to the requirements the option addressed; assert the audit trail records the accepting architect's identity.

**Acceptance Scenarios**:

1. **Given** a completed recommendation with at least one grounded option, **When** the architect explicitly accepts it via the confirmation step, **Then** new `Element` and `Relationship` records are appended to the design with `provenance` referencing the accepted option id
2. **Given** an accepted option, **When** the materialized elements are queried, **Then** each element carries `satisfies` links to the requirement ids in the option's `satisfies` list
3. **Given** an option with `advisory=True` (no verified citations), **When** the architect attempts to accept it, **Then** the confirmation step requires an explicit acknowledgment of the advisory status; the option MAY still be accepted but the materialized elements carry an `advisory_provenance` flag
4. **Given** an acceptance is confirmed, **When** the audit trail is queried, **Then** an entry records the accepting architect, the option id, the design id, and the timestamp

---

### User Story 4 - Inspect Each Orchestration Step (Priority: P2)

Every step in the recommendation pipeline is inspectable: retrieval, option generation, trade-off analysis, and ranking. Each step's telemetry span records the knowledge items retrieved, the LLM inputs and outputs (as references, not raw text), the cost, and the latency.

**Why this priority**: Inspectability is the ART-VI / QG-11 governance requirement. Without it, the recommendation pipeline cannot be trusted or debugged in production.

**Independent Test**: Run a recommendation job; assert one telemetry span was emitted per orchestration step; assert each span carries `retrieved_knowledge_refs`, `input_tokens`, `output_tokens`, `cost_usd`, and `latency_ms`; assert the spans share a correlation ID with the originating API request.

**Acceptance Scenarios**:

1. **Given** a recommendation job runs, **When** it completes (success or failure), **Then** one telemetry span is emitted per orchestration step (retrieval, generation, trade-off analysis, ranking), each carrying: retrieved knowledge references with versions, input/output token counts, estimated cost, latency, and a correlation ID
2. **Given** a step fails, **When** its span is emitted, **Then** the span records the error type and message; no partial results from the failed step are committed
3. **Given** all step spans for one job, **When** correlated, **Then** they form a complete, auditable record of the recommendation run's inputs, retrieved knowledge, and outputs

---

### Edge Cases

- What happens when the knowledge base returns no relevant results for the input requirements?
- How are options ranked when all of them have the same score?
- What happens when the LLM generates more options than the configured maximum?
- How does the engine behave when one orchestration step fails mid-pipeline?
- What happens when an accepted option refers to knowledge items that were deleted from the knowledge base after the recommendation was generated?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Before generating options, the engine MUST retrieve relevant knowledge from ADP-SPEC-005 using the input requirements as the query; retrieval MUST use the hybrid search mode and MUST request at minimum `pattern`, `standard`, and `principle` knowledge types
- **FR-002**: The engine MUST produce 1 to 5 ranked `SolutionOption` records; each MUST carry: `title`, `rationale`, `trade_offs` (a list of NFR/principle coverage assessments), `grounded_on` (list of `CitationRef`s), `satisfies` (list of requirement ids from the input set), and `rank` (integer, 1 = highest)
- **FR-003**: Any `SolutionOption` lacking at least one verified knowledge citation MUST be marked `advisory=True`; advisory options MUST NOT be auto-committed and MUST require explicit acknowledgment during acceptance
- **FR-004**: Accepting an option MUST be an explicit human action via ADP-SPEC-003's confirmation endpoint; acceptance MUST materialize the option's `elements` and `relationships` into the design store (ADP-SPEC-002) with `provenance` set to the accepted option's id; the acceptance is recorded in the audit trail with actor, timestamp, and option id
- **FR-005**: Every materialized `Element` MUST carry `satisfies` links to the requirement ids that the accepted option addressed; the requirement → element traceability thread MUST be intact and queryable via ADP-SPEC-002's traceability queries
- **FR-006**: Each orchestration step (knowledge retrieval, option generation, trade-off analysis, ranking) MUST emit one telemetry span per ADP-SPEC-012 carrying: step name, retrieved knowledge refs with versions, input/output token counts, estimated cost in USD, and latency in milliseconds

### Non-Functional Requirements

- **NFR-001**: Recommendation jobs MUST run asynchronously; the operation handle MUST be available within 2 seconds; recommendation results MUST be available for architect review within 60 seconds for typical inputs (≤ 15 confirmed requirements) — see SC-003 for the measurable verification target
- **NFR-002**: The orchestration MUST be step-by-step inspectable; each step's inputs, outputs, and retrieved-knowledge references MUST be recorded and available for audit without requiring access to the LLM endpoint logs

### Key Entities

- **RecommendationJob**: The async orchestration job; carries status (`pending`, `running`, `completed`, `failed`), input requirement ids, and reference to result set; attached to the ADP-SPEC-003 `OperationHandle` via `kind=recommendation`
- **SolutionOption**: The primary output; carries `id`, `rank`, `title`, `rationale`, `advisory` flag, `grounded_on` (`list[CitationRef]`), `satisfies` (`list[RequirementId]`), `trade_offs` (list of `TradeOffEntry`), and `proposed_elements` (list of partial `Element` descriptions the option would materialize)
- **TradeOffEntry**: One row in a `SolutionOption`'s trade-off assessment; carries `criterion` (NFR id or principle name), `stance` (`meets` / `partially_meets` / `does_not_meet`), and `rationale` (one sentence)
- **RecommendationStep**: One orchestration step's telemetry record; carries `step_name`, `retrieved_knowledge_refs`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `correlation_id`, and optional `error`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `SolutionOption` records surfaced to architects carry at least one knowledge citation with a valid id and version; zero options committed to the model without verified citations (FR-003 / ART-VII)
- **SC-002**: Every `SolutionOption` includes a `TradeOffEntry` for every applicable NFR and principle in the input context; zero options with missing trade-off coverage
- **SC-003**: Recommendation results are available within 60 seconds for inputs of up to 15 confirmed requirements under normal LLM endpoint conditions; the operation handle is available within 2 seconds (NFR-001)
- **SC-004**: Every recommendation job emits one telemetry span per orchestration step with all required fields; zero jobs with missing or incomplete spans (FR-006 / QG-11)
- **SC-005**: 100% of elements materialized from accepted options carry `provenance` referencing the option id and `satisfies` links to the addressed requirements; the traceability thread is intact and verifiable via ADP-SPEC-002's traceability queries

## Assumptions

- **Number of options and ranking criteria (resolved)**: The engine generates 3 candidate options by default (configurable via `ADP_REC_OPTION_COUNT`, range 1–5). Ranking uses equal weighting across three criteria: (a) coverage of input confirmed requirements, (b) alignment with retrieved principle knowledge items, and (c) trade-off profile against applicable NFRs. The weighting is configurable per deployment via `ADP_REC_RANKING_WEIGHTS`. The three-option default is standard for architectural decision records and avoids both underprovision (< 2 options) and decision paralysis (> 5 options).
- The recommendation engine uses the same configurable LLM endpoint as ADP-SPEC-006 (`ADP_LLM_BASE_URL`, `ADP_LLM_MODEL`). No separate LLM is required.
- "LangGraph" is mentioned as the orchestration framework in the source dependencies. This spec treats the orchestration as an implementation concern; the spec governs the workflow steps and their outputs, not the specific framework used.
- Prior solutions (kind=`prior_solution`) from the ADP-SPEC-005 knowledge base are included in retrieval and may be cited; recommending a prior solution is a valid and preferred outcome (reuse by construction).
- Materialization of elements from an accepted option is schema-validated against ADP-SPEC-001 before writing to ADP-SPEC-002. Proposals that would violate the schema fail with a descriptive error; the option remains accepted but un-materialized pending correction.
- The maximum of 15 confirmed requirements for the SC-003 performance target is an engineering guideline; inputs above this limit are still accepted but may exceed 60 seconds.
- "Applicable NFRs and principles" for trade-off analysis (SC-002 / T022) means: (a) confirmed requirements in the input set whose descriptions indicate a quality attribute (performance, security, scalability, reliability, availability); and (b) principle knowledge items in `state["retrieved_knowledge"]` where `kind == "principle"`. This determination is heuristic for v1; fine-grained applicability rules are a v2 governance configuration concern.

## Out of Scope

- Validation of the resulting design against standards and principles (ADP-SPEC-008)
- The knowledge index and retrieval interface (ADP-SPEC-005 — consumed but not owned here)
- The LLM endpoint itself; this spec consumes a configurable endpoint
- Automated acceptance without human confirmation
- Generating recommendations from unconfirmed (pending) requirements
- ADP-SPEC-012 telemetry pipeline and dashboards (spans are emitted to it; the pipeline is assumed to exist)
