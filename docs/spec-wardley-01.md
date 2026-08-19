---
document_type: sdd-spec
title: "SPEC-WARDLEY-01 — Wardley Mapping capability"
status: draft
audience: ADP engineering, SDD reviewers
last_updated: 2026-08-13
depends_on:
  - research-business-requirements.md
  - research-solution-architecture.md
package: adp.diagrams.wardley
---

# SPEC-WARDLEY-01 — Wardley Mapping capability

## 1. Problem

ADP's diagramming subsystem (`adp.diagrams`) covers flowchart, sequence, ER,
UML, and cloud-architecture types — all auto-laid-out graphs, independent of
C4. Wardley Mapping is a distinct strategic-visualization technique (value
chain × evolution stage) with no representation today. Unlike ADP's other
diagram types, a Wardley Map's node positions are the *data itself* — evolution
and visibility are measured/asserted values, not something a layout algorithm
derives — which makes it structurally simpler than flowchart/ER in one respect
(no auto-layout needed) while adding two continuous-valued axes with no
equivalent elsewhere in the platform.

## 2. Scope

**In scope:**
- `wardley_maps` — a named map, owned by a user.
- `wardley_components` — nodes positioned on (evolution, visibility), optionally
  linked to a real `capability_id` or `application_id`.
- `wardley_component_dependencies` — directed edges between components within
  the same map.
