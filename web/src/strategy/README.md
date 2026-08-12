# Strategic Objective Capture (ADP-d8u.1)

This module is entirely ADP-authored (no vendored code) and independent from
`web/src/business/` — it consumes that module's read hooks (`useCapabilities`,
`useValueStreams`) for link targets, but adds no new files there and changes
none of its existing ones (spec.md FR-012).

## `StrategyPage.tsx` — top-level tab container

Mirrors `web/src/business/BusinessPage.tsx`'s tab-bar convention: two tabs,
"Objectives" (default) and "Themes". Owns `selectedObjectiveId` the same way
`BusinessPage.tsx` owns `selectedVsId`/`selectedDomainId` — switches between
`ObjectiveList.tsx` and `ObjectiveDetail.tsx` locally, no routing library.

## `ThemeList.tsx`, `ObjectiveList.tsx`, `ObjectiveForm.tsx`, `ObjectiveDetail.tsx`

Mirror `web/src/business/DomainList.tsx`/`ValueStreamList.tsx`'s established
list+inline-create-form+onSelect convention. `ObjectiveForm.tsx` is shared
between creation (`ObjectiveList.tsx`) and, indirectly via its own inline
field set, editing (`ObjectiveDetail.tsx`'s edit mode) — the metric/target
group (`metric_name`/`target_value`/`target_unit`/`direction`) is
all-or-nothing client-side too, mirroring the backend's own Pydantic
validator (`src/adp/strategy/models.py`) so a partial group never round-trips
to a guaranteed 422.

## `ObjectiveCapabilityLinkEditor.tsx`, `ObjectiveValueStreamLinkEditor.tsx`

Near-verbatim mirrors of `web/src/business/DesignLinkEditor.tsx`'s structure
(research.md Decision 4) — a plain filtered `<select>` dropdown (excluding
already-linked items) plus Link/Remove buttons, backed by dedicated
link/unlink mutations, **not** a live-search typeahead (this codebase's
established scale precedent: capability/value-stream counts are small).

One structural difference from `DesignLinkEditor.tsx`: that component fetches
its "linked" set via a separate query (`useLinkedCapabilityDesigns`) because
a design's own detail payload doesn't carry it. Here, `adp.strategy`'s
`GET /objectives/{id}` already returns `capability_ids`/`value_stream_ids`
inline, so both editors take the loaded `StrategicObjective` as a prop and
derive "linked" directly from it — no extra query.

Two separate components rather than one parameterized by entity type (unlike
`DesignLinkEditor.tsx`'s single `entityType` prop) because the "available"
item list's source hook differs by target (`useCapabilities()` vs.
`useValueStreams()`, both from `web/src/api/business.ts`) rather than being a
single shared query parameterized by a type string.

## `web/src/api/strategy.ts`

Mirrors `web/src/api/business.ts`'s `apiGet`/`apiMutation` +
TanStack Query hook convention exactly — see that file for the established
pattern this one follows line-for-line (query keys, `onSuccess` cache
invalidation, `Error & { status?: number }` mutation error typing for 409
detection in the link editors).

## Nav wiring

A new top-level `"strategy"` `AppView` (`web/src/shell/index.ts`), nav entry
(`web/src/ui/AppShell.tsx`, alongside Business/Applications/Diagrams — not
nested under Business Architecture, since strategic objectives are a
distinct entity with their own lifecycle), and render case in `App.tsx` —
mirrors ADP-914.5's exact "diagrams" nav-entry precedent.
