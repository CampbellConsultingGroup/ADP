import React from "react";
import type { TechnologyCount } from "../api/portfolio";

interface TechnologyLandscapeProps {
  technologies: TechnologyCount[];
  activeTechnology: string | null;
  onSelect: (tech: string | null) => void;
  isLoading?: boolean;
}

export default function TechnologyLandscape({
  technologies,
  activeTechnology,
  onSelect,
  isLoading,
}: TechnologyLandscapeProps): React.ReactElement {
  if (isLoading) {
    return (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} style={{ width: 100, height: 32, borderRadius: 16, background: "var(--surface-3)" }} />
        ))}
      </div>
    );
  }

  if (technologies.length === 0) {
    return (
      <p style={{ color: "var(--ink-3)", fontSize: 14 }}>
        No technology tags recorded yet. Tag elements via the Inspection Panel.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {technologies.map((t) => {
        const isActive = activeTechnology === t.technology;
        return (
          <button
            key={t.technology}
            onClick={() => onSelect(isActive ? null : t.technology)}
            aria-pressed={isActive}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 16,
              border: `1px solid ${isActive ? "var(--accent)" : "var(--border)"}`,
              background: isActive ? "var(--accent-wash)" : "var(--surface-2)",
              color: isActive ? "var(--accent-2)" : "var(--ink-2)",
              cursor: "pointer", fontSize: 13, fontWeight: isActive ? 600 : 400, fontFamily: "var(--font)",
              transition: "all .15s",
            }}
          >
            {t.technology}
            <span
              style={{
                background: isActive ? "var(--accent)" : "var(--ink-3)", color: "#fff", borderRadius: 10,
                padding: "0 6px", fontSize: 11, fontWeight: 700, minWidth: 20, textAlign: "center",
              }}
            >
              {t.design_count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
