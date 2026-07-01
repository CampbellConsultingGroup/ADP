# Feature Specification: Knowledge Base & Retrieval

**Feature Branch**: `005-knowledge-retrieval`  
**Created**: 2026-06-29  
**Status**: Draft  
**Input**: User description: "ADP-SPEC-005 — Knowledge Base & Retrieval"

## Constitutional Articles Touched *(mandatory — ART-I)*

- **ART-I** — Spec-Driven Development: always applies
- **ART-II** — The Model is the Single Source of Truth: in scope; the knowledge index stores derived records but MUST NOT become a primary source — canonical knowledge lives in the organization's authoritative systems
- **ART-III** — Everything is Machine-Readable: central concern; all indexed knowledge items carry typed metadata and validate against published schemas (FR-006); citation references are typed
- **ART-IV** — Test-Driven Development: always applies; retrieval accuracy and relationship traversal require tests before implementation
- **ART-V** — Security by Design: in scope; organizational intellectual property is embedded in the index; embedding model selection determines whether that IP crosses an organizational boundary (see Assumptions)
- **ART-VII** — Grounded AI Only: the primary driver of this spec; retrieval is what makes AI outputs grounded and citable; an AI step that cannot cite a knowledge item MUST NOT commit its output (QG-12)
- **ART-IX** — Provenance and Auditability: in scope; every retrieval result carries a citable id and version usable as provenance in AI outputs (FR-005)
- **ART-XIII** — Typed Contracts Everywhere: all knowledge items, retrieval requests, and retrieval results are typed; no unstructured text blobs cross the retrieval boundary
- **ART-XV** — Schema Evolution is Governed: in scope; knowledge item schemas are versioned; re-indexing must preserve version distinguishability (FR-004)

## Threat Model *(mandatory — ART-V)*

The knowledge base stores organizational intellectual property — patterns, standards, prior solutions — in both structured and embedded (vectorized) form. Risk is moderate: the index concentrates sensitive content and its access or exfiltration could reveal architectural strategies.

**Assets at risk**: Organizational architecture patterns, reference architectures, approved solutions, and standards (sensitive IP); embeddings that encode semantic content from those artifacts; the provenance chain between retrieved knowledge and AI-derived recommendations.

**Trust boundaries crossed**: Organization's canonical knowledge sources → indexer → knowledge index; knowledge index → AI retrieval clients (ADP-SPEC-007, ADP-SPEC-008); indexer → embedding model (potential external API boundary, depending on model selection).

**Abuse cases**:
- **IP leakage via external embedding API**: If the embedding model is hosted externally, organizational content is transmitted to a third party during indexing → Mitigation: embedding model selection MUST consider data residency requirements (see Assumptions — this spec requires the decision to be explicit)
- **Index poisoning**: Malicious or unauthorized content in a canonical source is indexed and subsequently cited by AI as authoritative → Mitigation: FR-006 (schema validation on every write); canonical source authentication is a deployment prerequisite
- **Citation forgery**: A retrieval result returns a fabricated id/version that does not correspond to an indexed item → Mitigation: FR-005 (citation-ready id and version on every result); typed contract prevents unvalidated citations
- **Stale citation under schema change**: A breaking schema change renders previously valid citations invalid without warning → Mitigation: FR-004 (version distinguishability on re-index) + ART-XV (schema version embedded in every item)

**Residual risk**: Insider threat with direct index write access (accepted; mitigated by infrastructure-layer access controls); query inference attacks on the vector index (low risk for an internal tool; accepted for v1).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve Grounded Knowledge for an AI Step (Priority: P1)

An AI recommendation step is given a set of design requirements. It queries the knowledge base for relevant patterns, standards, and principles. The retrieval returns a ranked list of typed knowledge items each carrying a stable id and version that can be recorded as a citation in the AI's output.

**Why this priority**: Grounded retrieval is ADP's core value proposition. Without citable knowledge items, no AI output can be committed to the canonical model (ART-VII / QG-12). All other retrieval scenarios build on this foundation.

**Independent Test**: Submit a query representing a set of known requirements against an index pre-loaded with known items; assert that all known-relevant items are returned; assert each result has a non-empty, stable id and version. Tests independently of relationship traversal and re-indexing.

**Acceptance Scenarios**:

1. **Given** a set of requirements, **When** a retrieval query is submitted, **Then** the response contains a ranked list of typed knowledge items each with id, version, type, and relevance context
2. **Given** the same query submitted twice with no index changes, **When** results are compared, **Then** the ids and versions of returned items are identical (stable citations)
3. **Given** a retrieval result, **When** it is passed to an AI step as grounding, **Then** the id and version are sufficient to reconstruct the exact knowledge item used (citation-completeness)

