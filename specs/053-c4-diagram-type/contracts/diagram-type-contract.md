# Contract: `DiagramType` gains `"c4"`

The diagram tool's existing REST API (`/api/v1/diagrams`) is unchanged in shape — every
request/response field, route, and method stays exactly as documented for ADP-SPEC-046. The only
contract change is one additional accepted/returned value on the existing `diagram_type` field.

## Affected endpoints (all pre-existing, no new route)

| Endpoint | Field | Change |
|---|---|---|
| `POST /api/v1/diagrams` | request body `diagram_type` | now also accepts `"c4"` |
| `GET /api/v1/diagrams` | response `items[].diagram_type` | now may return `"c4"` |
| `GET /api/v1/diagrams/{id}` | response `diagram_type` | now may return `"c4"` |
| `PUT /api/v1/diagrams/{id}` | — | unaffected — `diagram_type` is immutable after creation (`DiagramUpdate` has no such field, `data-model.md` §4 of ADP-SPEC-046, unchanged here) |
| `DELETE /api/v1/diagrams/{id}` | — | unaffected |

## Existing tests whose assertions currently encode the *old* contract (must change)

These are not incidental breakage — each one currently asserts, on purpose, that `"c4"` is
rejected. That assertion becomes false the moment this feature ships; each must be updated to
assert the new, correct behavior rather than deleted or weakened.

| File | What it currently asserts | Required change |
|---|---|---|
| `tests/unit/diagrams/test_diagrams_models.py:42-47` | `DiagramCreate` accepts exactly `["flowchart", "sequence", "erd", "uml", "architecture"]` | add `"c4"` to the parametrized list |
| `tests/unit/diagrams/test_diagrams_models.py:50-52` | `DiagramCreate(diagram_type="c4")` raises `ValidationError` | change the example value to a still-genuinely-unsupported string (e.g. `"gantt"`) — the test's *purpose* (reject unknown types) is still valid and must be kept, just not with `"c4"` as the example |
| `tests/contract/test_diagrams_api_contract.py:43-54` | `POST /api/v1/diagrams` persists each of the same 5 types | add `"c4"` |
| `tests/contract/test_diagrams_api_contract.py:117` (a "rejects unsupported type" contract test) | `POST` with `diagram_type: "c4"` is rejected at the HTTP layer | same fix as the unit-test equivalent above |
| `tests/contract/test_diagrams_api_contract.py:162,172` | `GET /api/v1/diagrams` list/filter test iterates and asserts against the same 5-type set | add `"c4"` |
| `web/src/diagrams/DiagramEditorPage.test.tsx:256,262` | the type-selector `<select>` has exactly 5 `<option>`s; iterates the same 5-type list to confirm each is present and selectable | change `toHaveLength(5)` → `toHaveLength(6)`; add `"c4"` to the iterated list |

## New coverage this contract change requires (not a pre-existing test to fix — genuinely new)

| File | What it must verify |
|---|---|
| `web/src/diagrams/core/dsl/c4.test.ts` (new) | `parseC4`/`serializeC4` round-trip correctness — research.md Decision 2. This is DSL-engine-level, beneath the REST contract; listed here because it's the coverage that makes the contract's `"c4"` values actually trustworthy end to end, not just accepted. |
