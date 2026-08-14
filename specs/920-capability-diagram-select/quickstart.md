# Quickstart: Multi-Select Capabilities → Generate Diagram

Manual/browser verification scenarios. No backend changes exist to curl-test (plan.md's Ground-Truth
Research) — this is a pure frontend feature, verified entirely in the browser against a running local stack
(`ADP_AUTH_ENABLED=false`, backend on `:8001`, frontend on `:5173`) with the seeded retail capability tree.

## 1. Multi-branch selection and generation (User Story 1)

- Open Business → Capabilities tab.
- Check capabilities from at least two different branches, including one parent-and-child pair from the
  same branch.
- Confirm the "Generate Diagram from Selected" action is enabled only once at least one box is checked.
- Trigger it; confirm the diagram editor opens with exactly the checked capabilities as nodes, an edge
  present only between the checked parent-child pair, and no edge between capabilities from unrelated
  branches.
- Repeat with exactly one capability checked; confirm the result matches what the old per-row "Generate
  Diagram" button used to produce for that same capability (a single node, no edges, titled with its name).

## 2. Selection management (User Story 2)

- Check several capabilities; confirm a visible count reflects the current selection size.
- Use "Clear selection"; confirm every checked row returns to unchecked and the count returns to zero.

## 3. Edge cases

- Check a capability whose parent is not also checked; confirm it still appears in the generated diagram,
  with no incoming edge (its unchecked ancestor is not pulled in automatically).
- Switch to the Heat Map or Value Streams tab with capabilities checked, then return to Capabilities;
  confirm the selection has reset to empty.
- With zero capabilities checked, confirm there is no way to trigger diagram generation.
