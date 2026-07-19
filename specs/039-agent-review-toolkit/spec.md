# Feature Specification: Agent Review Toolkit (with Business Capabilities Adapter)

**Feature Branch**: `039-agent-review-toolkit`
**Created**: 2026-07-19
**Status**: Draft
**Input**: User description: "Research options to add an agent to the business capabilities screen that can review the capabilities and make suggestions. We would want the agent available as a button. It will be a business architecture expert. It will be able to see all the data tied to the capabilities to leverage for making suggestions. With human approval its suggestions would be added to the database. We would want to do this in a way that it could [be] repeated across any screen where an agent could be of value." Follow-up: "spec it out based on option B" (shared toolkit + thin per-domain adapters, as opposed to one monolithic generic engine or a per-domain-dispatch router).

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: (always applies) — this spec precedes implementation.
- **ART-II** — The Model is the Single Source of Truth: an accepted suggestion MUST write through the same store CRUD functions a human editing the screen would use. The toolkit introduces no parallel write path and no shadow copy of capability data.
- **ART-III** — Everything is Machine-Readable: suggestion payloads, the review-operation resource, and the toolkit's grounding-check result are all typed and schema-emitted.
- **ART-IV** — Test-Driven Development: (always applies) — contract tests for the toolkit's shared pieces and for the capability adapter precede their handlers.
- **ART-V** — Security by Design: the agent reads a wide slice of business/application data to form suggestions and can, on human approval, mutate the capability registry. See Threat Model.
- **ART-VI** — Observability is Not Optional: the review operation is itself an AI orchestration step and MUST emit a span (inputs/outputs/token usage/cost/latency) exactly like intake, recommendation, and validation do today.
- **ART-VII** — Grounded AI Only: every suggestion that references an existing entity (a capability, domain, application, or design) MUST have that reference verified against the database before the suggestion is shown, let alone accepted; an unverifiable reference makes the suggestion advisory-only.
- **ART-VIII** — Human-in-the-Loop for Consequence: no suggestion is ever applied automatically. Each suggestion is accepted or rejected individually, by an explicit, attributable human action.
- **ART-IX** — Provenance and Auditability: an accepted suggestion MUST be attributable to its confirming human actor and traceable back to the review operation/suggestion that produced it. Business capabilities have no `design_id` (the `audit_entries` table is design-centric), so — consistent with the rest of `adp.business`/`adp.application`, where ART-IX is already SHOULD-level and satisfied by structured logging — an accepted suggestion writes a structured log line (`origin=ai`, actor, operation id, suggestion id) plus a durable `llm_reasoning_log` row carrying the rationale; the latter is a real, queryable, append-only database record, not just a log line.
- **ART-XI** — Traceability End to End: an accepted suggestion's resulting change MUST be traceable back to the specific suggestion and review operation that produced it, so a reviewer can later ask "why does this capability's classification say this?"
- **ART-XIII** — Typed Contracts Everywhere: all boundary payloads (suggestion types, review-operation status, accept/reject requests) are Pydantic v2 models with `extra="forbid"`.
- **ART-XVI** — Documentation as Code: the toolkit's shared interface (what a new adapter must implement) is documented alongside this spec so a second adapter can be built without re-deriving it from source.

*Not engaged*: ART-X (Deterministic Validation Gating) — this feature has no pass/fail gate; every suggestion is individually accepted or rejected, which is ART-VIII's concern, not ART-X's. ART-XII (Fixed Visual Language) — no C4 diagram rendering change. ART-XIV / ART-XV (Reproducible builds / Schema evolution) — not distinctively engaged beyond the universal gates; this feature introduces no new database tables (see Assumptions), so no migration is expected.

## Threat Model *(mandatory — ART-V)*

**Assets at risk**: the business capability registry and everything an expert review reads to form a suggestion — capability names/descriptions/classification, domain assignments, linked value-stream stages, linked applications and their non-sensitive APM fields, linked technical capabilities, and linked solution designs. A suggestion that gets accepted mutates the canonical capability/domain data other screens and rollups depend on.

