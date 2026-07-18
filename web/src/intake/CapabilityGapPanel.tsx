/** CapabilityGapPanel — compares confirmed requirements against the business
 * and technical capability registries (ADP-zg3.4). Advisory only: cites
 * existing capabilities that already cover a requirement, and surfaces
 * requirements with no good match as gaps. Never creates/modifies registry
 * records.
 */

import React from "react";
import type { CapabilityGapSection } from "../api/intake";
import { useCapabilityGaps } from "../api/intake";

interface Props {
  designId: string;
}

function Section({ title, section }: { title: string; section: CapabilityGapSection }) {
  if (section.present.length === 0 && section.missing.length === 0) return null;

  return (
    <div style={{ marginBottom: 10 }}>
      <p style={{ fontSize: 11, fontWeight: 600, color: "var(--ink)", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {title}
      </p>
      {section.present.length > 0 && (
        <ul style={{ margin: "0 0 4px", padding: "0 0 0 14px" }}>
          {section.present.map((m) => (
            <li key={`${m.requirement_id}-${m.capability_id}`} style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 2 }}>
              <span style={{ color: "var(--good)" }}>✓</span> {m.requirement_title}{" "}
              <span style={{ color: "var(--ink-3)", fontSize: 11 }}>→ covered by "{m.capability_name}"</span>
            </li>
          ))}
        </ul>
      )}
      {section.missing.length > 0 && (
        <ul style={{ margin: 0, padding: "0 0 0 14px" }}>
          {section.missing.map((g) => (
            <li key={g.requirement_id} style={{ fontSize: 12, color: "var(--warn)", marginBottom: 2 }}>
              ⚠ {g.requirement_title} <span style={{ color: "var(--ink-3)", fontSize: 11 }}>(no matching capability — gap)</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CapabilityGapPanel({ designId }: Props): React.ReactElement | null {
  const { data, isLoading, error } = useCapabilityGaps(designId);

  if (!designId) return null;
  if (isLoading) return null;
  if (error || !data) return null;

  const isEmpty =
    data.business_capabilities.present.length === 0 &&
    data.business_capabilities.missing.length === 0 &&
    data.technical_capabilities.present.length === 0 &&
    data.technical_capabilities.missing.length === 0;

  if (isEmpty) return null;

  return (
    <div style={panelStyle}>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>
        Capability Gap Analysis
      </h4>
      <p style={{ fontSize: 11, color: "var(--ink-3)", margin: "0 0 8px" }}>
        Advisory — compares confirmed requirements against existing capabilities.
      </p>
      <Section title="Business Capabilities" section={data.business_capabilities} />
      <Section title="Technical Capabilities" section={data.technical_capabilities} />
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  padding: "12px 14px",
  background: "var(--warn-wash)",
  border: "1px solid var(--warn)",
  borderRadius: 6,
  marginTop: 12,
};
