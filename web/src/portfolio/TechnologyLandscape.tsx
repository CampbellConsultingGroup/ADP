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
          <div
            key={i}
            style={{
              width: 100,
              height: 32,
              borderRadius: 16,
              backgroundColor: "#E5E7EB",
              animation: "pulse 1.5s infinite",
            }}
          />
        ))}
      </div>
    );
  }

  if (technologies.length === 0) {
    return (
      <p style={{ color: "#6B7280", fontSize: 14 }}>
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
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 12px",
              borderRadius: 16,
              border: isActive ? "2px solid #1D4ED8" : "1.5px solid #D1D5DB",
              backgroundColor: isActive ? "#DBEAFE" : "#F9FAFB",
              color: isActive ? "#1E40AF" : "#374151",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              transition: "all 0.15s",
            }}
            aria-pressed={isActive}
          >
            {t.technology}
            <span
              style={{
                backgroundColor: isActive ? "#1D4ED8" : "#9CA3AF",
                color: "#fff",
                borderRadius: 10,
                padding: "0 6px",
                fontSize: 11,
                fontWeight: 700,
                minWidth: 20,
                textAlign: "center",
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
