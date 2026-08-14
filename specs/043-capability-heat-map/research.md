# Research: Capability Heat Map

No `[NEEDS CLARIFICATION]` markers remain in `spec.md` (resolved via `/speckit-clarify` on 2026-08-14). This
document records the implementation-level decisions made while translating the spec into a plan.

## Decision 1: No new backend endpoint

**Decision**: Build entirely on the existing `GET /api/v1/business/capabilities` endpoint and the existing
`useCapabilities()` frontend hook — no new route, no new response model, no new hook.

**Rationale**: plan.md's Ground-Truth Research confirms the existing `BusinessCapability` response already
carries every field the heat map needs (`level`, `parent_id`, `position`, `strategic_relevance`,
`maturity_level`), unfiltered and unpaginated — the same data `CapabilityTree.tsx` already fetches and
renders today. Duplicating that fetch behind a second endpoint would be a second source of truth for the
same read (violating ART-II) for no benefit.

**Alternatives considered**:
- *A dedicated `/capabilities/heatmap` aggregate endpoint* (mirroring 919's own `applications-heatmap`
  pattern): rejected — 919 needed a new endpoint because it had to compute a derived field (`cost` via
  `ApplicationCost.tco`) and enforce a permission check the existing list endpoint didn't do. Neither
  applies here: every field is already on the existing capability record, and capability reads are not
  permission-gated at all (spec.md's own Assumptions).

## Decision 2: Reuse `buildTree()` for hierarchy construction

**Decision**: Import and reuse `CapabilityTree.tsx`'s already-exported `buildTree(items: BusinessCapability[]):
CapabilityTreeNode[]` to construct the L1/L2/L3 hierarchy for the heat map, rather than writing a second
tree-building function.

**Rationale**: `buildTree()` is pure, already unit-tested (`test_default_position`/`test_optional_fields_
default_none`-adjacent coverage exists for the underlying model, and `buildTree` itself has direct test
coverage in `CapabilityTree.test.tsx`), and is the exact hierarchy the resolved FR-002 clarification requires
the heat map to match ("flat L1/L2/L3 hierarchy... matching the existing capability tree's own rendering
exactly"). Reimplementing the same parent/child/position logic a second time would risk the two views
silently drifting apart.

**Alternatives considered**:
- *Move `buildTree()` to a shared utility module* (e.g. `web/src/business/tree.ts`) before importing it from
  two components: considered but deferred — `buildTree()` has no dependency on anything specific to
  `CapabilityTree.tsx` today, so a plain cross-component import is fine for two consumers; revisit only if a
  third consumer appears.

## Decision 3: Drill-through target (US3/FR-008) is a scroll-and-highlight, not a new page

**Decision**: Clicking a heat-map cell switches `BusinessPage`'s tab to "Capabilities" and scrolls that
capability's existing row (in `CapabilityTree`) into view with a brief highlight — it does not navigate to a
new, separate detail screen.

**Rationale**: plan.md's Ground-Truth Research #2 confirms no such separate detail screen exists for
capabilities anywhere in the platform today (unlike Value Streams/Domains, which do have one). Building a
new one would be a significantly larger, out-of-scope change this spec never asked for; "that capability's
existing detail view" (spec.md's own wording) is satisfied literally by the inline-expandable row that
already carries every detail affordance (edit fields, Links panel, Agent Review) — matching what a user
already sees today by navigating to the Capabilities tab directly and finding that row themselves. Every row
defaults to expanded (`CapabilityNode.tsx`'s `useState(true)`), so no ancestor-expansion step is needed —
only a scroll.

**Alternatives considered**:
- *Build a new dedicated capability detail page*: rejected as out of scope — would require inventing a
  master/detail pattern for capabilities that doesn't exist today, a materially larger change than "drill
  through to existing detail" implies.
- *Open the row's detail inline directly from the heat map, without switching tabs*: rejected — the heat map
  and the tree are different visual representations of the same data; showing tree-only affordances (edit
  fields, Agent Review) inside the heat map's cells would blur the two views' distinct purposes (FR-001's
  "dense, scannable" grid vs. the tree's management UI).

## Decision 4: Strategic relevance uses a 3-step subset of the same swatch palette

**Decision**: `maturity_level` (1-5) reuses `ApplicationsHeatMap.tsx`'s existing 5-step `FIVE_STEP` swatch
array unchanged. `strategic_relevance` (1-3: Strategic/Core/Supporting) uses a distinct, purpose-built
3-step subset of the same visual language (crit/warn/good tokens) rather than mapping 3 values onto 5 slots
with awkward gaps.

**Rationale**: Reusing the exact same *tokens* (`var(--crit)`, `var(--warn)`, `var(--good)`, etc.) keeps the
two metrics visually consistent with each other and with 919's applications heat map, satisfying the
"established, unambiguous convention" the spec's own Assumptions call for — without forcing an artificial
1-5 stretch onto a genuinely 3-valued field.

**Alternatives considered**:
- *Stretch strategic_relevance's 3 values across the same 5-step array* (e.g. indices 0, 2, 4): rejected —
  produces an arbitrary, harder-to-reason-about mapping for no real benefit over a dedicated 3-step scale.
