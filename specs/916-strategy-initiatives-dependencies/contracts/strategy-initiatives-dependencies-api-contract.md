# API Contract: Strategy Initiatives & Objective Dependencies

All routes under the existing `/api/v1/strategy` prefix (`src/adp/strategy/router.py`, importing from the new `src/adp/strategy/initiatives.py`), gated by the existing `("/api/v1/strategy/", ActionType.WRITE_BUSINESS_ARCH)` rule for every non-`GET` — no new permission, no new prefix rule, no new router.

## Initiatives

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `POST` | `/strategy/initiatives` | `StrategyInitiativeCreate` | `StrategyInitiative` | 201 | FR-001 |
| `GET` | `/strategy/initiatives` | — | `StrategyInitiativeListResponse` | 200 | |
| `GET` | `/strategy/initiatives/{initiative_id}` | — | `StrategyInitiative` | 200 / 404 | FR-002 |
| `PATCH` | `/strategy/initiatives/{initiative_id}` | `StrategyInitiativeUpdate` | `StrategyInitiative` | 200 / 404 | FR-002 |
| `DELETE` | `/strategy/initiatives/{initiative_id}` | — | — | 204 / 404 | FR-011 — unconditional, no in-use block (unlike theme delete) |

## Initiative ↔ Objective links

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `POST` | `/strategy/initiatives/{initiative_id}/objectives/{objective_id}` | — | `StrategyInitiative` | 201 / 404 (either id) / 409 (duplicate) | FR-004 |
| `DELETE` | `/strategy/initiatives/{initiative_id}/objectives/{objective_id}` | — | — | 204 / 404 | FR-004 |
| `GET` | `/strategy/objectives/{objective_id}/initiatives` | — | `StrategyInitiativeListResponse` | 200 / 404 | Reverse lookup, FR-005 — lives under `/objectives/` per the existing convention that traceability reads are exposed from both sides (mirrors `915`'s `/objectives/{id}/progress` shape) |

## Objective dependencies

| Method | Path | Request | Response | Status | Notes |
|---|---|---|---|---|---|
| `POST` | `/strategy/objectives/{objective_id}/depends-on` | `ObjectiveDependencyCreate` | `ObjectiveDependenciesResponse` | 201 / 404 (either id) / 400 (would create a cycle, including self-dependency) / 409 (already recorded) | FR-006, FR-007 |
| `DELETE` | `/strategy/objectives/{objective_id}/depends-on/{depends_on_objective_id}` | — | — | 204 / 404 | FR-009 |
| `GET` | `/strategy/objectives/{objective_id}/dependencies` | — | `ObjectiveDependenciesResponse` | 200 / 404 | Both directions in one response (`depends_on` + `blocks`) — FR-008 |

## Error shape

All error responses use FastAPI's standard `{"detail": "..."}` shape, matching every existing `adp.strategy.router` `HTTPException`. The 400 cycle-rejection response's detail text names which objective(s) form the would-be cycle, not just a generic "invalid" message — mirrors how every other rejection in this router already explains itself (e.g. the existing 409 duplicate-theme-name message).

## Out of scope for this contract

- No endpoint here returns cross-objective aggregates (e.g. "how many initiatives are blocked," a portfolio-wide dependency graph view) — that's the sibling `ADP-d8u.7` feature's territory, not built by this one.
- No endpoint accepts AI-extracted initiative data — human-entered only, matching every other write in this domain.
