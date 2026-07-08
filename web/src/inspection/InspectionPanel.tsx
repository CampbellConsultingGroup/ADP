import React, { useState } from "react";
import type { ArchitectureDescription, Element } from "../types";
import TechnologyEditor from "./TechnologyEditor";

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
  const [editingTech, setEditingTech] = useState(false);

  if (!elementId) return null;

  const element: Element | undefined = design.elements.find((e) => e.id === elementId);
  if (!element) return null;

  const satisfiedReqs = (element.satisfies ?? []).map((reqId) => {
    const req = design.requirements?.find((r) => r.id === reqId);
    return { id: reqId, title: req?.title ?? reqId };
  });

  const meta = element.technology_metadata;
  const hasMeta = meta && Object.values(meta).some(v => v != null);
  const tags = element.tags ?? [];

  const TECH_FIELDS: { key: string; label: string }[] = [
    { key: "technology", label: "Technology" },
    { key: "vendor", label: "Vendor" },
    { key: "platform", label: "Platform" },
    { key: "version", label: "Version" },
    { key: "owner_team", label: "Owner team" },
  ];

  return (
    <div
      style={{
        width: 300,
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

      {/* Technology metadata section (ADP-SPEC-029) */}
      <section style={{ marginTop: 14, borderTop: "1px solid #F3F4F6", paddingTop: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <h4 style={{ fontSize: 13, margin: 0 }}>Technology</h4>
          {!editingTech && (
            <button
              onClick={() => setEditingTech(true)}
              style={{ background: "none", border: "1px solid #D1D5DB", borderRadius: 3, cursor: "pointer", fontSize: 11, color: "#374151", padding: "2px 8px" }}
            >
              {hasMeta || tags.length > 0 ? "Edit" : "Add"}
            </button>
          )}
        </div>

        {editingTech ? (
          <TechnologyEditor
            designId={design.id}
            elementId={element.id}
            existing={meta}
            existingTags={tags}
            onDone={() => setEditingTech(false)}
          />
        ) : hasMeta || tags.length > 0 ? (
          <div>
            {TECH_FIELDS.map(({ key, label }) => {
              const value = meta?.[key as keyof NonNullable<typeof meta>];
              if (!value) return null;
              return (
                <div key={key} style={{ display: "flex", gap: 6, marginBottom: 4 }}>
                  <span style={{ fontSize: 11, color: "#9CA3AF", minWidth: 72, flexShrink: 0 }}>{label}</span>
                  <span style={{ fontSize: 12, color: "#111827" }}>{value}</span>
                </div>
              );
            })}
            {tags.length > 0 && (
              <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                {tags.map(tag => (
                  <span key={tag} style={{ background: "#EDE9FE", color: "#5B21B6", fontSize: 11, padding: "2px 6px", borderRadius: 3 }}>
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p style={{ fontSize: 12, color: "#9CA3AF", fontStyle: "italic" }}>No technology metadata added yet</p>
        )}
      </section>

      <section style={{ marginTop: 12 }}>
        <h4 style={{ fontSize: 13, marginBottom: 6 }}>Provenance:</h4>
        <p style={{ fontSize: 12, color: "#555" }}>{formatProvenance(element.provenance)}</p>
      </section>
    </div>
  );
}
