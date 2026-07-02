import React from "react";
import type { ArchitectureDescription, Element } from "../types";

interface InspectionPanelProps {
  elementId: string | null;
  design: ArchitectureDescription;
  onClose: () => void;
}

function formatProvenance(provenance: string | undefined): string {
  if (!provenance) return "Manually placed";
  const upper = provenance.toUpperCase();
  return `Accepted from recommendation ${upper}`;
}

export default function InspectionPanel({
  elementId,
  design,
  onClose,
}: InspectionPanelProps): React.ReactElement | null {
  if (!elementId) return null;

  const element: Element | undefined = design.elements.find((e) => e.id === elementId);
  if (!element) return null;

  const satisfiedReqs = (element.satisfies ?? []).map((reqId) => {
    const req = design.requirements?.find((r) => r.id === reqId);
    return { id: reqId, title: req?.title ?? reqId };
  });

  return (
    <div
      style={{
        width: 280,
        background: "#fff",
        border: "1px solid #ddd",
        borderRadius: 6,
        padding: 16,
        overflowY: "auto",
        maxHeight: "100%",
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <strong style={{ fontSize: 15 }}>{element.name}</strong>
        <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18 }}>✕</button>
      </div>

      <div style={{ fontSize: 12, color: "#666", marginBottom: 12 }}>[{element.kind}]</div>

      {element.description && (
        <p style={{ fontSize: 13, color: "#333", marginBottom: 12 }}>{element.description}</p>
      )}

      <section>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>Satisfies:</h4>
        {satisfiedReqs.length === 0 ? (
          <p style={{ fontSize: 12, color: "#999" }}>No requirements satisfied</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {satisfiedReqs.map(({ id, title }) => (
              <li key={id} style={{ fontSize: 12, marginBottom: 4 }}>
                <span style={{ color: "#1168BD", fontWeight: 500 }}>{id}</span>
                {title !== id && <span style={{ color: "#333" }}>: {title}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={{ marginTop: 12 }}>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>Provenance:</h4>
        <p style={{ fontSize: 12, color: "#555" }}>{formatProvenance(element.provenance)}</p>
      </section>
    </div>
  );
}
