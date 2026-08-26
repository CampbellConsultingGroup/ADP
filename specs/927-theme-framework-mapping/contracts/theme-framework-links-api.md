# API Contract: Theme–Framework Mapping

**Auth**: All writes require `ActionType.WRITE_BUSINESS_ARCH` via the existing
`("/api/v1/strategy/", WRITE_BUSINESS_ARCH)` prefix rule — no `enforcement.py` change, no new
`ActionType`, no `PERMISSIONS_VERSION` bump (research.md D4). Reads are open beyond general platform
read access, matching both `StrategicTheme` and `RegulatoryFramework`'s own existing read gates.

---

## Theme–Framework link — `adp.strategy.router`

### POST /api/v1/strategy/themes/{theme_id}/frameworks

**Request body** (`ThemeFrameworkLinkCreate`):
```json
{ "framework_id": "FRM-abc123" }
```

**Response 201**: `list[str]` — the theme's full, updated `framework_ids` (mirrors
`link_objective_control`'s existing bare-list response shape).
**Response 404**: `theme_id` or `framework_id` does not exist.
**Response 409**: this pair is already linked.

### DELETE /api/v1/strategy/themes/{theme_id}/frameworks/{framework_id}

**Response 204**: unlinked.
**Response 404**: no such link exists.

### GET /api/v1/strategy/themes/{theme_id}

Unchanged route; response (`StrategicTheme`) gains `framework_ids: list[str]`.

### GET /api/v1/strategy/themes

Unchanged route; every item in `StrategicThemeListResponse.items` gains `framework_ids: list[str]`.

---

## Reverse lookup — `adp.compliance.router`

### GET /api/v1/compliance/frameworks/{framework_id}/themes

Every Strategic Theme tagged onto this Framework (spec.md FR-005).

**Response 200**: `StrategicThemeListResponse` (the existing list-response model, reused unmodified).
Ungated beyond general platform read access — a `RegulatoryFramework` carries no target-entity
sensitivity of its own, matching `GET /controls/{control_id}/objectives`'s own precedent.
**Response 404**: `framework_id` does not exist.
