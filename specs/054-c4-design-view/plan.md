# Implementation Plan: C4 Design View

**Branch**: `054-c4-design-view` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/054-c4-design-view/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Replaces `web/src/canvas/C4Canvas.tsx` (legacy ReactFlow-based) as the editing surface for a
design's canonical C4 model, building on the diagram tool's own, now-well-styled editor
(`web/src/diagrams/editor/Canvas.tsx`, ADP-SPEC-052) instead. This is Phase B of the C4Canvas
retirement roadmap; unlike Phase A (ADP-SPEC-053), this feature edits ADP's **canonical**
`ArchitectureDescription`/`Element`/`Relationship` records — the same governed data C4Canvas
already reads/writes today — not the separate, standalone `Diagram`/DSL concept.

The core technical shape: a new **adapter** layer converts `Element[]`/`Relationship[]` (filtered
to one C4 level, reusing the existing `filterElementsForLevel`/`filterRelationshipsForLevel`
helpers) into a `DiagramModel` the reused `Canvas.tsx` can render/edit, via `core/dsl/c4.ts`'s
already-vendored `parseC4`/`serializeC4` as the transcoding core (ADP-SPEC-053's own research).
Unlike the standalone diagram tool's "stage locally, save the whole DSL text on click" flow, this
feature's canvas interactions **commit immediately per action** — matching C4Canvas's own existing
behavior — so a **reconciliation layer** diffs each `Canvas.tsx` `onChange(model)` callback against
the previous model and fires the specific new granular backend endpoint (create/rename/delete one
element or relationship) rather than ever replacing the whole design at once. Those endpoints
replace the currently-broken whole-design `PUT` `usePlaceElement`/`useDrawRelationship` call today
— confirmed via direct source read that no such route exists — and are the actual fix for
ADP-914.1–.4.

Three real findings from research materially shaped this plan, each corrected in spec.md in the
same pass (ART-I): **container/boundary grouping was descoped** (confirmed C4Canvas never had it
either, and the canonical model has no field for it — new schema scope was not silently smuggled
in); **layout position "migration" is not a migration at all** — `design_layouts` (`layouts.py`)
is an in-process, transient dict, not a real table, so FR-013 is satisfied simply by having the new
view keep calling the *same, unmodified* `GET/PUT .../layout/{level}` endpoints C4Canvas already
calls, not a data-migration script; and **optimistic concurrency (`expected_version`) already
exists in `DesignStore.save()` but is used by zero existing endpoints today** — this feature
follows that same established precedent (no `expected_version`) rather than being the first to
adopt it, keeping scope bounded per spec.md's own explicit deferral of conflict-notification UI.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript 5.x + React 18 (frontend) — both existing stacks, no new language/version surface.
**Primary Dependencies**: None new. Backend: FastAPI, SQLAlchemy 2 async (Core), Pydantic v2 — all existing. Frontend: reuses `web/src/diagrams/editor/Canvas.tsx`/`DslPanel.tsx` (ADP-SPEC-052, unmodified), `core/dsl/c4.ts`'s `parseC4`/`serializeC4` (ADP-SPEC-053, unmodified), `web/src/canvas/c4-filter.ts`'s `filterElementsForLevel`/`filterRelationshipsForLevel` (unmodified), `web/src/inspection/InspectionPanel.tsx`/`TechnologyEditor.tsx` (unmodified) — all pre-existing.
**Storage**: No schema change to `ArchitectureDescription`/`Element`/`Relationship` — every new endpoint reads/writes the existing `designs`/`design_versions` tables via the existing `DesignStore.save()`/`.get()`. No migration.
**Testing**: pytest (backend: new `tests/unit/elements/`, `tests/contract/test_elements_api_contract.py`, mirroring `tests/unit/diagrams/`/`tests/contract/test_diagrams_api_contract.py`'s own structure); Vitest + React Testing Library (frontend: new adapter/reconciliation unit tests, new view component tests) — existing tooling only.
**Target Platform**: Browser (existing `web/` SPA) + existing FastAPI backend — no new deployable.
**Project Type**: Web application, frontend + backend slice of the existing ADP split.
**Performance Goals**: None specific beyond existing design-mutation endpoints' own characteristics (each new endpoint does the same single-design read-modify-write `DesignStore.save()` every existing mutation endpoint already does).
**Constraints**: `web/src/diagrams/editor/Canvas.tsx` and every other vendored file (`shapes.tsx`, `DslPanel.tsx`, `useDslSync.ts`, `ConfirmDialog.tsx`, `UnsupportedElementNotice.tsx`, `core/dsl/*`) MUST NOT be modified — same convention as ADP-SPEC-052/053. `web/src/canvas/` (C4Canvas and its supporting files) MUST NOT be deleted or have its behavior changed by this feature — that is explicitly Phase C (ADP-914.13), gated on this feature landing and being confirmed equivalent-or-better first (spec.md Assumptions). No change to the canonical `ArchitectureDescription`/`Element`/`Relationship` Pydantic model shape (no new fields) — container/boundary grouping and Db/Queue/`_Ext` C4-sub-kind distinctions are consciously not added to the canonical model in this feature (see research.md Decisions 1 and 6).
**Scale/Scope**: 5 new backend endpoints (`POST`/`PATCH`/`DELETE` elements, `POST`/`DELETE` relationships) in a new `src/adp/api/routers/elements.py`, mirroring `tags.py`'s exact structure; 1 new frontend adapter module (`web/src/canvas-v2/c4Adapter.ts` — the `Element[]`/`Relationship[]` ⇄ `DiagramModel` mapping) plus 1 new reconciliation module (`web/src/canvas-v2/reconcile.ts` — diffs `Canvas.tsx`'s `onChange` output and fires the right granular endpoint); 1 new top-level view component (`web/src/canvas-v2/C4DesignView.tsx`, the `Workspace.tsx`/`C4Canvas.tsx` replacement) reusing `InspectionPanel.tsx`/`TechnologyEditor.tsx` unchanged via an explicit element picker (not click-to-select on the vendored canvas — research.md Decision 4). Reached via a **new, separate** route/nav affordance during this phase (not a swap of the existing "Canvas" nav item — that swap is explicitly Phase C's job, per the already-approved roadmap's own phase boundaries).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Applies? | How this feature satisfies it |
|---|---|---|
| ART-I (SDD Mandatory) | Yes | spec.md (16/16 checklist, 3 clarifications resolved, 1 further correction made and reflected back into spec.md during this planning pass) → this plan → tasks.md (next command) → implementation, in order. |
| ART-II, ART-III (Model is Source of Truth / Machine-Readable) | Yes | This feature is a new editing surface for the existing canonical model — reads/writes real `Element`/`Relationship` records via the existing `DesignStore`, never a shadow copy. Deliberately does **not** expand the canonical model's shape (research.md Decisions 1, 6) to avoid an undiscussed schema change riding along with a UI migration. |
| ART-IV (TDD) | Yes | tasks.md will sequence failing tests before implementation in every user-story phase, both backend (new endpoint contract tests) and frontend (adapter/reconciliation unit tests, new view tests). |
| ART-V (Security by Design) | Yes | Threat model in spec.md. Every new endpoint reuses the existing `WRITE_DESIGN` permission gate via `enforcement.py`'s per-route table, matching `PUT .../elements/{id}/tags`'s exact existing entry style — no new trust boundary. |
| ART-IX (Provenance and Auditability) | Yes | Every new endpoint appends an `AuditEntry` before `store.save()`, mirroring `tags.py`'s exact pattern (`"create-element"`/`"update-element"`/`"delete-element"`/`"create-relationship"`/`"delete-relationship"` actions, human origin). |
| ART-XI (Traceability End to End) | Yes | Element deletion cascades to remove its relationships first (confirmed required: `ArchitectureDescription`'s own `model_validator` calls `validate_references`, which raises on any relationship pointing at a non-existent element — `store.save()` would hard-fail otherwise). `satisfies`/`provenance` are read but never touched by any new endpoint (FR-011/FR-012). |
| ART-XII (Fixed Visual Language) | Yes | Export reuses the *existing* `POST /designs/{id}/render` (locked theme) and `GET /designs/{id}/export/calm` endpoints unchanged — confirmed both already exist and already do exactly what FR-009/FR-010 require; zero backend change needed for export. The new view's own canvas rendering (`Canvas.tsx`'s live editing surface) is explicitly *not* subject to ART-XII — that article governs the locked *export* theme specifically, not every screen that happens to display a C4 element. |
| ART-XIII (Typed Contracts Everywhere) | Yes | New `ElementCreate`/`ElementUpdate`/`RelationshipCreate` Pydantic models, `extra="forbid"`, generated into the OpenAPI contract — matching `tags.py`'s `TagsRequest`/`TagsResponse` convention exactly. |
| ART-VI–VIII, X, XIV–XVI | No, beyond ordinary | No new observability surface beyond what mutation endpoints already carry (existing `logger.info` pattern reused); no AI step; no deterministic-gating concern; no schema/migration change at all (Storage above); standard documentation expectations. |

**Initial gate result**: PASS. No article is violated. **No Complexity Tracking entry is needed** —
every design decision in this plan (reuse existing endpoints for export/layout rather than
building new ones; don't expand the canonical model; don't touch vendored files; follow the
existing no-`expected_version` precedent) picks the option that adds the least new surface area
consistent with correctly satisfying the spec, not the most.

**Post-Phase-1 re-check**: PASS (unchanged) — data-model.md and contracts/ below implement exactly
the additive, precedent-following design described above; no new gate is implicated by the
detailed design.

## Project Structure

### Documentation (this feature)

```text
specs/054-c4-design-view/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── elements-api-contract.md   # Phase 1 output (/speckit.plan command)
├── checklists/
│   └── requirements.md
└── tasks.md               # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/adp/api/routers/elements.py           # NEW — 5 endpoints (create/rename/delete element,
                                          #   create/delete relationship), mirroring tags.py's
                                          #   exact fetch-mutate-audit-save structure.
src/adp/authz/enforcement.py              # MODIFIED — 5 new (method, path) -> ActionType.WRITE_DESIGN
                                          #   entries in the existing per-route dict, matching the
                                          #   designs domain's established exact-path convention
                                          #   (not the newer prefix-rule style other domains use).
src/adp/api/app.py                        # MODIFIED — mount the new elements router (one line,
                                          #   matching every other router's existing mount call).

web/src/canvas-v2/c4Adapter.ts             # NEW — Element[]/Relationship[] + C4Level -> DiagramModel
                                          #   and back, via core/dsl/c4.ts's role vocabulary (an
                                          #   exact string match with ElementKind, no mapping table
                                          #   needed) and shapes.tsx's existing shape set.
web/src/canvas-v2/reconcile.ts             # NEW — diffs Canvas.tsx's onChange(model) output against
                                          #   the previous model; fires the specific granular
                                          #   endpoint for whatever actually changed (add/rename/
                                          #   delete one element, add/delete one relationship);
                                          #   reconciles Canvas-generated temporary node/edge ids
                                          #   with the real ELM-xxx/REL-xxx ids the backend returns.
web/src/canvas-v2/C4DesignView.tsx         # NEW — the Workspace.tsx/C4Canvas.tsx replacement:
                                          #   level switcher (reusing Workspace.tsx's existing
                                          #   LEVELS array convention), the reused Canvas.tsx wired
                                          #   through the adapter+reconciler, an element picker
                                          #   driving InspectionPanel.tsx (research.md Decision 4),
                                          #   and Export actions calling the existing render/CALM
                                          #   endpoints directly (no new export code).
web/src/canvas-v2/*.test.ts(x)             # NEW — adapter round-trip tests, reconciliation-diff
                                          #   tests, view-level integration tests.

web/src/App.tsx                           # MODIFIED — new route/nav entry point to reach
web/src/ui/AppShell.tsx                   #   C4DesignView, additive alongside the existing
                                          #   "Canvas" item (not a replacement — Phase C's job).

web/src/diagrams/editor/Canvas.tsx        # UNCHANGED (vendored) — reused as-is, including its
web/src/diagrams/editor/shapes.tsx        #   already-existing toolbarContainer portal (no new
web/src/diagrams/core/dsl/c4.ts           #   prop/callback added — research.md Decision 4 avoids
web/src/inspection/InspectionPanel.tsx    #   needing one). InspectionPanel.tsx/TechnologyEditor.tsx
web/src/inspection/TechnologyEditor.tsx   #   reused unchanged, driven by a new picker, not canvas
                                          #   click-selection.
web/src/canvas/**                         # UNCHANGED — C4Canvas and everything under it stays
                                          #   exactly as it is; this feature does not touch it.
src/adp/api/routers/layouts.py            # UNCHANGED — the new view calls the same existing
src/adp/api/routers/render.py             #   layout/render/CALM-export endpoints C4Canvas already
src/adp/api/routers/calm.py               #   calls today, verbatim. Zero backend change for
                                          #   FR-009/FR-010/FR-013.
```

**Structure Decision**: A new, self-contained frontend module (`web/src/canvas-v2/`) rather than
editing `web/src/canvas/` in place — keeps the legacy screen fully intact and untouched (so Phase C
can cleanly delete it later) while the new one is built and proven alongside it. One new backend
router file, following the same per-concern-router pattern `layouts.py`/`tags.py` already
establish, rather than growing `designs.py` itself. Every already-solved concern (export,
technology tags, position storage, level-visibility filtering) is reused verbatim from existing
code — this feature's only genuinely new surface is element/relationship CRUD and the two frontend
modules that bridge the canonical model to the reused canvas component.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table intentionally omitted.
