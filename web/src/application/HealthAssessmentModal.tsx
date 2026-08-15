import React, { useEffect, useState } from "react";
import {
  useHealthAssessment,
  useSaveHealthAssessment,
  type HealthDimension,
  type HealthAssessmentSubmit,
} from "../api/application";
import { Button } from "../ui";

interface Props {
  appId: string;
  onClose: () => void;
}

/** Transcribed verbatim from docs/health-table.md -- if that file changes,
 * this constant (and the popup's copy) must be updated together
 * (docs/application-health-assessment-spec.md §3/§7). */
const SCORE_LABELS = ["1 — Critical", "2 — At Risk", "3 — Fair / Watch", "4 — Healthy", "5 — Thriving"];

const RUBRIC: { dimension: HealthDimension; label: string; options: string[] }[] = [
  {
    dimension: "stability_incidents",
    label: "Stability & Incidents",
    options: [
      "Severe or continuous outages; core function is unreliable or unusable.",
      "Frequent or high-impact incidents; SLA regularly missed; user-facing disruption.",
      "Recurring minor incidents or occasional workarounds; SLA occasionally missed.",
      "Rare, low-impact incidents; quickly resolved; SLA met.",
      "No incidents; consistently meets or exceeds uptime/SLA targets.",
    ],
  },
  {
    dimension: "technical_currency_debt",
    label: "Technical Currency & Debt",
    options: [
      "Running on end-of-life or unsupported infrastructure with no upgrade path.",
      "Key platform(s) or dependencies unsupported or nearing end-of-life; no funded upgrade plan.",
      "Some components aging without a firm upgrade plan; moderate accumulated debt.",
      "Mostly current; minor debt with a funded or scheduled upgrade path.",
      "All platforms and dependencies on current, vendor-supported versions; minimal debt.",
    ],
  },
  {
    dimension: "security_posture",
    label: "Security Posture",
    options: [
      "Known exploitable or critical vulnerabilities; failing compliance requirements.",
      "Known unpatched high-severity vulnerabilities or overdue audit findings.",
      "Some medium-severity findings open past target remediation date.",
      "Only low-severity findings open, with remediation on track.",
      "No known vulnerabilities; passes current audits; patching is current.",
    ],
  },
  {
    dimension: "support_team_capacity",
    label: "Support & Team Capacity",
    options: [
      "No one able to support it; original team or vendor is gone.",
      "No dedicated owner or team; support is ad hoc or purely reactive.",
      "Owner identified but thinly resourced; single point of failure on key knowledge.",
      "Clear owner; adequately resourced; minor bus-factor risk.",
      "Clear owner; well-resourced team; more than one person can support it.",
    ],
  },
  {
    dimension: "documentation_knowledge",
    label: "Documentation & Knowledge",
    options: [
      "No usable documentation; knowledge is effectively lost.",
      "Documentation is sparse; knowledge lives mostly in a few people's heads.",
      "Documentation exists but is outdated or incomplete in key areas.",
      "Good documentation with minor gaps.",
      "Comprehensive, current documentation; onboarding is straightforward.",
    ],
  },
  {
    dimension: "business_value_criticality",
    label: "Business Value & Criticality Alignment",
    options: [
      "Value no longer justifies its cost, risk, or existence; candidate for retirement.",
      "Cost or risk is starting to outweigh the value delivered.",
      "Value is unclear, declining, or only partially understood.",
      "Solid, understood value; cost and risk are justified.",
      "Clearly delivers strong, well-understood business value relative to its cost and risk.",
    ],
  },
];

export default function HealthAssessmentModal({ appId, onClose }: Props): React.ReactElement {
  const { data, isLoading } = useHealthAssessment(appId);
  const save = useSaveHealthAssessment(appId);
  const [selections, setSelections] = useState<Partial<Record<HealthDimension, number>>>({});
  const [prefilled, setPrefilled] = useState(false);

  // Pre-fill from the application's last-saved assessment, once, when it
  // arrives (spec §4 "Popup, on open") -- not on every refetch, so a save
  // in progress doesn't clobber the user's still-unsaved edits.
  useEffect(() => {
    if (data && !prefilled) {
      const initial: Partial<Record<HealthDimension, number>> = {};
      for (const entry of data.entries) initial[entry.dimension] = entry.score;
      setSelections(initial);
      setPrefilled(true);
    }
  }, [data, prefilled]);

  const allAnswered = RUBRIC.every((row) => selections[row.dimension] !== undefined);
  const computedMin = allAnswered
    ? Math.min(...RUBRIC.map((row) => selections[row.dimension]!))
    : null;

  function handleSave() {
    if (!allAnswered) return;
    save.mutate(selections as HealthAssessmentSubmit, { onSuccess: onClose });
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "var(--surface)", borderRadius: 8, padding: 24,
          maxWidth: 1000, width: "94%", maxHeight: "90vh", overflowY: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700 }}>Health Assessment</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-2)" }}>
          Pick the description that best matches this application for each dimension. The
          overall health score is the lowest of the six selections.
        </p>

        {isLoading ? (
          <div style={{ padding: 20, fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ ...cellStyle, textAlign: "left", minWidth: 160 }}>Dimension</th>
                  {SCORE_LABELS.map((label) => (
                    <th key={label} style={{ ...cellStyle, minWidth: 150 }}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {RUBRIC.map((row) => (
                  <tr key={row.dimension}>
                    <td style={{ ...cellStyle, fontWeight: 600, textAlign: "left" }}>{row.label}</td>
                    {row.options.map((description, idx) => {
                      const score = idx + 1;
                      return (
                        <td key={score} style={cellStyle}>
                          <label style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}>
                            <input
                              type="radio"
                              name={`health-${row.dimension}`}
                              checked={selections[row.dimension] === score}
                              onChange={() =>
                                setSelections((prev) => ({ ...prev, [row.dimension]: score }))
                              }
                            />
                            <span style={{ color: "var(--ink-3)" }}>{description}</span>
                          </label>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
          <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
            {allAnswered
              ? `Resulting health score: ${computedMin} (lowest of the six selections)`
              : "Select an option for every dimension to continue."}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <Button onClick={onClose} disabled={save.isPending}>Cancel</Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={!allAnswered || save.isPending}
            >
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
        {save.isError && (
          <div style={{ marginTop: 10, fontSize: 12, color: "var(--crit)" }}>
            {save.error instanceof Error ? save.error.message : "Failed to save"}
          </div>
        )}
      </div>
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  border: "1px solid var(--border)",
  padding: "8px 10px",
  textAlign: "center",
  verticalAlign: "top",
};