**Trust boundaries crossed**: browser → API (submit review, poll status, accept/reject a suggestion) → LLM provider (context sent out for suggestion generation) → back to API (suggestion set) → database (only on human accept).

**Abuse cases**:
- *Prompt-injection via capability free text*: a capability's `description` (or a linked application's `description`) contains text crafted to make the LLM emit a suggestion that looks legitimate but references a fabricated or unrelated entity id → **Mitigation**: every entity id a suggestion references is independently re-verified against the database (ART-VII); an id that doesn't resolve marks the suggestion advisory and blocks acceptance without an explicit override, exactly like the recommendation engine's citation validation.
- *Unauthorized trigger or approval*: a user without capability-write privileges triggers reviews to probe what data the agent can see, or approves a suggestion they aren't authorized to make manually → **Mitigation**: triggering a review and confirming a suggestion are each gated by a dedicated action-based permission (FR-013), and accepting a suggestion re-checks the underlying write permission for the target entity at accept time, not only at trigger time.
- *Silent drift via stale suggestions*: a suggestion is generated, the underlying capability is edited or deleted by someone else, and the suggestion is accepted anyway against stale state → **Mitigation**: accept re-fetches and re-validates the target entity's current state immediately before writing; if it no longer matches what the suggestion was generated against, the accept fails explicitly (409) rather than silently applying a stale change.
- *Sensitive-data leakage into the agent's context*: the agent's context assembly reaches into a linked application's sensitive fields (cost, risk, governance) without the reviewing user holding those permissions → **Mitigation**: v1's context assembly explicitly excludes application risk/cost/governance fields regardless of the reviewing user's permissions (see Clarifications); only non-sensitive APM fields are included.
- *Cost/abuse via repeated triggering*: a user repeatedly re-triggers review on the same capability to run up LLM cost or probe for different outputs → **Mitigation**: each review is a normal rate-observable operation through the existing `OperationStore`/telemetry path (ART-VI); no new mitigation beyond what already applies to intake/recommend is introduced in v1 (see Assumptions).

**Residual risk**: LLM suggestion quality depends on prompt design and model behavior that can drift between provider model versions; accepted at this threat level because every suggestion is human-reviewed before any write occurs (ART-VIII) and every write is fully attributable (ART-IX) — the worst case is a rejected or ignored bad suggestion, not a silent bad write.

## Clarifications

### Session 2026-07-19

