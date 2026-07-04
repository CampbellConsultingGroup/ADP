---
spec_id: ADP-SPEC-019
title: Recommendation Learning and Knowledge Capture
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-005, ADP-SPEC-007, ADP-SPEC-018]
articles_engaged: [ART-I, ART-III, ART-IV, ART-VII, ART-IX, ART-XIV]
quality_gates: [QG-03, QG-04, QG-13]
owner: enterprise-architecture
---

# ADP-SPEC-019 — Recommendation Learning and Knowledge Capture

## Overview

Two related enhancements to the Architecture Recommendation screen:

1. **Generate recommendations without requiring prior knowledge.** The current pipeline marks all options as "advisory" when the knowledge base is empty and may fail to produce useful options. The LLM must generate architectural options grounded in requirements alone when no knowledge base entries exist, without flagging them as unusable.

2. **Learn from decisions.** When the architect accepts or rejects a recommendation option, the decision (including the reason) is written to the knowledge base as a structured knowledge item. Future recommendation runs can retrieve these prior decisions and learn from them — accepted patterns become positive examples; rejected options become anti-patterns to avoid.

## User Scenarios & Acceptance Criteria

- **Recommend without prior knowledge.** Given an empty knowledge base and confirmed requirements, when recommendations are requested, then Claude generates useful architectural options based on the requirements alone — not an empty or unusable result.
- **Accept with reason.** Given a recommendation option, when the architect accepts it and provides an optional acceptance reason, then the accepted option is saved to the knowledge base as a positive architectural pattern.
- **Reject with reason.** Given a recommendation option, when the architect rejects it and provides a required rejection reason, then the rejected option is saved to the knowledge base as an architectural anti-pattern to avoid.
- **Learning improves future runs.** Given a knowledge base populated by prior decisions, when a new recommendation is requested for similar requirements, then the pipeline retrieves and incorporates those prior decisions in its context.

## Functional Requirements

- **FR-001**: The recommendation pipeline MUST generate useful options when the knowledge base is empty, using requirements alone as context.
- **FR-002**: The accept endpoint MUST accept an optional `acceptance_reason` field alongside `confirmation_id`; the reason is stored with the knowledge item.
- **FR-003**: A `POST /api/v1/designs/{id}/recommend/{op_id}/options/{option_id}/reject` endpoint MUST be added; it requires a non-empty `rejection_reason` and saves the rejected option as an anti-pattern in the knowledge base.
- **FR-004**: Accepted options MUST be written to the knowledge base as a `KnowledgeItem` with: the option title and rationale as content, the `satisfies` requirement IDs as metadata, `item_type="accepted_recommendation"`, and the acceptance reason.
- **FR-005**: Rejected options MUST be written to the knowledge base as a `KnowledgeItem` with: the option title and rejection reason as content, `item_type="rejected_recommendation"`, and the rejection reason.
- **FR-006**: The Recommendation UI MUST show a "Reject" button alongside "Accept" for each pending option; clicking Reject opens a dialog requiring a reason before the rejection is submitted.
- **FR-007**: Accepted and rejected options MUST be visually distinguished from pending options on the Recommendation screen (accepted = green badge, rejected = red/strikethrough).

## Out of Scope

- Re-indexing / re-embedding the knowledge base in real time (the knowledge item is written as text; embeddings are generated on the next `adp-reindex` run)
- Persistent storage of rejection reasons in the canonical design model (reasons are stored in the knowledge base only, not in `ArchitectureDescription`)
- Undo/restore of a rejection decision

## Assumptions

- `KnowledgeItem` and `adp.knowledge.index.KnowledgeIndex` already exist (ADP-SPEC-005); writing to the knowledge base means calling `KnowledgeIndex.add_item()` or the equivalent storage method.
- The knowledge base write does not block the accept/reject HTTP response — it can be a fire-and-forget background write (failure to write to KB does not fail the accept/reject).
- The `advisory` flag should be suppressed when the empty-KB case is handled gracefully — options generated from requirements alone are not "advisory" in the same sense as options without citations; they should be clearly labelled "Generated from requirements (no KB)" rather than a generic advisory warning.
