# API Contract: Regulatory Framework Legal Dates & Identity — COMPLY-01a

**Auth**: All write operations require `ActionType.WRITE_COMPLIANCE`, already covered by the existing
`("/api/v1/compliance/", WRITE_COMPLIANCE)` prefix rule — no `enforcement.py` change, no new `ActionType`,
no `PERMISSIONS_VERSION` bump. Reads are open, unchanged (COMPLY-01's own existing posture).

---

## Existing routes, extended (no path change)

### POST /api/v1/compliance/frameworks, PATCH /api/v1/compliance/frameworks/{framework_id}

**Request body** (`RegulatoryFrameworkCreate` / `RegulatoryFrameworkUpdate`) gains, all optional:
```json
{
  "regulation_number": "2016/679",
  "celex_number": "32016R0679",
  "adoption_date": "2016-04-27",
  "oj_publication_date": "2016-05-04",
  "entry_into_force_date": "2016-05-24",
  "consolidated_as_of": "2016-05-04",
  "status": "in_force"
}
```
Every existing field (`name`, `jurisdiction`, `authority`, `version`, `effective_date`, `source_url`)
is unchanged.

**Response 200/201** (`RegulatoryFramework`): includes the new fields, `null` where unset.
**Response 409**: `regulation_number` already used by another framework
(`DuplicateRegulationNumberError`).
**Response 422**: `status` not one of the four allowed values.

### GET /api/v1/compliance/frameworks/{framework_id}

**Response 200** (`RegulatoryFrameworkDetail`) gains two fields alongside the existing `controls`:
```json
{
  "application_phases": [
    { "id": "...", "framework_id": "...", "phase_label": "Prohibited practices",
      "applies_from_date": "2025-02-02", "description": null, "created_at": "..." }
  ],
  "amendments": []
}
```
Both `[]` when none recorded — not an error, not omitted (spec.md Edge Cases; research.md D4).

---

## New routes — Application Phases

### POST /api/v1/compliance/frameworks/{framework_id}/application-phases

**Request body** (`FrameworkApplicationPhaseCreate`):
```json
{ "phase_label": "GPAI obligations", "applies_from_date": "2025-08-02", "description": null }
```
**Response 201**: `FrameworkApplicationPhase`.
**Response 404**: `framework_id` does not exist.

### GET /api/v1/compliance/frameworks/{framework_id}/application-phases

**Response 200**: `FrameworkApplicationPhaseListResponse` (`items`, `total`), ordered by
`applies_from_date`.
**Response 404**: `framework_id` does not exist.

### DELETE /api/v1/compliance/frameworks/{framework_id}/application-phases/{phase_id}

**Response 204**: removed.
**Response 404**: `framework_id` or `phase_id` does not exist (`ApplicationPhaseNotFoundError`).

---

## New routes — Amendments

### POST /api/v1/compliance/frameworks/{framework_id}/amendments

**Request body** (`FrameworkAmendmentCreate`):
```json
{ "amending_celex": "32024R1620", "amending_title": "RTS on ICT risk management", "effective_date": null }
```
**Response 201**: `FrameworkAmendment`.
**Response 404**: `framework_id` does not exist.

### GET /api/v1/compliance/frameworks/{framework_id}/amendments

**Response 200**: `FrameworkAmendmentListResponse` (`items`, `total`), ordered by `effective_date`
(nulls last).
**Response 404**: `framework_id` does not exist.

### DELETE /api/v1/compliance/frameworks/{framework_id}/amendments/{amendment_id}

**Response 204**: removed.
**Response 404**: `framework_id` or `amendment_id` does not exist (`AmendmentNotFoundError`).

---

## Response Model Reference

```json
// FrameworkApplicationPhase (read model)
{
  "id": "string",
  "framework_id": "string",
  "phase_label": "string",
  "applies_from_date": "date",
  "description": "string | null",
  "created_at": "datetime"
}

// FrameworkAmendment (read model)
{
  "id": "string",
  "framework_id": "string",
  "amending_celex": "string | null",
  "amending_title": "string",
  "effective_date": "date | null",
  "created_at": "datetime"
}
```

Not changed by this spec, per the resolved Clarification: `web/src/compliance/FrameworkForm.tsx` /
`FrameworkDetail.tsx` — the Compliance screen keeps its current behavior (spec.md FR-010). The above
routes exist and are usable via direct API calls in this pass; UI surfacing is explicit follow-on work.
