# Quickstart: C4 Design View

Assumes the local dev stack is running (`web/` on :5173, API on :8001), a valid auth
session, and at least one existing design (create one via the Designs screen if needed).

## Scenario 1: Add elements and a relationship entirely by direct manipulation (User Story 1, FR-002/FR-003)

```bash
DESIGN_ID=<an existing design id>
curl -sX POST http://localhost:8001/api/v1/designs/$DESIGN_ID/elements \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"kind": "person", "name": "Customer"}'
# Expect 201, body.id matches ELM-NNN, kind="person"

curl -sX POST http://localhost:8001/api/v1/designs/$DESIGN_ID/elements \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"kind": "system", "name": "Payments Service"}'
# Expect 201

curl -sX POST http://localhost:8001/api/v1/designs/$DESIGN_ID/relationships \
  -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" \
  -d '{"source": "ELM-001", "target": "ELM-002", "label": "Uses"}'
# Expect 201

curl -s http://localhost:8001/api/v1/designs/$DESIGN_ID -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['elements']), len(d['relationships']))"
# Expect 2 1 (or +2/+1 over whatever the design already had)
```

In the browser: open the new C4 Design View for a design; use the toolbar to add a person and a
system directly on the canvas (not by typing DSL text); connect them; confirm both render, and
that reloading the page shows them exactly as placed (SC-001).

## Scenario 2: Delete cascades relationships correctly (User Story 1, FR-005, Edge Cases)

1. With the two elements and relationship from Scenario 1 still present, delete the "Customer"
   element from the canvas.
2. Confirm the "Uses" relationship is also removed (not left dangling) — both on canvas and via
   `GET /designs/{id}`.

## Scenario 3: Move between C4 levels without losing edits (User Story 2, FR-006/FR-007)

1. In a design with a person, a system, a container, and a component, open the Context level —
   confirm only the person and system are shown.
2. Switch to Container level — confirm only the system and container are shown (the person
   disappears, not because it was deleted, but because it's not part of this level's view).
3. Rename the system at the Container level.
4. Switch back to Context level — confirm the system's new name is shown there too (FR-007).

## Scenario 4: Technology tags and export keep working (User Story 3, FR-008/FR-009/FR-010)

1. On an element with existing technology metadata (or add some via the element picker), confirm
   it's visible and editable exactly as it is in the legacy screen today.
2. Use the new view's Export action to render the design — confirm the output uses the platform's
   official locked visual style (same as opening `POST /designs/{id}/render` directly would
   produce — compare against a render taken before this feature's changes, for the same design).
3. Export the same design in CALM format — confirm it succeeds and its shape matches what
   `GET /designs/{id}/export/calm` already produces today.

## Scenario 5: Previously-arranged layouts aren't reset (User Story 4, FR-013)

1. Open a design in the legacy C4Canvas screen first; arrange a few elements; confirm the layout
   save call succeeds (`PUT /designs/{id}/layout/{level}`).
2. Without restarting the backend process (this data is transient — research.md Decision 3), open
   the same design in the new C4 Design View at the same level.
3. Confirm elements appear in the positions just arranged, not a fresh auto-layout.

## Scenario 6: Boundary grouping is visually available but doesn't persist (Edge Cases, Decision 1)

1. In the new view, use "Add Container"/"Group into Container" to group two elements.
2. Confirm the grouping is visible while editing.
3. Reload the design. Confirm the elements themselves are still present and correct, but the
   grouping itself is gone (expected — not a bug; see spec.md Assumptions).

## Scenario 7: Existing screen is unaffected (Assumptions — no nav swap this phase)

1. Confirm the existing "Canvas" nav item still opens the legacy `C4Canvas.tsx` screen, unchanged,
   after this feature ships.
2. Confirm the new C4 Design View is reachable only via its own new entry point.

## Scenario 8: Automated regression check

```bash
cd web && npx vitest run src/canvas-v2/ && npx tsc --noEmit
cd .. && pytest tests/unit/elements/ tests/contract/test_elements_api_contract.py -q
pytest tests/ --ignore=tests/integration -q   # full platform regression
```
