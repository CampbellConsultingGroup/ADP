# Quickstart: Capability Heat Map

Manual/browser verification scenarios. No backend changes exist to curl-test (plan.md's Ground-Truth
Research #1) — this is a pure frontend feature, verified entirely in the browser against a running local
stack (`ADP_AUTH_ENABLED=false`, backend on `:8001`, frontend on `:5173`) with the seeded retail capability
tree.

## 1. Default view: shaded by maturity (User Story 1)

- Open Business → Heat Map tab.
- Confirm every capability appears exactly once, arranged in the same L1/L2/L3 hierarchy as the
  Capabilities tab's own tree, shaded by maturity level.
- Confirm a capability with no `maturity_level` set renders with a distinct "unclassified" treatment — never
  blank, never the same shade as a real level.
- Confirm a legend explains what each shade means.
- Hover or select a cell: confirm the capability's full name and exact maturity value (or "unclassified")
  appear without leaving the heat map.

## 2. Switch metric to strategic relevance (User Story 2)

- Switch the metric selector from "Maturity" to "Strategic relevance".
- Confirm every cell recolors immediately (single action, no navigation) and the legend updates to match.
- Confirm a capability that is unclassified for one metric but classified for the other updates correctly
  when the metric switches (the unclassified treatment is per-metric, not fixed to the capability).

## 3. Drill through to the capability's row (User Story 3)

- From the Heat Map tab, click a capability's cell (ideally one that is off-screen in the Capabilities tab's
  tree, to verify the scroll actually does something).
- Confirm the view switches to the Capabilities tab and that capability's existing row scrolls into view
  with a brief highlight — the same row a user would see navigating there directly, with its edit fields,
  Links panel, and Agent Review button all present (research.md Decision 3).

## 4. Edge cases

- Empty portfolio: with zero capabilities seeded, confirm the heat map shows an explicit empty state (not a
  blank or broken grid).
- Deep/wide hierarchy: confirm the grid remains scrollable/navigable rather than silently truncating any
  capability, for whatever depth/width the seeded retail data provides.
