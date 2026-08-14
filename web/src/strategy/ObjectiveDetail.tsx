import { useState } from "react";
import {
  useObjective,
  useUpdateObjective,
  useDeleteObjective,
  useObjectiveProgress,
  useAbandonObjective,
  useThemes,
  type ObjectiveDirection,
  type ObjectivePeriod,
  type ObjectiveStatus,
} from "../api/strategy";
import ObjectiveCapabilityLinkEditor from "./ObjectiveCapabilityLinkEditor";
import ObjectiveValueStreamLinkEditor from "./ObjectiveValueStreamLinkEditor";
import ObjectiveProgressForm from "./ObjectiveProgressForm";
import ObjectiveInitiativeLinkEditor from "./ObjectiveInitiativeLinkEditor";
import ObjectiveDependencyPanel from "./ObjectiveDependencyPanel";
import ObjectiveDesignLinkEditor from "./ObjectiveDesignLinkEditor";
import ObjectiveApplicationLinkEditor from "./ObjectiveApplicationLinkEditor";
import { checkMetricFields } from "./objectiveMetric";
import { Button, StatusBadge, type BadgeTone } from "../ui";
import NavLinkButton from "./NavLinkButton";

interface ObjectiveDetailProps {
  objectiveId: string;
  onBack: () => void;
  /** Cross-navigation: jump to this objective's own Theme (Themes tab,
   *  scroll-and-highlighted). Undocumented from a required-hierarchy field
   *  (theme_id) that, before this, was never displayed anywhere on this
   *  screen. */
  onNavigateToTheme?: (themeId: string) => void;
  /** Cross-navigation: jump to a linked Initiative (Initiatives tab,
   *  scroll-and-highlighted). Threaded down to ObjectiveInitiativeLinkEditor
   *  so its "Linked Initiatives" names become clickable. */
  onNavigateToInitiative?: (initiativeId: string) => void;
}

const PERIODS: ObjectivePeriod[] = ["Q1", "Q2", "Q3", "Q4", "FY"];
const DIRECTIONS: { value: ObjectiveDirection; label: string }[] = [
  { value: "increase", label: "Increase" },
  { value: "decrease", label: "Decrease" },
  { value: "reach", label: "Reach" },
];

// ADP-d8u.5: status is always computed server-side (never set directly,
// except "abandoned") -- this is purely a display mapping.
const STATUS_TONE: Record<ObjectiveStatus, BadgeTone> = {
  proposed: "neutral",
  active: "info",
  at_risk: "warn",
  achieved: "good",
  abandoned: "crit",
};
const STATUS_LABEL: Record<ObjectiveStatus, string> = {
  proposed: "Not yet started",
  active: "On track",
  at_risk: "At risk",
  achieved: "Achieved",
  abandoned: "Abandoned",
};

