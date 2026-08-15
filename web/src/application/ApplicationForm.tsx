import React, { useState } from "react";
import type { Application, ApplicationCreate } from "../api/application";
import HealthAssessmentModal from "./HealthAssessmentModal";
import BusinessValueAssessmentModal from "./BusinessValueAssessmentModal";

interface Props {
  initial?: Application | null;
  onSave: (data: ApplicationCreate) => Promise<void>;
  onCancel: () => void;
  saving?: boolean;
}

const TIME_OPTIONS = ["", "Tolerate", "Invest", "Migrate", "Eliminate"] as const;
const R_OPTIONS = ["", "Rehost", "Replatform", "Repurchase", "Refactor", "Retire", "Retain", "Relocate"] as const;
const PACE_OPTIONS = ["", "Record", "Differentiation", "Innovation"] as const;
const LIFECYCLE_OPTIONS = ["planned", "active", "sunset", "retired"] as const;
const HOSTING_OPTIONS = ["", "on_prem", "cloud", "saas", "hybrid"] as const;

export default function ApplicationForm({ initial, onSave, onCancel, saving }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [vendor, setVendor] = useState(initial?.vendor ?? "");
  const [owner, setOwner] = useState(initial?.primary_owner ?? "");
  const [time, setTime] = useState<string>(initial?.time_classification ?? "");
  const [rStrategy, setRStrategy] = useState<string>(initial?.r_strategy ?? "");
  const [pace, setPace] = useState<string>(initial?.pace_layer ?? "");
  // health_score is read-only here (docs/application-health-assessment-spec.md
  // §6 Q5) -- read straight off `initial` at render time, not local state, so
  // it live-updates after the assessment popup saves and the parent refetches.
  const [showHealthModal, setShowHealthModal] = useState(false);
  // business_value is read-only here too (docs/application-business-value-
  // assessment-spec.md §7), same treatment as health_score above.
  const [showBusinessValueModal, setShowBusinessValueModal] = useState(false);
  const [bizCrit, setBizCrit] = useState<string>(initial?.business_criticality?.toString() ?? "");
  const [bizUnit, setBizUnit] = useState<string>(initial?.owning_business_unit ?? "");
  const [bizOwner, setBizOwner] = useState<string>(initial?.business_owner ?? "");
  const [techOwner, setTechOwner] = useState<string>(initial?.technical_owner ?? "");
  const [lifecycle, setLifecycle] = useState<string>(initial?.lifecycle_status ?? "active");
  const [hostingModel, setHostingModel] = useState<string>(initial?.hosting_model ?? "");
  const [archPattern, setArchPattern] = useState<string>(initial?.architecture_pattern ?? "");
  const [techDebtFlags, setTechDebtFlags] = useState<string>((initial?.tech_debt_flags ?? []).join(", "));
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError("Name is required"); return; }
    const bcNum = bizCrit ? parseInt(bizCrit, 10) : null;
    const outOfRange = (v: number | null) => v !== null && (v < 1 || v > 5);
    if (outOfRange(bcNum)) { setError("Business criticality must be 1–5"); return; }
    setError(null);
    try {
      await onSave({
        name: name.trim(),
        description: description || null,
        vendor: vendor || null,
        primary_owner: owner || null,
        time_classification: (time || null) as ApplicationCreate["time_classification"],
        r_strategy: (rStrategy || null) as ApplicationCreate["r_strategy"],
        pace_layer: (pace || null) as ApplicationCreate["pace_layer"],
        business_criticality: bcNum,
        owning_business_unit: bizUnit || null,
        business_owner: bizOwner || null,
        technical_owner: techOwner || null,
        lifecycle_status: (lifecycle || "active") as ApplicationCreate["lifecycle_status"],
        hosting_model: (hostingModel || null) as ApplicationCreate["hosting_model"],
        architecture_pattern: archPattern || null,
        tech_debt_flags: techDebtFlags.split(",").map((t) => t.trim()).filter(Boolean),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    }
  };

  const field: React.CSSProperties = { width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4 };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12, padding: 16 }}>
      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>{initial ? "Edit Application" : "New Application"}</h3>
      {error && <div style={{ color: "var(--crit)", fontSize: 12 }}>{error}</div>}

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Name *
        <input style={field} value={name} onChange={e => setName(e.target.value)} placeholder="My Application" />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Description
        <textarea style={{ ...field, height: 60 }} value={description} onChange={e => setDescription(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Vendor
        <input style={field} value={vendor} onChange={e => setVendor(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Primary Owner
        <input style={field} value={owner} onChange={e => setOwner(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>TIME Classification
        <select style={field} value={time} onChange={e => setTime(e.target.value)}>
          {TIME_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>R-Strategy
        <select style={field} value={rStrategy} onChange={e => setRStrategy(e.target.value)}>
          {R_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Pace Layer
        <select style={field} value={pace} onChange={e => setPace(e.target.value)}>
          {PACE_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Health</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 13 }}>
            {initial?.health_score
              ? `${"★".repeat(initial.health_score)}${"☆".repeat(5 - initial.health_score)} (${initial.health_score})`
              : "— not assessed —"}
          </span>
          <button
            type="button"
            onClick={() => setShowHealthModal(true)}
            disabled={!initial}
            title={initial ? undefined : "Save the application first, then assess health"}
            style={{
              fontSize: 12, padding: "3px 10px", borderRadius: 4,
              border: "1px solid var(--accent)", background: "none", color: "var(--accent)",
              cursor: initial ? "pointer" : "not-allowed", opacity: initial ? 1 : 0.5,
            }}
          >
            Assess Health
          </button>
        </div>
        {!initial && (
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
            Save the application first, then assess health.
          </div>
        )}
      </div>

      {initial && showHealthModal && (
        <HealthAssessmentModal appId={initial.id} onClose={() => setShowHealthModal(false)} />
      )}

      <div>
        <div style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 4 }}>Business Value</div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 13 }}>
            {initial?.business_value
              ? `${"★".repeat(initial.business_value)}${"☆".repeat(5 - initial.business_value)} (${initial.business_value})`
              : "— not assessed —"}
          </span>
          <button
            type="button"
            onClick={() => setShowBusinessValueModal(true)}
            disabled={!initial}
            title={initial ? undefined : "Save the application first, then assess business value"}
            style={{
              fontSize: 12, padding: "3px 10px", borderRadius: 4,
              border: "1px solid var(--accent)", background: "none", color: "var(--accent)",
              cursor: initial ? "pointer" : "not-allowed", opacity: initial ? 1 : 0.5,
            }}
          >
            Assess Business Value
          </button>
        </div>
        {!initial && (
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
            Save the application first, then assess business value.
          </div>
        )}
      </div>

      {initial && showBusinessValueModal && (
        <BusinessValueAssessmentModal appId={initial.id} onClose={() => setShowBusinessValueModal(false)} />
      )}

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Business Criticality (1–5)
        <input style={field} type="number" min={1} max={5} value={bizCrit} onChange={e => setBizCrit(e.target.value)} placeholder="1–5" />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Owning Business Unit
        <input style={field} value={bizUnit} onChange={e => setBizUnit(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Business Owner
        <input style={field} value={bizOwner} onChange={e => setBizOwner(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Technical Owner
        <input style={field} value={techOwner} onChange={e => setTechOwner(e.target.value)} />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Lifecycle Status
        <select style={field} value={lifecycle} onChange={e => setLifecycle(e.target.value)}>
          {LIFECYCLE_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Hosting Model
        <select style={field} value={hostingModel} onChange={e => setHostingModel(e.target.value)}>
          {HOSTING_OPTIONS.map(o => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Architecture Pattern
        <input style={field} value={archPattern} onChange={e => setArchPattern(e.target.value)} placeholder="e.g. microservices" />
      </label>

      <label style={{ fontSize: 12, color: "var(--ink-2)" }}>Tech-Debt Flags (comma-separated)
        <input style={field} value={techDebtFlags} onChange={e => setTechDebtFlags(e.target.value)} placeholder="unsupported_version, deprecated_tech" />
      </label>

      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={saving} style={{ padding: "6px 16px", background: "var(--accent)", color: "var(--surface)", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onCancel} style={{ padding: "6px 14px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
          Cancel
        </button>
      </div>
    </form>
  );
}
