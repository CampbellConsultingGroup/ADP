# API Contract: Admin Scoring Rubric Management (ADP-931)

Router prefix: `/api/v1/admin/scoring-rubrics`

Auth: All endpoints require `AuthMiddleware` plus `ActionType.MANAGE_SCORING_RUBRICS` (only
`PersonaRole.PLATFORM_ADMIN` holds this grant — FR-007). A caller without the permission gets
**403** with no rubric content in the body — identical treatment to the Agent Prompt Management
precedent.

Confirmation: the confirm and restore endpoints require `ActionType.MANAGE_SCORING_RUBRICS` in
`REQUIRES_CONFIRMATION`, enforced the same way as `POST /api/v1/admin/agent-prompts/{agent_id}/confirm`.

Logging: All mutations emit `logger.info()` with `actor`, `rubric_id`, `change_type`.

---

## GET /api/v1/admin/scoring-rubrics

List every registered rubric with its current effective weights (FR-004).

**Response 200** — `RubricListResponse`

```json
{
  "items": [
    {
      "rubric_id": "business_value",
      "display_name": "Business Value Assessment",
      "dimension_labels": {
        "strategic_alignment": "Strategic Alignment",
        "revenue_cost_impact": "Revenue/Cost Impact",
        "customer_stakeholder_impact": "Customer/Stakeholder Impact",
        "competitive_differentiation": "Competitive Differentiation",
        "risk_compliance_contribution": "Risk/Compliance Contribution",
        "evidence_measurability": "Evidence & Measurability"
      },
      "active_weights": {
        "strategic_alignment": 0.25,
        "revenue_cost_impact": 0.25,
        "customer_stakeholder_impact": 0.15,
        "competitive_differentiation": 0.10,
        "risk_compliance_contribution": 0.15,
        "evidence_measurability": 0.10
      },
      "is_override": false,
      "version": 0
    }
  ]
}
```

`is_override: false` means `active_weights` is the built-in `BUSINESS_VALUE_WEIGHTS` fallback
(FR-002); `version` is `0` in that case. `is_override: true` means the weights came from
`rubric_weight_overrides` and `version` is that row's optimistic-lock token (needed for the confirm
request below).

**Response 403** — caller lacks `MANAGE_SCORING_RUBRICS`.

---

## GET /api/v1/admin/scoring-rubrics/{rubric_id}/history

Full change history for one rubric, newest first (FR-006).

**Response 200** — `RubricHistoryResponse`

```json
{
  "items": [
    {
      "id": 7,
      "rubric_id": "business_value",
      "actor": "jdoe@example.com",
      "changed_at": "2026-08-26T14:03:00Z",
      "change_type": "edit",
      "prior_weights": {"strategic_alignment": 0.25, "...": "..."},
      "new_weights": {"strategic_alignment": 0.30, "...": "..."}
    }
  ]
}
```

**Response 404** — `rubric_id` is not a registered rubric.
**Response 403** — caller lacks `MANAGE_SCORING_RUBRICS`.

---

## POST /api/v1/admin/scoring-rubrics/{rubric_id}/confirm

Save a new weight set for `rubric_id` and make it active immediately (FR-005).

**Request** — `RubricEditRequest`

```json
{
  "weights": {
    "strategic_alignment": 0.30,
    "revenue_cost_impact": 0.20,
    "customer_stakeholder_impact": 0.15,
    "competitive_differentiation": 0.10,
    "risk_compliance_contribution": 0.15,
    "evidence_measurability": 0.10
  },
  "expected_version": 0,
  "confirmation_id": "CONFIRM-business_value-2026-08-26T14:03:00Z"
}
```

- `weights`: rejected (422) unless the rubric's own registered validator accepts it — for
  `business_value`, exactly the 6 known dimension keys, each weight in `[0, 1]`, summing to
  `1.0 ± 1e-6`.
- `expected_version`: the `version` the editor loaded from `GET /scoring-rubrics` (`0` for a
  not-yet-overridden rubric). Mismatch → 409 (FR-005/012 mirror).
- `confirmation_id`: required, non-empty (identical `field_validator` shape to
  `PromptEditRequest.confirmation_id`); constructed client-side as
  `` `CONFIRM-${rubricId}-${ISOtimestamp}` ``, mirroring `PromptEditor.tsx`'s own convention.

**Response 200** — `RubricChangeResult` (the rubric's new active weights + incremented `version`)

**Response 404** — `rubric_id` not registered.
**Response 409** — version conflict; body includes `current_active_weights`/`current_version`.
**Response 422** — invalid weight set (per the rubric's own validator), or missing/blank
`confirmation_id`.
**Response 403** — caller lacks `MANAGE_SCORING_RUBRICS`.

**Side effect**: within one DB transaction — upserts `rubric_weight_overrides` and inserts one
`rubric_weight_history` row with `change_type="edit"`. Both writes succeed or fail together.

---

## POST /api/v1/admin/scoring-rubrics/{rubric_id}/restore/{history_id}

Restore a prior version from history as the new active weight set (FR-006). Identical confirmation
gate to the edit endpoint above.

**Request** — `RubricRestoreRequest`

```json
{
  "expected_version": 1,
  "confirmation_id": "CONFIRM-business_value-restore-7"
}
```

`history_id` must belong to `rubric_id`, else **404**.

**Response 200** — `RubricChangeResult` (same shape as confirm)
**Response 404** — `rubric_id` not registered, or `history_id` doesn't exist/belong to it.
**Response 409** — version conflict.
**Response 422** — missing/blank `confirmation_id`.
**Response 403** — caller lacks `MANAGE_SCORING_RUBRICS`.

**Side effect**: same transaction shape as confirm, `change_type="restore"`, `new_weights` copied
from the chosen history row's `new_weights`.
