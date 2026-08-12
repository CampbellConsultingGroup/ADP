# Implementation Plan: C4 Diagram Type in the Diagram Tool

**Branch**: `053-c4-diagram-type` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/053-c4-diagram-type/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Adds `"c4"` as a sixth selectable value on the diagram tool's existing `DiagramType` enum (today:
`flowchart | sequence | erd | uml | architecture`). The Mermaid-C4 parser/serializer
(`web/src/diagrams/core/dsl/c4.ts`) and its `dslFamilies` registry entry (`registry.ts:23`) already
exist and are structurally complete (`C4Context/Container/Component/Dynamic/Deployment`, the full
element-kind × `Db/Queue/_Ext` matrix, boundaries, styling macros) — they are simply unreachable
today because no `DiagramType` value routes to them. This is Phase A of the C4Canvas-retirement
roadmap (ADP-914.9); it is entirely additive, has zero coupling to ADP's separate canonical
`Design`/`Element`/`Relationship` model, and does not touch `web/src/canvas/` at all.

The one real implementation wrinkle: unlike the other five families, `c4` is a multi-level family —
`model.diagramTypeId` must be a level-specific value (`c4-context`, matching `c4.ts`'s
`LEVEL_TO_HEADER`), not the bare family name `"c4"` the app-level `DiagramType`/`dslFamily` selector
uses. A brand-new C4 diagram must be seeded with `createEmptyDiagramModel("c4-context")`, not
`createEmptyDiagramModel("c4")`, or `serializeC4` degrades silently to its `"C4Context"` fallback
header for a reason unrelated to the user's intent.

## Technical Context

