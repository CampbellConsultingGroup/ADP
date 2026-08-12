# Contract: `GET /api/v1/strategy/summary`

New endpoint on the existing `adp.strategy` router (`prefix="/api/v1/strategy"`). Read-only — no
`ActionType` gate (`enforce_route_permission` is a documented no-op for GET; spec.md FR-012 and
Assumptions), same normal-authentication requirement as every other route.

## `GET /api/v1/strategy/summary`

No path or query parameters.

**200** — `StrategicSummaryResponse`:

```json
{
  "total_objectives": 12,
  "total_themes": 4,
  "linked_count": 9,
  "unlinked_count": 3,
  "current_period_count": 5,
  "upcoming_count": 4,
  "past_due_count": 3
}
```

- `linked_count + unlinked_count == total_objectives` always (data-model.md's invariant).
- `current_period_count + upcoming_count + past_due_count == total_objectives` always.
- When no objectives exist yet, every field is `0` — no error, matching spec.md's empty-state
  Edge Case.
- `total_themes` counts every theme in the registry, including themes not yet referenced by any
  objective (spec.md Assumptions).

No other status code is meaningful for this endpoint — it takes no input to be invalid, and an
empty dataset is a valid `200`, not a `404`.

## Backward compatibility

Entirely new endpoint under the existing `/api/v1/strategy` prefix — no existing
`adp.strategy` endpoint changes, no existing contract touched. `StrategicObjectiveSummary` (used
by `GET /api/v1/strategy/objectives`) is unchanged — this feature deliberately does not extend it
(research.md Decision 1's rejected alternative).
