# Quickstart: Generate Diagrams from Business Data (ADP-914.7)

Assumes the web dev server is running (`cd web && npm run dev`) against an API with at least one
value stream (with 2+ stages) and one multi-level capability tree already seeded (e.g. via
`infra/azure/seed-data.sh` locally, or created manually through the Business Architecture screen).

## Scenario 1: Generate a flowchart from a value stream's stages (User Story 1)

1. Navigate to **Business** → **Value Streams**, open a value stream with at least 2 stages (e.g.
   "Quote to Bind" with stages "Intake," "Underwrite," "Bind").
2. Click **Generate Diagram**.
3. Expect: navigation to the **Diagrams** screen, opened directly in the editor (not the list),
   pre-filled with one node per stage in order and sequential edges between them, titled "Quote to
   Bind."
4. Expect: nothing has been saved yet — the diagram does not yet appear if you navigate to the
   Diagrams list and back without saving.
5. Click **Save**. Expect: the diagram now appears in the Diagrams list like any other.

## Scenario 2: Generate a flowchart from a capability's subtree (User Story 2)

1. Navigate to **Business** → **Capabilities**.
2. Find a level-1 capability with at least one level-2 child, itself having a level-3 child (e.g.
   "Underwriting" → "Risk Assessment" → "Rating Engine").
3. Click that capability's **Generate Diagram** action (in its per-node action row, alongside
   Edit/Add child/Delete).
4. Expect: navigation to the **Diagrams** screen, opened in the editor, pre-filled with 3 nodes
   ("Underwriting," "Risk Assessment," "Rating Engine") and edges Underwriting→Risk Assessment→
   Rating Engine, titled "Underwriting."

## Scenario 3: Empty-source edge cases (spec Edge Cases)

1. Generate from a value stream with zero stages → expect an empty, unsaved flowchart (zero
   nodes), not an error.
2. Generate from a leaf (level-3) capability → expect a single-node flowchart (just that
   capability), not an error.

## Scenario 4: A generated diagram is fully editable, identically to a hand-authored one (FR-007)

1. From Scenario 1 or 2's generated (unsaved) diagram, add a new node manually, relabel an
   existing one, and change the title.
2. Expect: every edit behaves exactly as it would on a manually-started "+ New Diagram" — nothing
   about the generated origin restricts subsequent editing.

## Scenario 5: Automated regression check

```bash
cd web && npx vitest run src/diagrams/generators.test.ts
# Expect: pure-function tests for both generators pass, including the empty-source edge cases.

npm run test:run
# Expect: full frontend suite green, no regressions.
```
