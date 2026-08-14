import { useState } from "react";
import { useThemes, type ObjectiveDirection, type ObjectivePeriod, type StrategicObjectiveCreate } from "../api/strategy";
import { checkMetricFields } from "./objectiveMetric";

interface ObjectiveFormProps {
  onSubmit: (data: StrategicObjectiveCreate) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

const PERIODS: ObjectivePeriod[] = ["Q1", "Q2", "Q3", "Q4", "FY"];
const DIRECTIONS: { value: ObjectiveDirection; label: string }[] = [
  { value: "increase", label: "Increase" },
  { value: "decrease", label: "Decrease" },
  { value: "reach", label: "Reach" },
];

export default function ObjectiveForm({ onSubmit, onCancel, isLoading }: ObjectiveFormProps) {
  const { data: themesData } = useThemes();
  const themes = themesData?.items ?? [];

  const [themeId, setThemeId] = useState(themes[0]?.id ?? "");
  const [owner, setOwner] = useState("");
  const [statement, setStatement] = useState("");
  const [metricName, setMetricName] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [targetUnit, setTargetUnit] = useState("");
  const [direction, setDirection] = useState<ObjectiveDirection | "">("");
  const [fiscalYear, setFiscalYear] = useState("");
  const [period, setPeriod] = useState<ObjectivePeriod>("Q1");
  const [error, setError] = useState<string | null>(null);

  const effectiveThemeId = themeId || themes[0]?.id || "";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!owner.trim()) {
      setError("Owner is required");
      return;
    }
    if (!statement.trim()) {
      setError("Statement is required");
      return;
    }
    const metricCheck = checkMetricFields(metricName, targetValue, targetUnit, direction);
    if (metricCheck.error) {
      setError(metricCheck.error);
      return;
    }
    setError(null);
    const hasMetric = metricCheck.hasMetric;

    onSubmit({
      theme_id: effectiveThemeId,
      owner: owner.trim(),
      statement: statement.trim(),
      metric_name: hasMetric ? metricName.trim() : undefined,
      target_value: hasMetric && targetValue.trim() ? Number(targetValue) : undefined,
      target_unit: hasMetric ? targetUnit.trim() : undefined,
      direction: hasMetric && direction ? direction : undefined,
      fiscal_year: Number(fiscalYear),
      period,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {error && <div style={{ color: "var(--crit)", fontSize: 13 }}>{error}</div>}

      <label style={{ fontSize: 13 }}>
        Theme *
        <select
          aria-label="Theme *"
          value={effectiveThemeId}
          onChange={(e) => setThemeId(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        >
          {themes.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>

      <label style={{ fontSize: 13 }}>
        Owner *
        <input
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="Claims Platform Team"
        />
      </label>

      <label style={{ fontSize: 13 }}>
        Statement *
        <textarea
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          rows={2}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="Reduce claims cycle time to improve retention"
        />
      </label>

      <fieldset style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10 }}>
        <legend style={{ fontSize: 12, color: "var(--ink-3)" }}>Metric &amp; target (optional)</legend>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Metric name
          <input
            value={metricName}
            onChange={(e) => setMetricName(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 2 }}
            placeholder="Claims cycle time"
          />
        </label>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Target value
          <input
            type="number"
            value={targetValue}
            onChange={(e) => setTargetValue(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 2 }}
            placeholder="40"
          />
        </label>
        <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
          Target unit
          <input
            value={targetUnit}
            onChange={(e) => setTargetUnit(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 2 }}
            placeholder="%"
          />
        </label>
        <label style={{ fontSize: 13 }}>
          Direction
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as ObjectiveDirection | "")}
            style={{ display: "block", width: "100%", marginTop: 2 }}
          >
            <option value="">—</option>
            {DIRECTIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </label>
      </fieldset>

      <label style={{ fontSize: 13 }}>
        Fiscal year *
        <input
          type="number"
          value={fiscalYear}
          onChange={(e) => setFiscalYear(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
          placeholder="2026"
        />
      </label>

      <label style={{ fontSize: 13 }}>
        Period *
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value as ObjectivePeriod)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={isLoading}>
          {isLoading ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
