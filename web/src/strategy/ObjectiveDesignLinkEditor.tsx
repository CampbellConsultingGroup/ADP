/** ObjectiveDesignLinkEditor — near-verbatim mirror of
 * ObjectiveCapabilityLinkEditor.tsx's structure (ADP-d8u.2), adapted to link
 * a StrategicObjective to real designs instead of capabilities. Unlike the
 * capability editor, the design list comes from a plain, non-Suspense query
 * (useDesignsForLinking) rather than web/src/api/designs.ts's own hooks --
 * see research.md/data-model.md for why. */

import React, { useState } from "react";
import {
  useDesignsForLinking,
  useLinkObjectiveDesign,
  useUnlinkObjectiveDesign,
  type StrategicObjective,
} from "../api/strategy";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveDesignLinkEditor({ objective }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);

  const allDesigns = useDesignsForLinking();
  const link = useLinkObjectiveDesign(objective.id);
  const unlink = useUnlinkObjectiveDesign(objective.id);

  const linkedIds = new Set(objective.design_ids);
  const linked = (allDesigns.data?.designs ?? []).filter((d) => linkedIds.has(d.id));
  const available = (allDesigns.data?.designs ?? []).filter((d) => !linkedIds.has(d.id));

  function handleAdd() {
    if (!selectedId) return;
    setLinkError(null);
    link.mutate(selectedId, {
      onSuccess: () => setSelectedId(""),
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link design");
        }
      },
    });
  }

  if (allDesigns.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading designs…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No designs linked yet.
          </p>
        )}
        {linked.map((d) => (
          <div
            key={d.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{d.title}</span>
            <button
              onClick={() => unlink.mutate(d.id)}
              disabled={unlink.isPending}
              style={{
                background: "none",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                cursor: "pointer",
                padding: "2px 8px",
                fontSize: "0.75rem",
                color: "var(--text-secondary)",
              }}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={selectedId}
          onChange={(e) => {
            setSelectedId(e.target.value);
            setLinkError(null);
          }}
          style={{
            flex: 1,
            minWidth: "160px",
            padding: "0.3rem 0.5rem",
            fontSize: "0.85rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            background: "var(--bg)",
            color: "var(--text)",
          }}
        >
          <option value="">— select design —</option>
          {available.map((d) => (
            <option key={d.id} value={d.id}>
              {d.title}
            </option>
          ))}
        </select>
        <button
          onClick={handleAdd}
          disabled={!selectedId || link.isPending}
          style={{
            padding: "0.3rem 0.75rem",
            fontSize: "0.85rem",
            borderRadius: "4px",
            border: "none",
            background: "var(--accent)",
            color: "#fff",
            cursor: selectedId ? "pointer" : "not-allowed",
            opacity: selectedId ? 1 : 0.5,
          }}
        >
          Link
        </button>
      </div>
      {linkError && (
        <p style={{ color: "var(--error, var(--crit))", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>
          {linkError}
        </p>
      )}
    </div>
  );
}