---

### User Story 2 - Keep the Index Current with Upstream Changes (Priority: P1)

An upstream standard is updated in the organization's canonical source. After re-indexing runs, queries against the knowledge base return the new version of the standard. The old version remains distinguishable in the index for any AI outputs that cited it before the update.

**Why this priority**: Stale knowledge produces misleading AI recommendations. Currency is as important as accuracy for governance decisions. Builds on US1 (the index must exist before it can be updated).

**Independent Test**: Index version 1.0 of a standard; update the canonical source to version 1.1; run re-indexing; query and assert the returned item has version 1.1; assert version 1.0 is still resolvable by its original id+version reference.

**Acceptance Scenarios**:

1. **Given** an indexed knowledge item at version 1.0, **When** re-indexing updates it to version 1.1, **Then** subsequent retrieval queries return version 1.1 as the current item
2. **Given** an existing citation referencing item id X at version 1.0, **When** version 1.1 is indexed, **Then** resolving the citation for version 1.0 still returns the correct prior content (version distinguishability)
3. **Given** re-indexing completes, **When** the index is queried, **Then** no item returned by retrieval carries a version that does not exist in the index

---

### User Story 3 - Traverse Knowledge Relationships (Priority: P2)

A validation step asks "which patterns in the knowledge base satisfy architecture principle P-001?" The retrieval system answers using indexed relationships between items — not by matching text — returning a list of patterns that are explicitly linked to that principle.

**Why this priority**: Relationship traversal enables structured governance queries that text-only retrieval cannot reliably answer. Builds on US1 (items must be indexed); independent of re-indexing.

**Independent Test**: Index a set of patterns with explicit "satisfies" relationships to principles; query for patterns satisfying a specific principle; assert only items with the correct relationship are returned; assert an item without the relationship is absent from results.

**Acceptance Scenarios**:

1. **Given** patterns P1 and P2 are indexed with a "satisfies" relationship to principle PR-001, and pattern P3 is not, **When** a relationship query requests "patterns that satisfy PR-001", **Then** P1 and P2 are returned and P3 is not
2. **Given** a relationship query, **When** results are returned, **Then** every result includes the relationship type and direction as part of its typed response
3. **Given** no items with the requested relationship exist in the index, **When** a relationship query is submitted, **Then** an empty list is returned (not an error)

---

### User Story 4 - Provide Citation-Ready References for Every Retrieved Item (Priority: P2)

Every knowledge item returned by any retrieval path — vector, keyword, or relationship — carries a citation reference that an AI step can record as provenance in its output. The citation reference is stable, typed, and sufficient to reconstruct the exact knowledge item used.

**Why this priority**: Citation completeness is the bridge between ART-VII (grounded AI) and ART-IX (provenance). Even if retrieval accuracy is high, AI outputs cannot be committed without citable references.

**Independent Test**: Run retrieval by all three paths (vector, keyword, relationship); for each path, assert every result contains a non-empty id and version; assert the id+version combination resolves to the same item when looked up directly.

**Acceptance Scenarios**:

1. **Given** any retrieval result (from any retrieval mode), **When** the citation reference is extracted, **Then** it contains a non-empty, stable id and a specific version string
2. **Given** a citation reference, **When** the referenced item is resolved by id+version, **Then** the returned item is the exact item retrieved in the original query
3. **Given** a citation reference recorded in an AI output, **When** the citation is validated, **Then** the id and version exist in the knowledge index (no dangling citations)

---

### Edge Cases

- What happens when the canonical source for a knowledge type is unavailable at re-index time?
- How does retrieval behave when the index is empty or contains no items matching the query?
- What happens when a canonical source item fails schema validation during indexing?
- How are duplicate items (same content, different canonical sources) handled?
- What happens when a knowledge item is deleted from the canonical source — does it remain in the index?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each knowledge item MUST be stored as a typed record carrying: a stable identifier, a version, a knowledge type, full text content, structured metadata, and an embedding vector; all fields are required; no field may be absent or untyped
- **FR-002**: The knowledge type taxonomy MUST include at minimum: `pattern`, `reference_architecture`, `standard`, `principle`, and `prior_solution`; the taxonomy MUST be extensible via a governed amendment process
- **FR-003**: Retrieval MUST support three complementary modes: vector similarity (semantic matching), keyword search (exact and fuzzy term matching), and relationship traversal (typed graph edges between items); results from all modes MUST be combinable in a single response
- **FR-004**: Re-indexing MUST update items from their canonical sources and MUST preserve version distinguishability; prior versions of updated items MUST remain resolvable by their id+version reference
- **FR-005**: Every knowledge item returned by any retrieval mode MUST carry a citation-ready reference consisting of a stable id and a specific version; the citation reference MUST be sufficient to reconstruct the exact item
- **FR-006**: Every knowledge item MUST validate against its published schema before being written to the index; items failing validation MUST be rejected with a descriptive error and MUST NOT be indexed

