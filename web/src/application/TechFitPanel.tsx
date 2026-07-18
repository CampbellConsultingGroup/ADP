import type { Application } from "../api/application";

/**
 * APM US5 — technical fit depth: hosting model, architecture pattern, and
 * tech-debt flags. These are plain columns on Application (already loaded by
 * ApplicationDetail), so this panel reads from the passed-in app rather than
 * issuing its own fetch. Editing happens via the main Edit form.
 */

interface Props { app: Application; }

const HOSTING_LABELS: Record<string, string> = {
  on_prem: "On-Prem",
  cloud: "Cloud",
  saas: "SaaS",
  hybrid: "Hybrid",
};

export default function TechFitPanel({ app }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480, fontSize: 13 }}>
      <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Technical Fit</h4>

      <div>
        <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Hosting Model
        </div>
        <div>{app.hosting_model ? (HOSTING_LABELS[app.hosting_model] ?? app.hosting_model) : "— not set —"}</div>
      </div>

      <div>
        <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          Architecture Pattern
        </div>
        <div>{app.architecture_pattern || "— not set —"}</div>
      </div>

      <div>
        <div style={{ fontSize: 11, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 4 }}>
          Tech-Debt Flags
        </div>
        {app.tech_debt_flags.length === 0 ? (
          <div style={{ color: "var(--ink-3)" }}>None recorded.</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {app.tech_debt_flags.map((flag) => (
              <span
                key={flag}
                style={{
                  fontSize: 11, padding: "2px 8px", borderRadius: 10,
                  background: "var(--warn-wash, rgba(200,140,0,0.12))", color: "var(--warn, #b0742a)",
                }}
              >
                ⚠ {flag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
