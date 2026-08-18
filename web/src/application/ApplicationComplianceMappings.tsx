import { useApplicationComplianceMappings } from "../api/compliance";

/** COMPLY-02 US3 — reverse lookup of Controls mapped to this Application. Read-only here;
 *  mapping creation/editing happens on the Control's own side
 *  (compliance/ControlMappingsEditor.tsx). Gated server-side by READ_APPLICATION_GOVERNANCE
 *  (research.md D2), mirroring GovernancePanel.tsx's own 403-handling shape. */

interface Props { appId: string; }

export default function ApplicationComplianceMappings({ appId }: Props) {
  const { data, isLoading, error } = useApplicationComplianceMappings(appId);

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;

  if (error) {
    const forbidden = (error as Error).message.includes("403");
    return (
      <div style={{ fontSize: 13, color: "var(--ink-3)" }}>
        {forbidden
          ? "You don't have permission to view compliance mappings for this application."
          : "Could not load compliance mappings."}
      </div>
    );
  }

  const items = data?.items ?? [];
  if (items.length === 0) {
    return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No controls mapped yet.</div>;
  }

  return (
    <div>
      {items.map((m) => (
        <div
          key={m.control_id}
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
            padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 6,
            marginBottom: 6, fontSize: 13,
          }}
        >
          <span style={{ color: "var(--ink)" }}>{m.control_id}</span>
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
            {m.compliance_status.replace("_", " ")}
          </span>
        </div>
      ))}
    </div>
  );
}
