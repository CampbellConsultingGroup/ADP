# Quickstart: C4 Diagram Type in the Diagram Tool

Assumes the local dev stack is running (`web/` on :5173, API on :8001) and a valid auth token/
session (standard architect login — no special role needed; `WRITE_DIAGRAM` is already broadly
granted, unchanged by this feature).

## Scenario 1: API accepts and returns `"c4"` (User Story 1/2, FR-001/FR-005)

```bash
# Create
curl -sX POST http://localhost:8001/api/v1/diagrams \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Payments Context", "diagram_type": "c4", "dsl_source": "C4Context\nPerson(user, \"Customer\")\nSystem(sys, \"Payments\")\nRel(user, sys, \"uses\")\n"}'
# Expect: 201, body.diagram_type == "c4"

# List — confirm it appears correctly labeled (SC-004)
curl -s http://localhost:8001/api/v1/diagrams -H "Authorization: Bearer $TOKEN" \
  | jq '.items[] | select(.diagram_type == "c4")'
```

## Scenario 2: Create and author a new C4 diagram in the browser (User Story 1, FR-001–FR-004)

1. Navigate to Diagrams → New Diagram.
2. Confirm "c4" (labeled "C4 Diagram" or similar in the type selector) is present as a choice
   alongside flowchart/sequence/erd/uml/architecture.
3. Select it; confirm the new diagram opens empty, with the DSL panel showing a valid starting
   point at Context level (e.g. `C4Context` on its own, no elements yet — not the flowchart-family
   default).
4. In the DSL panel, enter:
   ```
   C4Context
   Person(user, "Customer")
   System(sys, "Payments Service")
   SystemDb(db, "Payments DB")
   Rel(user, sys, "Uses")
   Rel(sys, db, "Reads/writes")
   ```
   Click Apply.
5. Confirm all three elements and both relationships render on the canvas, with `db` shown using
   the database (cylinder) shape.

## Scenario 3: Malformed C4 text reports a clear error (User Story 1, FR-007)

1. In the same DSL panel, replace the text with something the format doesn't recognize, e.g. a
   line reading `Persn(user, "Customer")` (typo).
2. Click Apply.
3. Confirm the tool reports the specific line and content it could not interpret — the same error
   presentation already used for every other diagram type's parse errors.

## Scenario 4: Save, reopen, round-trip fidelity (User Story 2, FR-005, SC-003)

1. Save the diagram from Scenario 2.
2. Navigate away (back to the diagram list), then reopen it.
3. Confirm every element, relationship, and label is exactly as left — no data loss, no
   re-ordering, no dropped elements.

## Scenario 5: Export (User Story 3, FR-006)

1. With a saved C4 diagram open, use the export action.
2. Confirm an image file (SVG and/or PNG, matching whichever formats every other diagram type
   already offers) downloads, depicting the diagram's current content.

## Scenario 6: Existing diagrams are unaffected (Edge Cases, SC-006)

1. Open a pre-existing flowchart/sequence/erd/uml/architecture diagram created before this feature
   shipped.
2. Confirm it opens, renders, and behaves exactly as before — same type, same content, same
   available toolbar actions.

## Scenario 7: Automated regression check

```bash
cd web && npx vitest run src/diagrams/core/dsl/ src/diagrams/DiagramEditorPage.test.tsx && npx tsc --noEmit
cd .. && pytest tests/unit/diagrams/ tests/contract/test_diagrams_api_contract.py -q
```