- **Q: Whole-capability-tree review or single-capability review for v1?** → **A:** Single-capability review only. The entry point is a per-capability action, not a page-level "review everything" button. Bounded context keeps the prompt small, the suggestion set reviewable, and cost predictable; whole-tree review is a future extension of the same toolkit, not part of this spec.
- **Q: Does the agent's context include sensitive application data (risk, cost, governance)?** → **A:** No, not in v1. Context assembly for a linked application includes only its non-sensitive APM fields (`time_classification`, `r_strategy`, `pace_layer`, `health_score`); application risk, cost, and governance records are excluded regardless of the reviewing user's own permissions, to avoid entangling this feature with the sensitive-category authz gates on day one.
- **Q: Do rejected suggestions feed back into future reviews (like the recommendation engine's reject-as-anti-pattern learning)?** → **A:** No, not in v1. A rejected suggestion is simply marked rejected and never written; it does not influence a later review of the same or any other capability. This is an explicit future extension, not part of this spec.
- **Q: What is the fixed taxonomy of suggestion types for the Business Capabilities adapter?** → **A:** Five types: `reclassify_strategic_relevance`, `set_maturity_level`, `assign_domain`, `flag_duplicate`, `propose_new_capability`. This is the adapter's complete scope for v1; the toolkit itself does not fix or limit the taxonomy for future adapters.
- **Q: Can `flag_duplicate` compare capabilities across different hierarchy levels (L1 vs L2 vs L3)?** → **A:** No. A duplicate flag is only valid between two capabilities at the same `level`, since capabilities at different hierarchy depths represent different granularities by definition and cannot be structural duplicates of each other.
- **Q: Does triggering a review use a separate permission from accepting/rejecting its suggestions?** → **A:** Yes. Two new action types are introduced — one to trigger a review, one to confirm (accept or reject) a suggestion — distinct from the underlying write action used when a suggestion is actually applied. This mirrors the existing recommendation module's separation of "submit the AI operation" from "confirm its output," which is a cleaner and more recently established precedent than the intake module's simpler approach.
- **Q: Does accepting a suggestion introduce a new write path into the capability/domain store?** → **A:** No. Accepting a suggestion MUST call the exact same store functions (update, domain-assign, create) that the Business Capabilities screen's own manual edit UI already calls. The toolkit and adapter add a review-and-approval layer in front of existing writes; they do not add a second way to write the same data.
- **Q: Does this feature require a new database table?** → **A:** No. A review operation and its suggestions are transient, following the same shape as an intake extraction operation or a recommendation operation: tracked in the existing `OperationStore` (already TTL-bounded and Postgres-backed), not a new permanent table. If planning determines the existing `llm_reasoning_log` needs a schema change to record suggestion-level reasoning, that is a plan-level implementation detail, not a spec-level requirement.
- **Q: When the LLM call itself fails mid-review (network error, provider error, malformed response) — distinct from the already-resolved "no API key configured" case — how should the operation behave?** → **A:** The operation transitions to `failed` with an `error_description`, exactly mirroring how intake/recommendation already surface LLM-call failures. No automatic retry and no silent fallback to an empty suggestion set — that would violate ART-VI's prohibition on silent catch-and-continue and would be indistinguishable from the legitimate "no LLM configured" case, hiding a real failure.
- **Q: Does FR-015's accept-time stale-state check compare only the specific field(s) a suggestion would write, or any field on the target entity?** → **A:** Field-scoped only. Accept re-verifies the target entity still exists and that the *specific field(s) the suggestion would write* are unchanged since generation; an unrelated field change (e.g. someone renamed the capability, or a different accepted suggestion changed a different field) does not block acceptance. This matches the existing "Conflicting suggestions" edge case philosophy — independent field writes shouldn't block each other — and there is no whole-record version column to check against (`update_capability` has none today).

## User Scenarios & Testing *(mandatory)*

> Each story is an independently shippable slice through the full pipeline: context assembly → suggestion generation → grounding check → human review → (on accept) an existing write path + audit entry. Stories are ordered by increasing write-risk, so the safest, most foundational slice — which proves the whole toolkit end to end — ships first.

### User Story 1 - Flag possible duplicate capabilities (Priority: P1)

A business architect looking at a capability suspects it overlaps with another one elsewhere in the tree. They trigger a review on the capability; the reviewing agent — a "business architecture expert" persona — considers the capability's name, description, and full linked context, compares it against other capabilities at the same hierarchy level, and surfaces any it considers a likely duplicate, with its reasoning. No suggestion in this story writes anything to the database; accepting one simply acknowledges it (no store mutation), so this story proves the full read/generate/ground/review pipeline with zero write risk.

**Why this priority**: This is the safest possible first slice — it exercises context assembly, the LLM call, the ART-VII grounding check (the flagged capability's id must resolve to a real, same-level capability), the async operation lifecycle, and the human review UI, without touching the write path at all. It de-risks every later story.

**Independent Test**: Create two capabilities at the same level with near-identical names/descriptions and a third, unrelated one at the same level. Trigger a review on one of the near-duplicates; confirm the suggestion set flags the other near-duplicate (citing its real capability id) and does not flag the unrelated one.

**Acceptance Scenarios**:

1. **Given** a capability with a near-duplicate at the same hierarchy level, **When** a review is triggered, **Then** the completed operation includes a `flag_duplicate` suggestion citing the other capability's real id and a rationale.
2. **Given** a capability with no plausible duplicate, **When** a review is triggered, **Then** the completed operation returns no `flag_duplicate` suggestions rather than a low-confidence false positive.
3. **Given** a `flag_duplicate` suggestion whose cited capability id no longer exists (deleted between generation and review), **When** the human opens the suggestion, **Then** it is shown as advisory/stale rather than presented as a normal actionable suggestion.

---

### User Story 2 - Suggest strategic relevance and maturity classification (Priority: P2)

A business architect reviews a capability that has never been classified. The agent proposes a `strategic_relevance` (Strategic/Core/Supporting) and/or a `maturity_level` (Ad hoc … World Class) value, with a rationale grounded in the capability's linked applications, value-stream stages, and domain. The architect accepts or rejects each proposed field independently; an accepted suggestion writes through the exact same update path the manual dropdown on the Business Capabilities screen already uses.

**Why this priority**: This is the first story where a suggestion actually writes to the database, so it is the first to exercise ART-VIII (explicit per-suggestion confirmation), ART-IX (audit entry with `origin="ai"`), and the "no parallel write path" requirement (ART-II) — on the two lowest-risk fields (a single enum value each, already nullable/reversible). It builds directly on Story 1's proven read-only pipeline.

**Independent Test**: Trigger a review on an unclassified capability with rich linked context (e.g. a linked application flagged Eliminate/low health). Confirm the suggestion set includes a `set_maturity_level` and/or `reclassify_strategic_relevance` suggestion with a rationale referencing that context; accept one and confirm the capability's field updates and an audit entry with `origin="ai"` is written; reject the other and confirm the capability's field is unchanged.

**Acceptance Scenarios**:

1. **Given** an unclassified capability, **When** a review is triggered, **Then** the completed operation includes a `reclassify_strategic_relevance` and/or `set_maturity_level` suggestion, each with a rationale.
2. **Given** a pending `set_maturity_level` suggestion, **When** the architect accepts it, **Then** the capability's `maturity_level` updates to the suggested value, a structured log entry (`origin="ai"`, the architect as actor) and an `llm_reasoning_log` row are written, and the suggestion cannot be accepted a second time.
3. **Given** a pending suggestion, **When** the architect rejects it, **Then** no database write occurs and the suggestion is marked rejected.
4. **Given** a capability already classified, **When** a review is triggered, **Then** the agent may still suggest a change (e.g. reclassifying maturity upward) but MUST state the current value in its rationale rather than suggesting blind.

---

### User Story 3 - Suggest a domain assignment (Priority: P3)

A business architect reviews an L1 capability with no assigned business domain. The agent proposes assigning it to a specific existing domain, citing the domain's classification and scope statement as rationale. Accepting the suggestion calls the existing domain-assignment path.

**Why this priority**: The first suggestion type that references a *different* entity type (a domain, not the capability itself), exercising cross-entity grounding — the cited domain id must be independently verified to exist — before extending to the fully net-new case (Story 4).

**Independent Test**: Create an unassigned L1 capability whose linked applications/value-stream stages strongly align with one existing domain's scope. Trigger a review; confirm the suggestion cites that domain's real id; accept it and confirm the capability's `domain_id` updates via the existing assignment path.

**Acceptance Scenarios**:

1. **Given** an unassigned L1 capability, **When** a review is triggered, **Then** an `assign_domain` suggestion may be produced citing a real domain id and a rationale.
2. **Given** a capability below L1, **When** a review is triggered, **Then** no `assign_domain` suggestion is produced (domain assignment is L1-only, matching the existing rule).
3. **Given** an `assign_domain` suggestion citing a domain, **When** the human accepts it, **Then** the capability's domain assignment updates via the same path the manual UI uses, and an audit entry is written.

---

### User Story 4 - Propose a new capability to close a gap (Priority: P4)

A business architect reviews a capability whose linked applications or value-stream stages imply a related capability that doesn't exist yet — for example, a value-stream stage with no capability coverage at all, or a pattern the existing capability-gap analysis (ADP-zg3.4) has already flagged. The agent proposes a net-new sibling or child capability (name, description, suggested level/parent) with a rationale citing the specific supporting context (the uncovered stage, the gap-analysis finding, or similar). Accepting it creates a real capability record via the existing create path, with provenance back to the suggestion.

**Why this priority**: The highest-value and highest-complexity suggestion type — it creates a new record rather than updating an existing one, and by definition cannot cite an existing capability id for what it's proposing, so its "grounding" is the supporting context data it cites instead (ART-VII is satisfied by requiring at least one real, verifiable citation to context data, not to the proposed capability itself, which doesn't exist yet).

**Independent Test**: Create a value-stream stage linked to no capability at all, itself linked to a capability under review. Trigger a review; confirm a `propose_new_capability` suggestion is produced citing the uncovered stage's real id; accept it and confirm a new capability record is created via the existing creation path with the correct level/parent and provenance back to the accepted suggestion.

**Acceptance Scenarios**:

1. **Given** a capability whose linked context reveals an uncovered value-stream stage, **When** a review is triggered, **Then** a `propose_new_capability` suggestion may be produced citing that stage's real id as supporting evidence.
2. **Given** a `propose_new_capability` suggestion with no verifiable supporting citation, **When** it is generated, **Then** it is marked advisory and cannot be accepted without an explicit override acknowledgment.
3. **Given** an accepted `propose_new_capability` suggestion, **When** the new capability is created, **Then** it is created via the existing capability-creation path (including its hierarchy-consistency validation), and its record carries provenance back to the suggestion/operation that produced it.

### Edge Cases

- **Stale reference at accept time**: the capability, domain, or other cited entity a suggestion references is edited or deleted between suggestion generation and human review → accept MUST re-verify the entity still exists and that the specific field(s) the suggestion would write are unchanged, and fail explicitly (not silently apply against stale data) if either check fails; an unrelated field change on the same entity does not block acceptance (field-scoped, not whole-record).
- **Conflicting suggestions in one review**: the same review produces two suggestions touching the same field with different values (e.g. two candidate maturity levels) → both remain independently actionable; accepting one does not silently invalidate the other, but the human is shown both together so they can choose.
- **Re-triggering review on the same capability**: a new review is triggered while a previous review's suggestions are still pending → the new review is an independent operation; the previous pending suggestion set is unaffected and expires on its own TTL like any other operation, exactly as repeated intake/recommend submissions already behave.
- **No LLM configured (dev/local)**: with no API key configured, the review operation completes with an empty suggestion set (consistent with the existing stub-client fallback used by intake and recommendation) rather than hanging or erroring.
- **LLM call fails mid-review** (network error, provider error, malformed response — distinct from "no LLM configured"): the operation transitions to `failed` with an `error_description`, exactly like an intake/recommendation failure; it MUST NOT retry automatically and MUST NOT silently fall back to an empty suggestion set, which would be indistinguishable from the legitimate no-API-key case and would hide a real failure (ART-VI).
- **Authorization mismatch between trigger and accept**: a user permitted to trigger a review is not permitted to write the target entity manually → accept MUST re-check the underlying write action for the target entity, not only the review-confirm action, and refuse the write if that check fails.
- **Large/deep linked context**: a capability with many linked applications, stages, and a large subtree → context assembly is scoped to the single capability's *direct* links only (its own fields, its domain, its immediate parent/children, its direct application/stage/tech-capability/design links) — not a full-tree traversal — to keep the prompt bounded and cost predictable.
- **Duplicate flag directionality**: capability A is flagged as a duplicate of B during A's review — reviewing B later must not double-count or auto-generate a mirrored suggestion; each review is scoped to its own triggering capability.

## Requirements *(mandatory)*

### Functional Requirements

**Shared toolkit**

- **FR-001**: System MUST provide a single shared LLM-client stub for local/no-API-key development, used by every agent-review adapter, replacing the ad hoc per-router stub duplication that exists today in the intake and recommendation routers.
- **FR-002**: System MUST provide a shared grounding/citation validator: given a suggestion and the set of entity ids it references, it MUST independently verify each referenced id resolves to a real, currently-existing record before the suggestion is treated as fully actionable; an id that fails to resolve MUST mark that suggestion advisory rather than discarding or silently correcting it.
- **FR-003**: System MUST provide shared helpers for (a) writing a structured, attributable log line (`origin="ai"`, confirming human as actor, operation/suggestion id) and (b) writing the durable `llm_reasoning_log` reasoning-trail record, for every accepted suggestion, so each adapter does not re-derive this logic. Where an adapter's domain is design-centric (has a real `design_id`), it MAY instead write a genuine `AuditEntry` via the existing `write_audit_record` path — which mechanism applies is a property of the adapter's domain, not something the toolkit hardcodes.
- **FR-004**: System MUST track every review as an operation in the existing `OperationStore` (submit → `pending`/`running` → `completed`/`failed`, pollable by `operation_id`), introducing no new job-tracking mechanism.
- **FR-005**: The toolkit's shared modules (LLM stub, grounding validator, audit/reasoning helpers) MUST NOT import from or depend on any single domain module (e.g. `adp.business`), so a second adapter for a different screen can be built without modifying the toolkit.
- **FR-006**: System MUST emit an observability span for each review operation carrying the same categories of information (step name, design/entity id, operation id, token usage, cost, latency) that intake/recommendation/validation steps already emit, so a review is inspectable the same way any other AI step is.
- **FR-021**: A review operation whose LLM call fails (network error, provider error, malformed response) MUST transition to `failed` with an `error_description`, MUST NOT retry automatically, and MUST NOT be indistinguishable from the no-API-key-configured case (which legitimately completes with an empty suggestion set). *(Resolved 2026-07-19.)*

**Business Capabilities adapter**

- **FR-007**: System MUST provide a way to trigger an agent review of a single business capability, returning an operation id to poll, following the same submit/poll contract as intake and recommendation.
- **FR-008**: The review's context MUST include the capability's own fields (name, description, level, position, strategic relevance, maturity level), its assigned domain (if any), its parent and direct children, its linked value-stream stages, its linked applications (non-sensitive APM fields only — see FR-009), its linked technical capabilities, and its linked solution designs.
- **FR-009**: The review's context MUST NOT include application risk, cost, or governance data, regardless of the reviewing user's own permissions. *(Resolved 2026-07-19.)*
- **FR-010**: System MUST support exactly five suggestion types for this adapter: `reclassify_strategic_relevance`, `set_maturity_level`, `assign_domain`, `flag_duplicate`, `propose_new_capability`. *(Resolved 2026-07-19.)*
- **FR-011**: A `flag_duplicate` suggestion MUST only compare capabilities at the same hierarchy `level`. *(Resolved 2026-07-19.)*
- **FR-012**: An `assign_domain` suggestion MUST only be produced for a capability at hierarchy level 1, consistent with the existing domain-assignment rule.
- **FR-013**: System MUST gate triggering a review and confirming (accepting or rejecting) a suggestion behind two distinct action-based permissions, separate from the underlying write action used when a suggestion is applied. *(Resolved 2026-07-19; requires a `PERMISSIONS_VERSION` bump.)*
- **FR-014**: Accepting a suggestion MUST call the existing business-capability store functions (update, domain assignment, or create) — the exact same functions the screen's manual edit UI calls — and MUST NOT introduce a second write path for the same data.
- **FR-015**: Accepting a suggestion MUST re-verify, immediately before writing, that every entity it references still exists and that the *specific field(s) the suggestion would write* are unchanged since generation, and MUST fail explicitly (without writing) if either check fails; a change to an unrelated field on the same entity MUST NOT block acceptance. *(Resolved 2026-07-19 — field-scoped, not whole-record.)*
- **FR-016**: Accepting a suggestion MUST re-check the underlying write permission for the target entity at accept time, independent of whether the user was permitted to trigger the review.
- **FR-017**: Rejecting a suggestion MUST mark it rejected and MUST NOT perform any database write.
- **FR-018**: System MUST NOT feed rejected suggestions back into future reviews in v1 (no anti-pattern learning loop). *(Resolved 2026-07-19; deferred.)*
- **FR-019**: All new boundary payloads (trigger request, review-operation status, suggestion types, accept/reject requests) MUST be typed Pydantic v2 models with `extra="forbid"` and MUST emit to JSON Schema via the generator.
- **FR-020**: The web layer MUST provide a reusable button/panel component and a generic polling+accept/reject hook set, parameterized by adapter, so the same components can be pointed at a future second adapter without modification; the Business Capabilities screen wires a per-capability entry point (not a page-level "review everything" button) using these components.

### Key Entities *(include if feature involves data)*

- **AgentReviewOperation**: a transient, `OperationStore`-tracked async job (mirrors an intake extraction or recommendation operation): status (pending/running/completed/failed), the target entity it reviewed, its resulting suggestion set, and error detail on failure.
- **AgentSuggestion**: one proposed change from an agent review — a type tag (one of the five for this adapter), the target entity, a rationale, zero or more cited entity ids, an `advisory` flag (set when a citation fails grounding), and a status (pending/accepted/rejected).
- **GroundingResult** (toolkit-level, not persisted): the outcome of independently re-verifying a suggestion's cited entity ids against the database — which ids resolved, which did not, and therefore whether the suggestion is fully grounded or advisory.
- **BusinessCapability, BusinessDomain, ValueStreamStage, Application, TechnicalCapability, Design** (all existing): read by context assembly; capability and domain are additionally the write targets when a suggestion is accepted.
- **`llm_reasoning_log` (existing)**: the durable, queryable provenance record for every accepted suggestion's rationale, keyed by operation id and suggestion id (via its `option_id` column). `AuditEntry` is not used here — business capabilities have no `design_id` to attach one to; a structured log line fills the same attributability role the rest of `adp.business` already relies on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every suggestion shown to a human that cites an existing entity has that citation independently verified against the database at generation time; zero suggestions referencing a non-existent entity are ever presented as fully actionable (unverifiable ones are always shown as advisory).
- **SC-002**: 100% of accepted suggestions produce exactly one structured, attributable log entry (`origin="ai"`, confirming human as actor) and exactly one `llm_reasoning_log` row, written via the same store functions a manual edit would use — verified by there being no code path that writes capability/domain data other than the existing manual-edit path plus this one, shared, review-accept path.
- **SC-003**: A rejected suggestion never results in a database write, in 100% of cases.
- **SC-004**: Triggering a review and confirming a suggestion are each independently enforceable by a distinct permission — a user holding only one of the two permissions can perform that action and not the other, verified by authorization tests.
- **SC-005**: The shared toolkit modules contain zero references to `adp.business` (or any other single domain module), verified by an import-boundary check, demonstrating the toolkit is reusable without modification by a hypothetical second adapter.
- **SC-006**: A stale-state accept attempt (target entity changed or deleted after suggestion generation) always fails explicitly rather than applying a change against outdated data.
- **SC-007**: Every review operation is pollable through the same request/response shape as an existing intake or recommendation operation, requiring no new client-side polling pattern.
- **SC-008**: All new boundary payloads pass schema validation with zero schema-drift-check failures in CI.

## Assumptions

- **No new database tables**: review operations and suggestions are transient, tracked in the existing `OperationStore` exactly like intake proposals and recommendation options; no new migration is expected. If reasoning-trail storage needs a schema change, that is a plan-level decision, not a spec-level requirement.
- **Single-capability scope for v1**: whole-tree/bulk review is a natural future extension of the same toolkit but is explicitly out of scope here.
- **Non-sensitive context only**: application risk, cost, and governance data are excluded from the agent's context in v1 regardless of permissions, to avoid entangling this feature with the sensitive-category authz gates.
- **No rejection-learning loop in v1**: unlike the recommendation engine's accepted/rejected-decision knowledge capture (ADP-SPEC-019), rejected suggestions here have no feedback effect on future reviews.
- **One adapter delivered, reusability proven at the interface level**: this spec ships the toolkit and exactly one adapter (Business Capabilities); a second adapter for a different screen is a future spec, not part of this one. Reusability is demonstrated by the toolkit having no per-domain dependencies (SC-005), not by building a second instance.
- **Reused LLM provider configuration**: the same `ADP_LLM_ENDPOINT`/`ADP_LLM_API_KEY`/model-selection configuration already used by intake and recommendation is reused; no new provider integration.
- **Reused UI interaction conventions**: the review/suggestion review UI follows the same accept/reject, invalidate-on-success conventions already established by the existing proposal and recommendation-option review components; no new design-system primitives are introduced.
- **Cost/token tracking remains at its current state**: existing gaps in LLM cost estimation (not fully implemented across the codebase today) are not fixed by this feature.