**Language/Version**: TypeScript 5.x + React 18 (frontend); Python 3.12 (backend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: None new. Reuses the already-vendored `web/src/diagrams/core/dsl/c4.ts` parser/serializer and its `dslFamilies` registry entry (`registry.ts:23`); Pydantic v2 `Literal` (backend); existing FastAPI/SQLAlchemy stack — zero new packages either side.
**Storage**: No schema change. `diagrams.diagram_type` is stored as plain `TEXT` (not a Postgres enum), per migration 024 — confirmed by reading the migration directly; the value set is enforced only at the Pydantic `Literal` layer, so adding `"c4"` needs no migration at all.
**Testing**: Vitest (frontend: `families.test.ts` round-trip pattern, `DiagramEditorPage.test.tsx`); pytest (backend: `tests/unit/diagrams/test_diagrams_models.py`, `tests/contract/test_diagrams_api_contract.py`) — all existing suites, extended in place.
**Target Platform**: Browser (existing `web/` SPA) + existing FastAPI backend — no new deployable, no new route.
**Project Type**: Web application, frontend + backend slice of the existing ADP split.
**Performance Goals**: None specific — adding one `Literal` value and one array entry has no measurable performance surface.
**Constraints**: `web/src/diagrams/core/` (the vendored parser/serializer/registry) MUST NOT be modified per this session's established vendoring convention (research.md Decision 1 of ADP-SPEC-052, reaffirmed here) — `c4.ts`/`registry.ts` are already complete and correct; this feature only adds *callers* that reach them, never edits them. Zero coupling to `web/src/canvas/`, `adp.store`, or the canonical `Design`/`Element`/`Relationship` model (spec.md FR-009) — confirmed no shared code path exists between the two systems (ADP-914.9's research).
**Scale/Scope**: 2 files change on each side to add the value itself (`src/adp/diagrams/models.py`'s `DiagramType` Literal; `web/src/diagrams/DiagramEditorPage.tsx`'s `DIAGRAM_TYPES` array + the create-time `diagramTypeId` seeding fix); 1 new frontend test file (`web/src/diagrams/core/dsl/c4.test.ts` — the c4 family currently has **zero** test coverage anywhere in the repo, a real gap this feature closes, not just plumbing); 4 existing test files updated in place (2 backend, 2 frontend) whose parametrized "supported types" lists and one "rejects `c4` as unsupported" negative test now need to change, since `c4` is exactly what stops being unsupported.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, zero `NEEDS CLARIFICATION`) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II, ART-III (Model is Source of Truth / Machine-Readable) | No | The canonical `ArchitectureDescription` model is untouched — this feature's data (a `Diagram`'s `dsl_source` text) is already outside that model's scope, unchanged by this feature (spec.md FR-009). |
| ART-IV (TDD) | Yes | tasks.md sequences failing tests before implementation in every user-story phase — including the genuinely new `c4.test.ts` round-trip coverage this feature adds (Scale/Scope above), not just the plumbing-level tests. |
| ART-V (Security by Design) | Yes | Threat model in spec.md: no new trust boundary, no new data exposure — reuses the diagram tool's existing `WRITE_DIAGRAM`-gated create/edit/delete flow unchanged for every type including this new one. |
| ART-VI (Observability) | No, beyond ordinary | No new telemetry surface, no AI step. |
| ART-VII–XI (AI/traceability articles) | No | No AI-generated content, no new audit obligation, no traceability-thread change — standalone diagrams carry none of this today and this feature doesn't add any. |
| ART-XII (Fixed Visual Language) | No | Governs the locked C4 rendering theme used for canonical `Design` exports specifically (ADP-SPEC-010) — explicitly a different, ungoverned rendering path (spec.md's own Assumptions section draws this line; also the subject of a carried-forward constraint for the *later* Phase B/C work, not this one). |
| ART-XIII (Typed Contracts Everywhere) | Yes | The one boundary change is a `Literal` extension on `DiagramType`, still `extra="forbid"`-validated, still generated into the OpenAPI contract — not hand-maintained, not an untyped dict. |
| ART-XIV, ART-XV (Reproducible builds / Schema evolution) | Yes (lightly) | Additive, backward-compatible `Literal` value addition — no migration, no version bump needed (the field is stored as plain `TEXT`, not a DB-level enum). `adp-generate --check` re-run to confirm no drift. |
| ART-XVI (Documentation as Code) | Yes (SHOULD) | This plan + research.md + data-model.md, each decision grounded in a direct read of the file it changes. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** — this is the smallest possible change that satisfies the spec: two `Literal`/array additions, one seeding-logic fix, and closing a pre-existing test-coverage gap.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly the additive design described above; no new gate is implicated by the detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/053-c4-diagram-type/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── diagram-type-contract.md   # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/diagrams/models.py                  # MODIFIED — DiagramType Literal gains "c4".

web/src/diagrams/api.ts                     # MODIFIED — mirrored frontend DiagramType union.
web/src/diagrams/DiagramEditorPage.tsx      # MODIFIED — DIAGRAM_TYPES array gains "c4"; the
                                            #   create-a-brand-new-diagram seeding logic gains
                                            #   the "c4" -> "c4-context" diagramTypeId mapping
                                            #   (Summary's implementation wrinkle) so a new C4
                                            #   diagram starts at Context level, not an
                                            #   accidentally-mislabeled empty model.

web/src/diagrams/core/dsl/c4.test.ts        # NEW — round-trip coverage for parseC4/serializeC4,
                                            #   mirroring families.test.ts's existing per-family
                                            #   pattern (flowchart/erd/architecture/sequence/uml
                                            #   each already have one; c4 currently has none at
                                            #   all anywhere in the repo).

tests/unit/diagrams/test_diagrams_models.py         # MODIFIED — "c4" added to the parametrized
                                                    #   accepted-types list; the existing
                                                    #   "rejects unsupported type" negative test's
                                                    #   example value changes away from "c4"
                                                    #   (it's what stops being unsupported).
tests/contract/test_diagrams_api_contract.py        # MODIFIED — same two changes, contract-test
                                                    #   equivalent (2 call sites: the parametrized
                                                    #   create test, and the list/filter test).
web/src/diagrams/DiagramEditorPage.test.tsx         # MODIFIED — the "every type present, only one
                                                    #   recommended" test's `toHaveLength(5)` and
                                                    #   hardcoded 5-type array both become 6/+"c4".

web/src/diagrams/core/dsl/c4.ts             # UNCHANGED (vendored) — already complete; this
web/src/diagrams/core/dsl/registry.ts       #   feature adds callers, never edits either file
                                            #   (Technical Context Constraints).
web/src/canvas/**                           # UNCHANGED — zero coupling, confirmed (Summary).
```

**Structure Decision**: No new package, no new route, no new table, no new component. The two
`Literal`/array edits are the entire "feature" surface; everything else in this list is either a
one-line seeding-logic fix or test-file maintenance made necessary by that same one-line change
(existing tests that specifically asserted `"c4"` was *rejected* must now assert the opposite) or
by closing the pre-existing zero-coverage gap on `c4.ts` itself.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
