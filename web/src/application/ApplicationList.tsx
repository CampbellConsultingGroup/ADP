import type { Application, TimeClassification } from "../api/application";

const TIME_COLORS: Record<TimeClassification, { bg: string; text: string }> = {
  Invest: { bg: "#d4edda", text: "#155724" },
  Migrate: { bg: "#fff3cd", text: "#856404" },
  Eliminate: { bg: "#f8d7da", text: "#721c24" },
  Tolerate: { bg: "#e2e3e5", text: "#383d41" },
};

interface Props {
  apps: Application[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
}

export default function ApplicationList({ apps, selectedId, onSelect, onAdd }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ padding: "8px 12px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e0e0e0" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "#555" }}>Applications ({apps.length})</span>
        <button
          onClick={onAdd}
          style={{ fontSize: 12, padding: "4px 10px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
        >
          + Add Application
        </button>
      </div>
      {apps.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "#888", fontSize: 13 }}>
          No applications yet.
        </div>
      )}
      {apps.map((app) => {
        const tc = app.time_classification;
        const colors = tc ? TIME_COLORS[tc] : { bg: "#f5f5f5", text: "#555" };
        return (
          <button
            key={app.id}
            onClick={() => onSelect(app.id)}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
              padding: "10px 14px",
              borderBottom: "1px solid #eee",
              background: selectedId === app.id ? "#e8f0fe" : "transparent",
              border: "none",
              borderLeft: selectedId === app.id ? "3px solid #1168BD" : "3px solid transparent",
              cursor: "pointer",
              textAlign: "left",
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "#222", flex: 1 }}>{app.name}</span>
              {tc && (
                <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 10, background: colors.bg, color: colors.text }}>
                  {tc}
                </span>
              )}
              {app.health_score !== null && (
                <span style={{ fontSize: 11, color: "#666" }}>
                  {"★".repeat(app.health_score)}{"☆".repeat(5 - app.health_score)}
                </span>
              )}
            </div>
            {app.vendor && (
              <span style={{ fontSize: 11, color: "#888", marginTop: 2 }}>{app.vendor}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
