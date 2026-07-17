import { useEffect, useState } from "react";
import { useApplicationRisk, useUpdateApplicationRisk } from "../api/application";
import type {
  ApplicationRiskUpdate,
  DataClassification,
  DrBcStatus,
  SecurityPosture,
  VulnerabilityStatus,
} from "../api/application";

/** APM US3 — application risk & compliance register (sensitive: gated server-side). */

interface Props { appId: string; }

const SECURITY_OPTIONS: (SecurityPosture | "")[] = ["", "strong", "adequate", "weak", "unknown"];
const VULN_OPTIONS: (VulnerabilityStatus | "")[] = ["", "none_known", "open_low", "open_high", "critical"];
const CLASS_OPTIONS: (DataClassification | "")[] = ["", "public", "internal", "confidential", "restricted"];
const DR_BC_OPTIONS: (DrBcStatus | "")[] = ["", "tested", "documented", "none"];

const field: React.CSSProperties = {
  width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4,
};
const label: React.CSSProperties = { fontSize: 12, color: "var(--ink-2)" };

export default function RiskPanel({ appId }: Props) {
  const { data: risk, isLoading, error } = useApplicationRisk(appId);
  const updateRisk = useUpdateApplicationRisk(appId);

  const [securityPosture, setSecurityPosture] = useState<string>("");
  const [vulnStatus, setVulnStatus] = useState<string>("");
  const [classification, setClassification] = useState<string>("");
  const [tags, setTags] = useState<string>("");
  const [drBc, setDrBc] = useState<string>("");
  const [eolDate, setEolDate] = useState<string>("");
  const [eosDate, setEosDate] = useState<string>("");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!risk) return;
    setSecurityPosture(risk.security_posture ?? "");
    setVulnStatus(risk.vulnerability_status ?? "");
    setClassification(risk.data_classification ?? "");
    setTags(risk.regulatory_tags.join(", "));
    setDrBc(risk.dr_bc_status ?? "");
    setEolDate(risk.end_of_life_date ?? "");
    setEosDate(risk.end_of_support_date ?? "");
  }, [risk]);

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;

  if (error) {
    const forbidden = (error as Error).message.includes("403");
    return (
      <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
        {forbidden
          ? "You don't have permission to view risk & compliance data for this application."
          : "Could not load risk & compliance data."}
      </div>
    );
  }

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    const body: ApplicationRiskUpdate = {
      security_posture: (securityPosture || null) as ApplicationRiskUpdate["security_posture"],
      vulnerability_status: (vulnStatus || null) as ApplicationRiskUpdate["vulnerability_status"],
      data_classification: (classification || null) as ApplicationRiskUpdate["data_classification"],
      regulatory_tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      dr_bc_status: (drBc || null) as ApplicationRiskUpdate["dr_bc_status"],
      end_of_life_date: eolDate || null,
      end_of_support_date: eosDate || null,
    };
    try {
      await updateRisk.mutateAsync(body);
      showToast("Saved");
    } catch (e) {
      const forbidden = (e as Error).message.includes("403");
      showToast(forbidden ? "You don't have permission to edit risk data" : "Save failed");
    }
  };

  const eosInPast = eosDate !== "" && new Date(eosDate) < new Date();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 420 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Risk &amp; Compliance</h4>
      {toast && <div style={{ fontSize: 11, color: toast === "Saved" ? "var(--ink-2)" : "var(--crit)" }}>{toast}</div>}

      <label style={label}>Security Posture
        <select style={field} value={securityPosture} onChange={(e) => setSecurityPosture(e.target.value)}>
          {SECURITY_OPTIONS.map((o) => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={label}>Vulnerability Status
        <select style={field} value={vulnStatus} onChange={(e) => setVulnStatus(e.target.value)}>
          {VULN_OPTIONS.map((o) => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={label}>Data Classification
        <select style={field} value={classification} onChange={(e) => setClassification(e.target.value)}>
          {CLASS_OPTIONS.map((o) => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={label}>Regulatory Tags (comma-separated)
        <input style={field} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="SOX, GDPR, HIPAA" />
      </label>

      <label style={label}>DR / BC Status
        <select style={field} value={drBc} onChange={(e) => setDrBc(e.target.value)}>
          {DR_BC_OPTIONS.map((o) => <option key={o} value={o}>{o || "— none —"}</option>)}
        </select>
      </label>

      <label style={label}>End-of-Life Date
        <input style={field} type="date" value={eolDate} onChange={(e) => setEolDate(e.target.value)} />
      </label>

      <label style={label}>
        End-of-Support Date
        <input style={field} type="date" value={eosDate} onChange={(e) => setEosDate(e.target.value)} />
      </label>
      {eosInPast && (
        <div style={{ fontSize: 12, color: "var(--crit)" }}>⚠ Out of support — this date is in the past.</div>
      )}

      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateRisk.isPending}
          style={{
            padding: "6px 14px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--accent, #2874A6)", color: "#fff", cursor: "pointer",
          }}
        >
          {updateRisk.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
