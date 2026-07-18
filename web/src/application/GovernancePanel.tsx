import { useEffect, useState } from "react";
import { useApplicationGovernance, useUpdateApplicationGovernance } from "../api/application";
import type { ApplicationGovernanceUpdate } from "../api/application";

/** APM US7 — application ownership & governance (sensitive: gated server-side). */

interface Props { appId: string; }

const field: React.CSSProperties = {
  width: "100%", padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4,
};
const label: React.CSSProperties = { fontSize: 12, color: "var(--ink-2)" };

export default function GovernancePanel({ appId }: Props) {
  const { data: governance, isLoading, error } = useApplicationGovernance(appId);
  const updateGovernance = useUpdateApplicationGovernance(appId);

  const [contractTerms, setContractTerms] = useState("");
  const [renewalDate, setRenewalDate] = useState("");
  const [sla, setSla] = useState("");
  const [businessSponsor, setBusinessSponsor] = useState("");
  const [itOwner, setItOwner] = useState("");
  const [decisionRights, setDecisionRights] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!governance) return;
    setContractTerms(governance.contract_terms ?? "");
    setRenewalDate(governance.renewal_date ?? "");
    setSla(governance.sla ?? "");
    setBusinessSponsor(governance.business_sponsor ?? "");
    setItOwner(governance.it_owner ?? "");
    setDecisionRights(governance.decision_rights ?? "");
  }, [governance]);

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;

  if (error) {
    const forbidden = (error as Error).message.includes("403");
    return (
      <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
        {forbidden
          ? "You don't have permission to view governance data for this application."
          : "Could not load governance data."}
      </div>
    );
  }

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const handleSave = async () => {
    const body: ApplicationGovernanceUpdate = {
      contract_terms: contractTerms || null,
      renewal_date: renewalDate || null,
      sla: sla || null,
      business_sponsor: businessSponsor || null,
      it_owner: itOwner || null,
      decision_rights: decisionRights || null,
    };
    try {
      await updateGovernance.mutateAsync(body);
      showToast("Saved");
    } catch (e) {
      const forbidden = (e as Error).message.includes("403");
      showToast(forbidden ? "You don't have permission to edit governance data" : "Save failed");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 460 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Ownership &amp; Governance</h4>
      {toast && <div style={{ fontSize: 11, color: toast === "Saved" ? "var(--ink-2)" : "var(--crit)" }}>{toast}</div>}

      <label style={label}>Contract Terms
        <textarea style={{ ...field, height: 60 }} value={contractTerms} onChange={(e) => setContractTerms(e.target.value)} />
      </label>

      <label style={label}>Renewal Date
        <input style={field} type="date" value={renewalDate} onChange={(e) => setRenewalDate(e.target.value)} />
      </label>

      <label style={label}>SLA
        <input style={field} value={sla} onChange={(e) => setSla(e.target.value)} placeholder="e.g. 99.9% uptime" />
      </label>

      <label style={label}>Business Sponsor
        <input style={field} value={businessSponsor} onChange={(e) => setBusinessSponsor(e.target.value)} />
      </label>

      <label style={label}>IT Owner
        <input style={field} value={itOwner} onChange={(e) => setItOwner(e.target.value)} />
      </label>

      <label style={label}>Decision Rights
        <textarea style={{ ...field, height: 50 }} value={decisionRights} onChange={(e) => setDecisionRights(e.target.value)} />
      </label>

      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateGovernance.isPending}
          style={{
            padding: "6px 14px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 6,
            background: "var(--accent, #2874A6)", color: "#fff", cursor: "pointer",
          }}
        >
          {updateGovernance.isPending ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
