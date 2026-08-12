# Phase 1 Data Model: Strategy Domain Card on the Overview Dashboard

No new table, no migration. This feature reads four already-existing tables (all from migration
025, ADP-d8u.1) and returns one new, purpose-built response shape — nothing is persisted.

## Source tables (unchanged, read-only for this feature)

| Table | Columns this feature reads |
|---|---|
| `strategic_objectives` | `id`, `fiscal_year`, `period` |
| `strategic_themes` | `id` (count only) |
| `strategic_objective_capabilities` | `objective_id` (existence check per objective) |
| `strategic_objective_value_streams` | `objective_id` (existence check per objective) |

## `StrategicSummaryResponse` (new Pydantic model, `src/adp/strategy/models.py`)

| Field | Type | Meaning |
|---|---|---|
| `total_objectives` | `int` | FR-002 — `COUNT(*)` from `strategic_objectives` |
| `total_themes` | `int` | FR-002 — `COUNT(*)` from `strategic_themes` |
| `linked_count` | `int` | FR-004/005 — objectives with ≥1 row in either join table |
| `unlinked_count` | `int` | FR-004/006 — `total_objectives - linked_count` |
| `current_period_count` | `int` | FR-007 — objectives whose `(fiscal_year, period)` is the current period per Decision 4's comparison rule |
| `upcoming_count` | `int` | FR-007 — objectives whose period is strictly later than current |
| `past_due_count` | `int` | FR-007/009 — objectives whose period is strictly earlier than current, per the `FY`-aware rule (research.md Decision 4) |

`model_config = ConfigDict(extra="forbid")`, mirroring every other ADP boundary model and
`PortfolioSummaryResponse`'s own shape directly.

**Invariant**: `linked_count + unlinked_count == total_objectives` and
`current_period_count + upcoming_count + past_due_count == total_objectives` always hold — every
objective falls into exactly one bucket of each pair. Worth a direct assertion in the contract
test (not just individual field checks) since a bug that double-counts or drops a row would
otherwise pass a naive per-field check on a small fixture.

## Query shape (`get_summary_stats`, `src/adp/strategy/store.py`)

One `sa.text()` statement (research.md Decision 3), computing all seven fields in a single
round-trip:

1. `SELECT COUNT(*) FROM strategic_themes` — `total_themes`.
2. One query over `strategic_objectives` LEFT JOINed against both link tables (deduplicated by
   objective id) to get `total_objectives`, `linked_count` (and `unlinked_count` derived), plus a
   `CASE`-classified fiscal bucket per row, aggregated with `COUNT(*) FILTER (WHERE ...)` for the
   three fiscal buckets in the same pass.

No new `Table()` object needed beyond what `src/adp/strategy/store.py` already defines
(`_objectives`, `_themes`, `_objective_capabilities`, `_objective_value_streams`) — the query text
references their real column/table names directly, matching `adp.portfolio`'s own precedent of
using raw SQL for aggregate reads rather than composing them through the Core expression builder.

## Frontend shape (`web/src/api/strategy.ts`)

```ts
export interface StrategicSummary {
  total_objectives: number;
  total_themes: number;
  linked_count: number;
  unlinked_count: number;
  current_period_count: number;
  upcoming_count: number;
  past_due_count: number;
}

export function useStrategySummary(): UseQueryResult<StrategicSummary> {
  return useQuery<StrategicSummary>({
    queryKey: ["strategy-summary"],
    queryFn: () => apiGet<StrategicSummary>("/api/v1/strategy/summary"),
    staleTime: 60_000,
  });
}
```

Mirrors `usePortfolioSummary()` field-for-field in structure (same `staleTime`, same
single-query-key shape) — the one new hook this feature needs.
