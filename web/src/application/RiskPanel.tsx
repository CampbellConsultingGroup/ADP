import { useEffect, useState } from "react";
import { useApplicationRisk, useUpdateApplicationRisk } from "../api/application";
import type {
  ApplicationRiskUpdate,
  DataClassification,
  DrBcStatus,
  SecurityPosture,
  VulnerabilityStatus,
} from "../api/application";
import { useFrameworks } from "../api/compliance";

/** APM US3 — application risk & compliance register (sensitive: gated server-side).
 *
 * 932-regulatory-framework-tags (ADP-bkg): regulatory_tags is a governed multi-select of real
 * RegulatoryFramework ids (COMPLY-01), not free text — only `in_force`/`amended` frameworks are
 * selectable (spec.md FR-001); each selected tag displays by name, disambiguated by jurisdiction/
 * version when two frameworks share a name (spec.md FR-003). This is a lightweight "applies here"
 * tag, distinct from the separate "Regulatory Compliance" tab's per-control ControlMapping
 * assessed status (spec.md FR-008) — unaffected by this component. */

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
  const { data: frameworksData } = useFrameworks();

  const [securityPosture, setSecurityPosture] = useState<string>("");
  const [vulnStatus, setVulnStatus] = useState<string>("");
  const [classification, setClassification] = useState<string>("");
  const [selectedFrameworkIds, setSelectedFrameworkIds] = useState<string[]>([]);
  const [drBc, setDrBc] = useState<string>("");
  const [eolDate, setEolDate] = useState<string>("");
  const [eosDate, setEosDate] = useState<string>("");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!risk) return;
    setSecurityPosture(risk.security_posture ?? "");
    setVulnStatus(risk.vulnerability_status ?? "");
    setClassification(risk.data_classification ?? "");
    setSelectedFrameworkIds(risk.regulatory_tags);
    setDrBc(risk.dr_bc_status ?? "");
    setEolDate(risk.end_of_life_date ?? "");
    setEosDate(risk.end_of_support_date ?? "");
  }, [risk]);

  const allFrameworks = frameworksData?.items ?? [];
  const selectableFrameworks = allFrameworks.filter(
    (f) => f.status === "in_force" || f.status === "amended"
  );
  // Tags already selected before this feature's status filter existed, or whose framework has
  // since changed status, must still render even if no longer *selectable* (spec.md Edge Cases) —
  // so lookups for display fall back to the full list, not just selectableFrameworks.
  const frameworksById = new Map(allFrameworks.map((f) => [f.id, f]));
  const nameCounts = new Map<string, number>();
  for (const f of allFrameworks) nameCounts.set(f.name, (nameCounts.get(f.name) ?? 0) + 1);

  function frameworkLabel(id: string): string {
    const f = frameworksById.get(id);
    if (!f) return id;
    const ambiguous = (nameCounts.get(f.name) ?? 0) > 1;
    return ambiguous ? `${f.name} (${f.jurisdiction}, ${f.version})` : f.name;
  }

  function toggleFramework(id: string) {
    setSelectedFrameworkIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

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
      regulatory_tags: selectedFrameworkIds,
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

      <div style={label}>
        Regulatory Frameworks
        <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 4 }}>
          {selectableFrameworks.length === 0 && (
            <div style={{ fontSize: 12, color: "var(--ink-3)" }}>
              No regulatory frameworks have been added yet.
            </div>
          )}
          {selectableFrameworks.map((f) => (
            <label key={f.id} style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={selectedFrameworkIds.includes(f.id)}
                onChange={() => toggleFramework(f.id)}
              />
              {frameworkLabel(f.id)}
            </label>
          ))}
          {selectedFrameworkIds
            .filter((id) => !selectableFrameworks.some((f) => f.id === id))
            .map((id) => (
              <label
                key={id}
                style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 6, color: "var(--ink-3)" }}
                title="No longer selectable (not in_force/amended) -- this existing tag was kept as-is; unchecking removes it"
              >
                <input type="checkbox" checked onChange={() => toggleFramework(id)} />
                {frameworkLabel(id)}
              </label>
            ))}
        </div>
      </div>

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
