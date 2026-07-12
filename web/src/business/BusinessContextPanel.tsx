/** BusinessContextPanel — shows capabilities and value streams linked to a design (ADP-SPEC-034). */

import React from "react";
import { useDesignBusinessContext } from "../api/business";
import type { AppView } from "../shell";

interface Props {
  designId: string | null;
  onNavigate: (view: AppView) => void;
}

export default function BusinessContextPanel({ designId, onNavigate }: Props): React.ReactElement | null {
  const { data, isLoading, error } = useDesignBusinessContext(designId);

  if (!designId) return null;
  if (isLoading) {
    return (
      <div style={panelStyle}>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary, var(--ink-3))", margin: 0 }}>
          Loading business context…
        </p>
      </div>
    );
  }
  if (error) return null;

  const hasCapabilities = (data?.capabilities?.length ?? 0) > 0;
  const hasValueStreams = (data?.value_streams?.length ?? 0) > 0;
  const isEmpty = !hasCapabilities && !hasValueStreams;

  return (
    <div style={panelStyle}>
      <h4 style={{ margin: "0 0 8px", fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>
        Business Architecture
      </h4>

      {isEmpty ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <p style={{ fontSize: 12, color: "var(--ink-3)", margin: 0 }}>
            No business entities linked to this design.
          </p>
          <button
            onClick={() => onNavigate("business")}
            style={linkBtn}
          >
            Go to Business →
          </button>
        </div>
      ) : (
        <>
          {hasCapabilities && (
            <div style={{ marginBottom: 8 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: "var(--good)", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Capabilities
              </p>
              <ul style={{ margin: 0, padding: "0 0 0 14px" }}>
                {data!.capabilities.map((c) => (
                  <li key={c.capability_id} style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 2 }}>
                    {c.name}{" "}
                    <span style={{ color: "var(--ink-3)", fontSize: 11 }}>L{c.level}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasValueStreams && (
            <div style={{ marginBottom: 8 }}>
              <p style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)", margin: "0 0 4px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Value Streams
              </p>
              <ul style={{ margin: 0, padding: "0 0 0 14px" }}>
                {data!.value_streams.map((v) => (
                  <li key={v.value_stream_id} style={{ fontSize: 12, color: "var(--ink-2)", marginBottom: 2 }}>
                    {v.name}
                    {v.stakeholder && (
                      <span style={{ color: "var(--ink-3)", fontSize: 11 }}> · {v.stakeholder}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <button onClick={() => onNavigate("business")} style={{ ...linkBtn, marginTop: 4 }}>
            Go to Business →
          </button>
        </>
      )}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  padding: "12px 14px",
  background: "var(--good-wash)",
  border: "1px solid var(--good)",
  borderRadius: 6,
  marginTop: 12,
};

const linkBtn: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  fontSize: 12,
  color: "var(--accent)",
  padding: 0,
  textDecoration: "underline",
};
