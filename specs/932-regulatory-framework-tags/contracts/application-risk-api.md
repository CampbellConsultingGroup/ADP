# API Contract: Application Regulatory Framework Tags

**Auth**: No change. Both routes below already exist and already carry
`require_action_dep(ActionType.READ_APPLICATION_RISK)` (GET) /
`ActionType.WRITE_APPLICATION_RISK` (PUT, via the existing
`("PUT", "/api/v1/applications/{app_id}/risk")` enforcement-map entry). No new `ActionType`, no
`PERMISSIONS_VERSION` bump (research.md D1/D4 — this feature introduces no new permission surface).

Populating the picker reads `GET /api/v1/compliance/frameworks` — already open beyond general
platform read access, unchanged.

---

## GET /api/v1/applications/{app_id}/risk

Unchanged route. Response (`ApplicationRisk`) field `regulatory_tags: list[str]` changes meaning:
now the set of currently-linked `RegulatoryFramework` ids (via `ApplicationFrameworkTag`), computed
on read — no longer arbitrary free text. Shape (`list[str]`) is unchanged (research.md D3).

**Response 200** (example):
```json
{
  "security_posture": "adequate",
  "vulnerability_status": "open_low",
  "data_classification": "confidential",
  "regulatory_tags": ["a1b2c3d4-...", "e5f6a7b8-..."],
  "dr_bc_status": "documented",
  "end_of_life_date": null,
  "end_of_support_date": null,
  "updated_at": "2026-10-07T12:00:00Z"
}
```
**Response 403**: caller lacks `READ_APPLICATION_RISK` (unchanged).

## PUT /api/v1/applications/{app_id}/risk

Unchanged route and unchanged request shape (`ApplicationRiskUpdate`). `regulatory_tags: list[str]`
is now interpreted as the **complete desired set** of framework ids for this application (full
replace semantics, matching every other field already on this body) — not an incremental
link/unlink call.

**Request body** (example — adding/removing frameworks alongside any other field):
```json
{
  "security_posture": "adequate",
  "vulnerability_status": "open_low",
  "data_classification": "confidential",
  "regulatory_tags": ["a1b2c3d4-...", "e5f6a7b8-..."],
  "dr_bc_status": "documented",
  "end_of_life_date": null,
  "end_of_support_date": null
}
```

**Response 200**: `ApplicationRisk`, reflecting the new linked set.

**Response 422**: `regulatory_tags` contains an id that either (a) does not exist in
`regulatory_frameworks` (FR-002), or (b) exists but is newly being added (i.e. not already linked
to this application) and its `status` is not `in_force` or `amended` (FR-001, research.md D4).
The entire write is rejected — no partial application of the valid subset. An id that was already
linked before this request is never subject to check (b), regardless of its current `status`
(Edge Cases — a status change after tagging does not retroactively untag).

**Response 403**: caller lacks `WRITE_APPLICATION_RISK` (unchanged).

---

## Explicitly not part of this contract

No `GET /api/v1/compliance/frameworks/{framework_id}/applications` reverse-lookup endpoint is
added in this feature (research.md D7 — deferred as a named follow-on, matching the spec's own
Assumptions section).
