/** Shared metric-field validation for ObjectiveForm.tsx (create) and
 * ObjectiveDetail.tsx (edit) -- both submit the same four-field metric group
 * to the same backend, which enforces an all-or-nothing rule
 * (src/adp/strategy/models.py's `_validate_metric_fields`, data-model.md
 * FR-003). The previous per-form `hasMetric` check only required *any one*
 * of the four fields to be set before submitting all four -- so filling in
 * just one (e.g. only Direction) silently sent a partial payload that the
 * backend rejected with a raw, unexplained 422, which read to a user as
 * "there's no way to save" (bug found live, 2026-08-14). */

export interface MetricFieldsCheck {
  /** Non-null when the fields are inconsistently filled in -- show this and
   *  block submission rather than sending a payload the backend will 422. */
  error: string | null;
  /** True only when all four fields are filled in (never true when `error`
   *  is set) -- callers use this to decide whether to submit the metric
   *  group at all, or omit it entirely. */
  hasMetric: boolean;
}

export function checkMetricFields(
  metricName: string,
  targetValue: string,
  targetUnit: string,
  direction: string,
): MetricFieldsCheck {
  const filledCount = [metricName.trim(), targetValue.trim(), targetUnit.trim(), direction].filter(
    (v) => v !== "",
  ).length;

  if (filledCount > 0 && filledCount < 4) {
    return {
      error:
        "Metric name, target value, target unit, and direction must all be filled in together, or all left blank.",
      hasMetric: false,
    };
  }
  return { error: null, hasMetric: filledCount === 4 };
}