- `wardley_movements` — one current planned evolution-target per component
  (the map's "movement arrow"), not a history.

**Out of scope (deferred):**
- **Pipelines** (a component representing a range across evolution rather than
  a point) — genuinely useful but adds a second geometry type; not needed for
  a first version.
- **Notes/annotations** pinned to arbitrary map coordinates — can reuse the
  existing `notes` field pattern later if wanted; not required to make a map
  useful.
- **AI-assisted component extraction** (free text → proposed components +
  evolution positions, human-confirmed) — same AI-proposes/human-confirms
  shape as requirements intake, but it's a second spec once the manual-entry
  version is validated. Flagged here so it isn't forgotten, not built now.

## 3. Data model

**`wardley_maps`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | TEXT | not null |
| `description` | TEXT | nullable |
| `owner_id` | UUID FK → users | not null |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**`wardley_components`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `map_id` | UUID FK → wardley_maps, `ON DELETE CASCADE` | indexed |
| `name` | TEXT | not null |
| `evolution` | NUMERIC | CHECK 0 ≤ evolution ≤ 1. Continuous, per the guide's own left/center/right-within-stage positioning — not a 4-value enum. |
| `visibility` | NUMERIC | CHECK 0 ≤ visibility ≤ 1. 1 = user-facing, 0 = invisible infrastructure. |
| `is_anchor` | BOOLEAN | not null, default false — marks User / User Need nodes, which sit outside the normal evolution axis |
| `capability_id` | UUID FK → capabilities | nullable — optional link into the real registry |
| `application_id` | UUID FK → applications | nullable — optional link into the real registry |
| `notes` | TEXT | nullable |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

A component may reference `capability_id`, `application_id`, both, or neither
— many legitimate components (a competitor's capability, a hypothetical future
state) won't map to anything in the registry, so this stays optional rather
than required, unlike the objective→capability link in Strategy which is
always to a real entity.

**`wardley_component_dependencies`** (join table, standard shape)
| Column | Type | Notes |
|---|---|---|
| `component_id` | UUID FK → wardley_components, `ON DELETE CASCADE` | |
| `depends_on_component_id` | UUID FK → wardley_components, `ON DELETE CASCADE` | indexed |
| `created_at` | TIMESTAMPTZ | |

PK: `(component_id, depends_on_component_id)`. CHECK constraint rejects
`component_id = depends_on_component_id` (no self-dependency) at the DB level.
Cross-map dependencies (component A in map 1 depending on component B in map
2) are rejected at the store layer, not the DB — same reasoning as the
objective-dependency cycle check in the Strategy work: not expressible as a
CHECK constraint, so it's application logic, flagged explicitly for review.

**`wardley_movements`**
| Column | Type | Notes |
|---|---|---|
| `component_id` | UUID PK, FK → wardley_components, `ON DELETE CASCADE` | one row per component — upsert semantics, not a time series |
| `target_evolution` | NUMERIC | CHECK 0 ≤ target_evolution ≤ 1 |
| `target_date` | DATE | nullable |
| `note` | TEXT | nullable |
| `updated_at` | TIMESTAMPTZ | |

**Design choice flagged for review:** this spec treats movement as "current
planned target," overwritten on update. If you want a movement history
(useful for a "how has our thinking on this component changed" view), swap to
the STRAT-01 progress-table shape (composite PK on `component_id` +
`recorded_date`) instead — same pattern, different tradeoff.

## 4. API surface

| Method | Path | Notes |
|---|---|---|
| `POST` / `GET` / `PATCH` / `DELETE` | `/diagrams/wardley/maps` (+ `/{id}`) | standard CRUD |
| `POST` / `GET` / `PATCH` / `DELETE` | `/diagrams/wardley/maps/{map_id}/components` (+ `/{id}`) | component CRUD, scoped to a map |
| `POST` / `DELETE` | `/diagrams/wardley/components/{id}/dependencies/{depends_on_id}` | validates same-map membership before insert |
| `GET` | `/diagrams/wardley/components/{id}/dependencies` | ungated read, both directions |
| `PUT` | `/diagrams/wardley/components/{id}/movement` | upsert — full replace, not partial patch, since it's a single current-state record |
| `DELETE` | `/diagrams/wardley/components/{id}/movement` | clears the movement arrow |
| `GET` | `/diagrams/wardley/maps/{id}/render` | returns the full map (components + dependencies + movements) in one call — the canvas needs all of it at once, not paginated fetches |

### 4.1 Cross-package validation

Following the existing convention: when a component's `capability_id` or
`application_id` is set, the router opens a second, domain-scoped session and
calls `adp.business.store.get_capability` / `adp.application.store.get_application`
directly to confirm the reference is real — no duplicated check, no new
internal HTTP call.

## 5. Permissions

New `ActionType`: `diagrams:write` may already exist and cover this (it's a
diagrams-package concern) — confirm against the existing permission table
before adding a new action. Route-prefix rules needed:

```
/diagrams/wardley/maps/*                          -> diagrams:write (mutating verbs)
/diagrams/wardley/components/*/dependencies/*      -> diagrams:write
/diagrams/wardley/components/*/movement            -> diagrams:write
```

All GET routes remain ungated reads. The route-permission completeness test
will fail CI if a prefix rule is missing.

## 6. Migration notes

- Single new Alembic revision, four tables, no backfill (net-new capability).
- `evolution`/`visibility`/`target_evolution` use `NUMERIC`, not floating
  point, per the existing convention that money/metric values are never
  float — these are compared and sorted on, same reasoning applies even
  though they're not money.

## 7. UI / screen impact

- New screen: `Diagrams → Wardley`, alongside the existing flowchart/sequence/
  ER/UML/cloud-architecture tabs in `08-diagrams.png`.
- Canvas reuses React Flow (already used for the C4 canvas), since Wardley
  needs free-form node positioning, not auto-layout — closer to how the C4
  canvas already handles positions than to how flowchart/ER layouts work.
  Net-new work is axis rendering (evolution gridlines/labels along x,
  visibility along y) and the dependency-arrow style, not node/edge plumbing.
- Component detail panel gains an optional "Link to capability/application"
  field, same pattern as other optional cross-domain links in the product.

## 8. Open questions for SDD review

- Confirm `adp.diagrams` package line count before deciding `wardley` as a
  submodule vs. a new sibling package — same measured-decision rule applied to
  every other package split in this codebase.
- Movement-as-single-row vs. movement-as-history (see §3) — needs a product
  call, not an engineering one.
- Should a component's evolution-stage label (Genesis/Custom Built/Product/
  Commodity) be a derived, computed read (bucketing the continuous value) the
  way objective status is derived in STRAT-01 — or is showing the raw
  continuous position on the canvas sufficient without a discrete label at
  all? This spec's reference implementation includes the derivation as a
  pure, testable function either way, since it costs little and the UI can
  choose whether to surface it.
