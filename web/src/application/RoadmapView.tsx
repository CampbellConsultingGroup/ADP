import { useState } from "react";
import {
  useRoadmap,
  useInitiatives,
  useCreateInitiative,
  useDeleteInitiative,
} from "../api/application";
import type { RoadmapEntry } from "../api/application";

/**
 * APM US6 — lifecycle & roadmap view (ADP-SPEC-038).
 * Decommission track (Eliminate-classified or sunset/retired apps, with EOL
 * date + initiative links) plus transformation-initiative management.
 */

function RoadmapCard({ entry }: { entry: RoadmapEntry }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
        padding: "8px 12px",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 6,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{entry.name}</span>
        <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{entry.lifecycle_status}</span>
      </div>
      <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
        {entry.time_classification && <span>{entry.time_classification}</span>}
        {entry.end_of_life_date && <span> · EOL {entry.end_of_life_date}</span>}
      </div>
      {entry.initiative_links.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {entry.initiative_links.map((link) => (
            <span
              key={link.initiative_id}
              style={{ fontSize: 11, background: "var(--accent-wash)", color: "var(--accent)", padding: "1px 7px", borderRadius: 10 }}
            >
              {link.initiative_name} · {link.planned_disposition}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function RoadmapView() {
  const { data: roadmap, isLoading: roadmapLoading } = useRoadmap();
  const { data: initiatives } = useInitiatives();
  const createInitiative = useCreateInitiative();
  const deleteInitiative = useDeleteInitiative();

  const [name, setName] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!name.trim()) { setError("Name is required"); return; }
    setError(null);
    try {
      await createInitiative.mutateAsync({ name: name.trim(), target_date: targetDate || null });
      setName("");
      setTargetDate("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create");
    }
  };

  return (
    <div style={{ padding: 24, overflow: "auto", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>Roadmap</h2>
        <p style={{ margin: 0, color: "var(--ink-3)", fontSize: 13 }}>
          Decommission track — applications classified Eliminate or in a sunset/retired lifecycle — plus the
          transformation initiatives driving them.
        </p>
      </div>

      {/* Decommission track */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 12, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
          Decommission Track {roadmap ? `(${roadmap.total})` : ""}
        </div>
        {roadmapLoading ? (
          <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>
        ) : roadmap && roadmap.items.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No applications currently on the decommission track.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 8 }}>
            {roadmap?.items.map((entry) => <RoadmapCard key={entry.app_id} entry={entry} />)}
          </div>
        )}
      </div>

      {/* Transformation initiatives */}
      <div>
        <div style={{ fontSize: 12, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
          Transformation Initiatives {initiatives ? `(${initiatives.total})` : ""}
        </div>
        {error && <div style={{ fontSize: 11, color: "var(--crit)", marginBottom: 6 }}>{error}</div>}
        {initiatives?.items.length === 0 && (
          <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 8 }}>No initiatives yet.</div>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 12 }}>
          {initiatives?.items.map((i) => (
            <div key={i.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
              <span style={{ flex: 1 }}>{i.name}</span>
              {i.target_date && <span style={{ fontSize: 11, color: "var(--ink-3)" }}>target {i.target_date}</span>}
              <button
                onClick={() => deleteInitiative.mutate(i.id)}
                style={{ fontSize: 11, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New initiative name"
            style={{ flex: 1, fontSize: 13, padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
          />
          <input
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            style={{ fontSize: 13, padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
          />
          <button
            onClick={handleCreate}
            style={{ fontSize: 13, padding: "6px 14px", background: "var(--accent, #2874A6)", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
