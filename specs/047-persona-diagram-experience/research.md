# Phase 0 Research: Persona-Differentiated Diagram Experience

No `NEEDS CLARIFICATION` markers remain in the Technical Context — this feature's scope is narrow
enough that all three of the originating request's open questions were already resolved directly
in spec.md's Assumptions section with documented, reversible defaults. The decisions below record
*how* those defaults get implemented, confirmed by direct reads of the actual code rather than
assumed.

## Decision 1: Where does the signed-in user's role come from?

**Decision**: `useAuth().user?.role` (existing hook, `web/src/auth/AuthProvider.tsx`) — no new state, no new API call.

**Rationale**: Confirmed by direct read of `AuthProvider.tsx` that this is both available and race-free
by the time any page component mounts: `AuthProvider` renders a full-screen "Signing in…" placeholder
and withholds all children (including whatever page is active) until `isLoading` resolves to `false`.
When `VITE_AUTH_ENABLED=true`, that only happens after `initKeycloak()` resolves and `user` is set from
the parsed token. When `VITE_AUTH_ENABLED=false` (the project's dev/test default), `isLoading` resolves
to `false` immediately and `user` stays `null` for the session — which is exactly spec.md's Edge Case
("role cannot be determined → fall back to today's default, no recommendation shown"), not a gap to
paper over.

**Alternatives considered**:
- A fresh `/api/v1/me`-style backend call to fetch role independently — rejected: would introduce a new
  network round-trip and a new (however small) backend surface for data the frontend already has
  synchronously via the existing auth context, directly contradicting the spec's "zero backend change"
  constraint for no real benefit.
- Reading `role` via prop-drilling from `App.tsx` — rejected: `useAuth()` is already the established,
  used-elsewhere pattern (`AppShell.tsx`'s `roleLabel`/`roleColors` badge) for exactly this kind of
  read; prop-drilling would just be a longer path to the same context value.

## Decision 2: Persona → diagram-type mapping values

**Decision**: Enterprise Architect → `architecture`, Solution Architect → `flowchart`, Technical Architect → `sequence`.

**Rationale**: `src/adp/authz/permissions.py`'s actual per-role `PERMISSION_GRANTS` were checked directly
as a potential data-driven signal first — Solution Architect and Technical Architect turn out to differ
by only two actions (`OVERRIDE_VERDICT`, `EXPORT_DESIGN`), and Enterprise Architect holds a near-total
wildcard grant; none of that differentiates along diagram-type lines. With no existing in-codebase signal
to lean on, the mapping falls back to a documented, defensible convention (spec.md's Assumptions) drawn
from each role's typical scope of work already visible elsewhere in ADP: Enterprise Architect operates at
the cross-system/enterprise view (closest fit: `architecture`, ADP's cloud/system-landscape diagram type);
Solution Architect works through solution/process design (closest fit: `flowchart`, process/decision-flow
diagrams); Technical Architect works at technical-integration detail (closest fit: `sequence`,
system-to-system interaction diagrams). `erd` and `uml` remain fully selectable by every role — nobody's
*default*, per spec.md's explicit "steering, not restriction" decision.

**Alternatives considered**:
- Deriving the mapping from real usage data (which role actually creates which diagram type most, once
  the feature has been live a while) — rejected for v1: no usage data exists yet (ADP-SPEC-046 only just
  shipped), and spec.md already flags this mapping as "expected to be revisited... a one-line constant
  edit, not a structural change" — the right sequencing is ship a reasonable default now, refine later
  with real data, not block v1 on data that doesn't exist yet.
- A 3-way even mapping onto only 3 of the 5 types with `erd`/`uml` left as second-class — considered and
  rejected implicitly by FR-004/FR-005: no type is disabled or reordered out of reach; `erd`/`uml` are
  exactly as reachable as the 3 mapped types, just without a role's default landing on them.

## Decision 3: Where does the persona-aware default get computed?

**Decision**: Inside `DiagramEditorPage.tsx`'s own existing `newDiagramType ?? "flowchart"` fallback
(becomes `newDiagramType ?? recommended ?? "flowchart"`) — not in `DiagramsPage.tsx`, the call site.

**Rationale**: Confirmed by direct read of `DiagramsPage.tsx` (ADP-914.5) that it already renders
`<DiagramEditorPage diagramId={mode.diagramId} onSaved={...} />` for the "+ New Diagram" flow *without*
passing an explicit `newDiagramType` prop — meaning `DiagramEditorPage`'s own internal fallback is
already the single point where "what type does a brand-new diagram start as" gets decided today. Moving
that decision to the call site would require `DiagramsPage.tsx` to also call `useAuth()` and duplicate
the mapping lookup, for no behavioral difference. Keeping it in `DiagramEditorPage.tsx` also naturally
satisfies FR-005 (the "Recommended" label in the type `<select>`) from the same `useAuth()` call and the
same `recommended` value, in the same file — one role lookup, two related outcomes (initial value +
visual label), not two.

**Alternatives considered**:
- Computing it in `DiagramsPage.tsx` and passing `newDiagramType={recommended}` explicitly — rejected:
  would still need a *second*, independent role lookup inside `DiagramEditorPage.tsx` anyway for the
  "Recommended" label (FR-005), since the label needs to know the recommended type regardless of what
  was passed in as the initial default (a user could later be shown the badge on an option they haven't
  selected). Two lookups for one concern is worse than one lookup that serves both concerns.

## Decision 4: How is the "Recommended for your role" indicator shown?

**Decision**: Append `" (Recommended for your role)"` to the matching type's `<option>` text inside the
existing `<select aria-label="Diagram type">` — not a separate badge element outside the select.

**Rationale**: The existing type selector is a plain HTML `<select>`/`<option>` pair (`DiagramEditorPage.tsx`,
confirmed by direct read) — `<option>` elements can only render text content, not arbitrary styled markup
(no icons, no colored badge span). A text suffix on the matching option is therefore the only option-level
way to satisfy FR-005 without restructuring the selector into a different UI control (e.g. a custom
listbox/menu), which spec.md's narrow scope doesn't call for and which would be a materially larger,
riskier change for a presentation-only feature. It is also trivially testable (`screen.getByText(...)`
against the option's accessible text), matching this project's existing frontend test conventions.

**Alternatives considered**:
- Replacing the native `<select>` with a custom dropdown/listbox component to allow richer per-option
  styling (icon, colored badge) — rejected: a materially larger UI change than this feature's scope
  warrants (spec.md SC-002/SC-003 only require the recommendation to be identifiable "at a glance," which
  a clear text suffix already satisfies), and would touch `Canvas.tsx`/`shapes.tsx`-adjacent styling
  conventions this feature has no reason to open up.
- A separate helper line below the `<select>` (e.g. "Recommended: sequence") instead of in-option text —
  considered viable but rejected as strictly worse: it doesn't co-locate the recommendation with the
  option itself, so a user has to cross-reference two places instead of reading one.