### Non-Functional Requirements

- **NFR-001**: Retrieval latency for a single query against a corpus of up to 10,000 knowledge items MUST be under 500 milliseconds at the 95th percentile, so that the knowledge retrieval step does not dominate AI orchestration latency (see SC-005 for the measurable verification target)
- **NFR-002**: The index MUST support a minimum of 10,000 knowledge items for v1; the architecture MUST be able to scale beyond this via configuration, not code changes

### Key Entities

- **KnowledgeItem**: The central indexed record; carries `id` (stable, opaque), `version` (semver or commit hash from canonical source), `kind` (one of the FR-002 types), `full_text` (the full prose or structured content), `metadata` (typed structured fields specific to the item's kind), `embedding` (the vector representation of the item's content), `source_ref` (a reference to the canonical source and its version)
- **KnowledgeRelationship**: A typed, directed edge between two `KnowledgeItem` records; carries `source_id`, `target_id`, `relationship_type` (e.g., `satisfies`, `extends`, `supersedes`, `implements`)
- **CitationRef**: The citation-ready reference returned with every retrieval result; carries `item_id` and `item_version`; sufficient to reconstruct the exact item used in an AI step
- **RetrievalQuery**: The typed request to the retrieval subsystem; carries the query text, optional required `kind` filters, optional relationship traversal parameters, and optional result count limit
- **RetrievalResult**: The typed response from the retrieval subsystem; carries a ranked list of (`KnowledgeItem`, `CitationRef`, `relevance_score`, `match_reason`) tuples

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Retrieval returns at least one item with a valid citation for 95% of well-formed queries against a corpus of pre-indexed items covering all five knowledge types; verified by accuracy tests with known-relevant items
- **SC-002**: After re-indexing a changed item, the updated version is the top result for queries that would have previously returned the old version; old version remains resolvable by its citation; verified by versioning tests
- **SC-003**: Relationship queries correctly identify all explicitly indexed relationships without text matching; precision and recall are both ≥ 95% on a representative set of known relationships; verified by relationship traversal tests
- **SC-004**: 100% of retrieval results across all three modes carry a non-empty, valid citation (id + version); zero results returned without a citation; verified by citation completeness tests
- **SC-005**: Retrieval completes in under 500 milliseconds at p95 for queries against a 10,000-item corpus in a representative deployment environment; verified by performance tests

## Assumptions

- **Canonical sources (resolved)**: Patterns, reference architectures, standards, and principles are sourced from one or more Git-managed documentation repositories (content in Markdown or YAML). Prior solutions are the approved `ArchitectureDescription` records retrieved from the ADP-SPEC-002 design store. Two connectors are required for v1: a Git repository connector and an ADP design store connector. Re-index cadence is nightly for all knowledge types; on-demand re-index is out of scope for v1.
- **Embedding model (resolved)**: The embedding model is self-hosted and open-source. No organizational knowledge content is transmitted to external services during indexing or retrieval. The specific model selection is a deployment decision and not fixed by this spec; the architecture must support model replacement without re-engineering the indexing pipeline.
- The knowledge base indexes canonical content — it does not become a fork. If a canonical item is updated, re-indexing reflects the update; ADP does not maintain its own edited copy.
- Knowledge item deletion from a canonical source is handled conservatively for v1: deleted items are marked inactive in the index but not physically removed, so existing citations remain resolvable. Physical deletion requires an explicit governance action.
- The taxonomy in FR-002 is the v1 baseline; new knowledge types are added via a spec amendment and a schema version bump per ART-XV.
- SC-003's "95% precision and recall" target is verified for v1 against hand-crafted representative test fixtures (T028–T030); a labeled evaluation corpus for production-accuracy measurement is a v2 prerequisite and is out of scope here.

## Out of Scope

- The recommendation logic that consumes retrieval results (ADP-SPEC-006/007)
- The validation logic that consumes retrieval results (ADP-SPEC-008)
- Authoring or editing knowledge items within ADP (knowledge is consumed from canonical sources, not created here)
- User-facing search or browse interface for the knowledge base
- Multi-lingual knowledge items for v1
- Fine-tuned or domain-adapted embedding models (v1 uses an out-of-the-box model)
