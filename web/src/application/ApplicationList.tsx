import type { Application, TimeClassification } from "../api/application";
import { Button, StatusBadge, type BadgeTone } from "../ui";

export const TIME_TONE: Record<TimeClassification, BadgeTone> = {
  Invest: "good",
  Migrate: "warn",
  Eliminate: "crit",
  Tolerate: "neutral",
};

interface Props {
  apps: Application[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
}

export default function ApplicationList({ apps, selectedId, onSelect, onAdd }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "10px 12px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--ink-2)" }}>Applications ({apps.length})</span>
        <Button variant="primary" size="sm" icon="plus" onClick={onAdd}>Add</Button>
      </div>
      {apps.length === 0 && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--ink-3)", fontSize: 13 }}>No applications yet.</div>
      )}
      {apps.map((app) => {
        const active = selectedId === app.id;
        return (
          <button
            key={app.id}
            onClick={() => onSelect(app.id)}
            style={{
              display: "flex", flexDirection: "column", alignItems: "flex-start",
              padding: "10px 14px", borderBottom: "1px solid var(--border)",
              background: active ? "var(--accent-wash)" : "transparent",
              border: "none", borderLeft: active ? "3px solid var(--accent)" : "3px solid transparent",
              cursor: "pointer", textAlign: "left", width: "100%", color: "inherit", fontFamily: "inherit",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", flex: 1 }}>{app.name}</span>
              {app.time_classification && <StatusBadge tone={TIME_TONE[app.time_classification]}>{app.time_classification}</StatusBadge>}
              {app.health_score !== null && (
                <span style={{ fontSize: 11, color: "var(--ink-3)" }}>
                  {"★".repeat(app.health_score)}{"☆".repeat(5 - app.health_score)}
                </span>
              )}
            </div>
            {app.vendor && <span style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>{app.vendor}</span>}
          </button>
        );
      })}
    </div>
  );
}
