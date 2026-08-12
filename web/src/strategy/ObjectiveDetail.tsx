import { useState } from "react";
import {
  useObjective,
  useUpdateObjective,
  useDeleteObjective,
  type ObjectiveDirection,
  type ObjectivePeriod,
} from "../api/strategy";
import ObjectiveCapabilityLinkEditor from "./ObjectiveCapabilityLinkEditor";
import ObjectiveValueStreamLinkEditor from "./ObjectiveValueStreamLinkEditor";
import { Button } from "../ui";

interface ObjectiveDetailProps {
  objectiveId: string;
  onBack: () => void;
}

const PERIODS: ObjectivePeriod[] = ["Q1", "Q2", "Q3", "Q4", "FY"];
const DIRECTIONS: { value: ObjectiveDirection; label: string }[] = [
  { value: "increase", label: "Increase" },
  { value: "decrease", label: "Decrease" },
  { value: "reach", label: "Reach" },
];

export default function ObjectiveDetail({ objectiveId, onBack }: ObjectiveDetailProps) {
  const { data: objective, isLoading, error } = useObjective(objectiveId);
  const updateMutation = useUpdateObjective(objectiveId);
  const deleteMutation = useDeleteObjective();
  const [editing, setEditing] = useState(false);

  const [owner, setOwner] = useState("");
  const [statement, setStatement] = useState("");
  const [metricName, setMetricName] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [targetUnit, setTargetUnit] = useState("");
  const [direction, setDirection] = useState<ObjectiveDirection | "">("");
  const [fiscalYear, setFiscalYear] = useState("");
  const [period, setPeriod] = useState<ObjectivePeriod>("Q1");

  function startEdit() {
    if (!objective) return;
    setOwner(objective.owner);
    setStatement(objective.statement);
    setMetricName(objective.metric_name ?? "");
    setTargetValue(objective.target_value != null ? String(objective.target_value) : "");
    setTargetUnit(objective.target_unit ?? "");
    setDirection(objective.direction ?? "");
    setFiscalYear(String(objective.fiscal_year));
    setPeriod(objective.period);
    setEditing(true);
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const hasMetric = !!(metricName.trim() || targetValue.trim() || targetUnit.trim() || direction);
    updateMutation.mutate(
      {
        owner: owner.trim(),
        statement: statement.trim(),
        metric_name: hasMetric ? metricName.trim() : null,
        target_value: hasMetric && targetValue.trim() ? Number(targetValue) : null,
        target_unit: hasMetric ? targetUnit.trim() : null,
        direction: hasMetric && direction ? direction : null,
        fiscal_year: Number(fiscalYear),
        period,
      },
      { onSuccess: () => setEditing(false) },
    );
  }

  function handleDelete() {
    if (!objective) return;
    if (!confirm(`Delete objective "${objective.statement}"?`)) return;
    deleteMutation.mutate(objective.id, { onSuccess: onBack });
  }

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading objective…</div>;
  if (error || !objective) return <div className="ui-alert crit">Failed to load objective</div>;

  return (
    <div>
      <button onClick={onBack} style={{ marginBottom: 12, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)" }}>
        ← Back to objectives
      </button>

      {editing ? (
        <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <label style={{ fontSize: 13 }}>
            Owner *
            <input value={owner} onChange={(e) => setOwner(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
          </label>
          <label style={{ fontSize: 13 }}>
            Statement *
            <textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={2} style={{ display: "block", width: "100%", marginTop: 2 }} />
          </label>
          <fieldset style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10 }}>
            <legend style={{ fontSize: 12, color: "var(--ink-3)" }}>Metric &amp; target (optional)</legend>
            <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
              Metric name
              <input value={metricName} onChange={(e) => setMetricName(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
            </label>
            <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
              Target value
              <input type="number" value={targetValue} onChange={(e) => setTargetValue(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
            </label>
            <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
              Target unit
              <input value={targetUnit} onChange={(e) => setTargetUnit(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
            </label>
            <label style={{ fontSize: 13 }}>
              Direction
              <select value={direction} onChange={(e) => setDirection(e.target.value as ObjectiveDirection | "")} style={{ display: "block", width: "100%", marginTop: 2 }}>
                <option value="">—</option>
                {DIRECTIONS.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </label>
          </fieldset>
          <label style={{ fontSize: 13 }}>
            Fiscal year *
            <input type="number" value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
          </label>
          <label style={{ fontSize: 13 }}>
            Period *
            <select value={period} onChange={(e) => setPeriod(e.target.value as ObjectivePeriod)} style={{ display: "block", width: "100%", marginTop: 2 }}>
              {PERIODS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setEditing(false)}>Cancel</button>
          </div>
          {updateMutation.isError && (
            <div className="ui-alert crit" style={{ fontSize: 12 }}>{updateMutation.error.message}</div>
          )}
        </form>
      ) : (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
            <h3 style={{ margin: 0, fontSize: 16, color: "var(--ink)" }}>{objective.statement}</h3>
            <div style={{ display: "flex", gap: 8 }}>
              <Button size="sm" onClick={startEdit}>Edit</Button>
              <Button size="sm" variant="danger" onClick={handleDelete}>Delete</Button>
            </div>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 4 }}>Owner: {objective.owner}</div>
          <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 4 }}>
            {objective.period} {objective.fiscal_year}
          </div>
          {objective.metric_name && (
            <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 4 }}>
              {objective.metric_name}: {objective.direction} to {objective.target_value}
              {objective.target_unit}
            </div>
          )}

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Capabilities</h4>
          <ObjectiveCapabilityLinkEditor objective={objective} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Value Streams</h4>
          <ObjectiveValueStreamLinkEditor objective={objective} />
        </>
      )}
    </div>
  );
}