export default function ObjectiveDetail({ objectiveId, onBack, onNavigateToTheme, onNavigateToInitiative }: ObjectiveDetailProps) {
  const { data: objective, isLoading, error } = useObjective(objectiveId);
  const { data: themesData } = useThemes();
  const { data: progress } = useObjectiveProgress(objectiveId);
  const updateMutation = useUpdateObjective(objectiveId);
  const deleteMutation = useDeleteObjective();
  const abandonMutation = useAbandonObjective(objectiveId);
  const [editing, setEditing] = useState(false);

  const [owner, setOwner] = useState("");
  const [statement, setStatement] = useState("");
  const [metricName, setMetricName] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [targetUnit, setTargetUnit] = useState("");
  const [direction, setDirection] = useState<ObjectiveDirection | "">("");
  const [fiscalYear, setFiscalYear] = useState("");
  const [period, setPeriod] = useState<ObjectivePeriod>("Q1");
  const [metricError, setMetricError] = useState<string | null>(null);

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
    setMetricError(null);
    setEditing(true);
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const metricCheck = checkMetricFields(metricName, targetValue, targetUnit, direction);
    if (metricCheck.error) {
      setMetricError(metricCheck.error);
      return;
    }
    setMetricError(null);
    const hasMetric = metricCheck.hasMetric;
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

  function handleAbandon() {
    if (!objective) return;
    const reason = prompt("Why is this objective being abandoned? (required)");
    if (reason == null) return; // cancelled
    const trimmed = reason.trim();
    if (!trimmed) return; // FR-009: a reason is required -- nothing to submit without one
    abandonMutation.mutate({ status_reason: trimmed });
  }

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading objective…</div>;
  if (error || !objective) return <div className="ui-alert crit">Failed to load objective</div>;

  const theme = themesData?.items.find((t) => t.id === objective.theme_id);

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
          {metricError && (
            <div className="ui-alert crit" style={{ fontSize: 12 }}>{metricError}</div>
          )}
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 16, color: "var(--ink)" }}>{objective.statement}</h3>
              <StatusBadge tone={STATUS_TONE[objective.status]}>
                {STATUS_LABEL[objective.status]}
              </StatusBadge>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <Button size="sm" onClick={startEdit}>Edit</Button>
              {objective.status !== "abandoned" && (
                <Button size="sm" variant="danger" onClick={handleAbandon}>Abandon</Button>
              )}
              <Button size="sm" variant="danger" onClick={handleDelete}>Delete</Button>
            </div>
          </div>
          {/* Labeled data card: the objective's own fields, made clearly legible
              and visually distinct from the "Linked ___" sections below --
              previously plain unlabeled text easy to read past (reported live,
              2026-08-14). */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
              gap: 12,
              padding: 14,
              marginBottom: 16,
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
            }}
          >
            <div>
              <div style={fieldLabelStyle}>Theme</div>
              <div style={fieldValueStyle}>
                {onNavigateToTheme ? (
                  <NavLinkButton onClick={() => onNavigateToTheme(objective.theme_id)} title="Jump to this theme">
                    {theme?.name ?? objective.theme_id}
                  </NavLinkButton>
                ) : (
                  theme?.name ?? objective.theme_id
                )}
              </div>
            </div>
            <div>
              <div style={fieldLabelStyle}>Owner</div>
              <div style={fieldValueStyle}>{objective.owner}</div>
            </div>
            <div>
              <div style={fieldLabelStyle}>Fiscal Period</div>
              <div style={fieldValueStyle}>{objective.period} {objective.fiscal_year}</div>
            </div>
            {objective.metric_name && (
              <div>
                <div style={fieldLabelStyle}>Target</div>
                <div style={fieldValueStyle}>
                  {objective.metric_name}: {objective.direction} to {objective.target_value}
                  {objective.target_unit}
                </div>
              </div>
            )}
          </div>
          {objective.status === "abandoned" && objective.status_reason && (
            <div className="ui-alert crit" style={{ fontSize: 12, marginBottom: 4 }}>
              Abandoned: {objective.status_reason}
            </div>
          )}

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 8, color: "var(--ink)" }}>Progress</h4>
          {progress && progress.items.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, margin: "0 0 12px", fontSize: 13 }}>
              {progress.items.map((entry) => (
                <li key={entry.as_of_date} style={{ display: "flex", gap: 8, marginBottom: 2, color: "var(--ink-2)" }}>
                  <span style={{ color: "var(--ink-3)" }}>{entry.as_of_date}</span>
                  <span>{entry.actual_value}</span>
                  {entry.note && <span style={{ color: "var(--ink-3)" }}>— {entry.note}</span>}
                </li>
              ))}
            </ul>
          )}
          <ObjectiveProgressForm objectiveId={objective.id} existingEntries={progress?.items ?? []} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Capabilities</h4>
          <ObjectiveCapabilityLinkEditor objective={objective} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Value Streams</h4>
          <ObjectiveValueStreamLinkEditor objective={objective} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Designs</h4>
          <ObjectiveDesignLinkEditor objective={objective} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Applications</h4>
          <ObjectiveApplicationLinkEditor objective={objective} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Linked Initiatives</h4>
          <ObjectiveInitiativeLinkEditor objectiveId={objective.id} onNavigateToInitiative={onNavigateToInitiative} />

          <h4 style={{ fontSize: 14, marginTop: 20, marginBottom: 0, color: "var(--ink)" }}>Dependencies</h4>
          <ObjectiveDependencyPanel objectiveId={objective.id} />
        </>
      )}
    </div>
  );
}

const fieldLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: "var(--ink-3)",
  textTransform: "uppercase",
  letterSpacing: 0.4,
  marginBottom: 2,
};

const fieldValueStyle: React.CSSProperties = {
  fontSize: 13,
  color: "var(--ink)",
};
