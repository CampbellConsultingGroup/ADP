# Specification Quality Checklist: AI Chat Assistant for Business Architecture Q&A

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-20
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) beyond referencing existing ADP entities/specs
- [x] Focused on user value and business needs (a business architect or business person getting grounded, conversational answers about the portfolio)
- [x] Written for non-technical stakeholders (business architect / business person persona)
- [x] All mandatory sections completed (Constitutional Articles, Threat Model, User Scenarios, Requirements, Success Criteria)

## Requirement Completeness

- [x] Each functional requirement is testable
- [x] Success criteria are measurable and technology-agnostic
- [x] User stories are independently testable and prioritized (P1–P4, ordered by increasing technical risk rather than write-risk, since this feature performs no writes at all)
- [x] Edge cases enumerated (stream interruption, tool-call failure, write-requiring questions, concurrent messages, ambiguous cross-domain questions, context-window growth, unauthorized sensitive-category questions)
- [x] All `[NEEDS CLARIFICATION]` resolved — **7 resolved** in the 2026-07-20 clarification session:
  - Read-only scope (no write/accept-dispatch path, unlike Agent Review)
  - Cross-domain context (business capabilities, applications, portfolio, governance — not page-scoped)
  - Persisted conversation history (new tables, not a transient `OperationStore` operation)
  - Contextual toggle UI entry point (matches the "Review"/"Review Portfolio" pattern)
  - Retrieval strategy: extend `adp.search` (hybrid index) + a fixed read-only tool-call set, not semantic search alone
  - Real-time streamed delivery (new infrastructure), not submit-then-poll
  - Sensitive-category data filtered per the asking user's own permissions, not blanket-excluded (a security-relevant call resolved here, flagged for explicit confirmation before implementation)

## Constitutional Alignment

- [x] ART-V threat model provided, proportional to the broadest read surface of any AI feature in ADP so far (FR-005, FR-009)
- [x] ART-VII grounding required for every entity a reply cites (FR-006)
- [x] ART-II no shadow copy of data — every answer derives from live canonical stores, not a stale cache (FR-002, FR-003)
- [x] ART-IX conversation history itself is the provenance/audit trail, since nothing mutates (FR-008, FR-009)
- [x] ART-XIII typed contracts for every new boundary payload (FR-001, FR-008)
- [x] ART-XV governed schema evolution — this spec, unlike Agent Review, adds new tables via a migration (FR-008, Assumptions)

## Scope & Dependencies

- [x] Existing precedents identified for reuse (`adp.search` hybrid index, the LLM client/config pattern, the grounding validator, the "Review"/"Review Portfolio" UI toggle pattern, existing `READ_APPLICATION_*` sensitive-category permissions)
- [x] MVP identified (US1 — single-domain streamed Q&A proves the toggle → conversation → streamed reply → grounded-citation pipeline before any new retrieval/tool-calling work)
- [x] Assumptions documented (new tables required, streaming is new infrastructure, `ADP-jyu` is a prerequisite fix not in this spec's scope, one entry point delivered with the module built for reuse)
- [x] Reusability requirement stated as a verifiable constraint (FR-010: a reusable panel/toggle component, parameterized like Agent Review's), not deferred to "we'll figure it out when we build a second entry point"
- [x] Known external blocker called out explicitly (`ADP-jyu`, open bug in `/api/v1/search`) rather than silently assumed away

## Notes

This spec deliberately separates the reusable chat module (FR-001–012, FR-015) from its first concrete entry point (FR-013–014) — the same split Agent Review used between its toolkit and its Business Capabilities adapter. Unlike Agent Review, this spec resolves one genuinely security-relevant question itself (sensitive-category filtering, FR-005) rather than deferring it, because the feature's stated use cases would be materially weaker without cost/risk/governance questions working — that resolution should be explicitly re-confirmed before implementation begins, since it's a real security posture decision, not just a scope cut.
