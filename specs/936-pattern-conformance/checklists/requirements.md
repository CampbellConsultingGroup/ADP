# Specification Quality Checklist: EA Pattern Adoptions, Conformance & Discovery

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-14
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs). See note 1.
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders (user stories); corrections table aimed at reviewers
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain (2 resolved with the user on 2026-11-14, 3 informed defaults recorded)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined (6 stories)
- [x] Edge cases are identified (domainless apps, multi-domain apps, out-of-scope pins, cascades, limits, re-seed)
- [x] Scope is clearly bounded (Out of Scope; 937 boundary)
- [x] Dependencies and assumptions identified (934/935, registries, seed scripts)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (conformance, adoptions, transition, discovery, views, dry run)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification beyond the ground-truth table

## Notes

1. As in 921–935, the Ground-Truth Corrections table cites `file:line` evidence of where the source bundle disagrees with the codebase. Real field names appear in FR-005/FR-006 because the snapshot attribute set *is* the authoring contract that pattern authors write expressions against.
2. Found by inspection rather than anticipated by the bundle:
   - GT-1: domains attach only to L1 capabilities, so a parent walk is needed.
   - GT-8: the fixture's backbone selector matches almost everything, so pins must be authoritative.
   - GT-9: `seed_retail.py` is currently broken.
