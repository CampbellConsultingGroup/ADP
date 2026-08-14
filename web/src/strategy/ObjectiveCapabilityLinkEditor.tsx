/** ObjectiveCapabilityLinkEditor — near-verbatim mirror of
 * web/src/business/DesignLinkEditor.tsx's structure (research.md
 * Decision 4), adapted to link a StrategicObjective to real
 * BusinessCapability records instead of designs. Unlike DesignLinkEditor,
 * the "linked" set comes straight off the objective prop (capability_ids)
 * rather than a separate query -- adp.strategy's GET /objectives/{id}
 * already returns it inline. */

import React, { useState } from "react";
import { useCapabilities } from "../api/business";
import {
  useLinkObjectiveCapability,
  useUnlinkObjectiveCapability,
  type StrategicObjective,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveCapabilityLinkEditor({ objective }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const allCapabilities = useCapabilities();
  const link = useLinkObjectiveCapability(objective.id);
  const unlink = useUnlinkObjectiveCapability(objective.id);

  const linkedIds = new Set(objective.capability_ids);
  const linked = (allCapabilities.data?.items ?? []).filter((c) => linkedIds.has(c.id));
  const available = (allCapabilities.data?.items ?? []).filter((c) => !linkedIds.has(c.id));

  function handleAdd() {
    if (!selectedId) return;
    setLinkError(null);
    const name = available.find((c) => c.id === selectedId)?.name ?? selectedId;
    link.mutate(selectedId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(name);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link capability");
        }
      },
    });
  }

  if (allCapabilities.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading capabilities…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No capabilities linked yet.
          </p>
        )}
        {linked.map((c) => (
          <div
            key={c.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{c.name}</span>
            <button
              onClick={() => unlink.mutate(c.id, { onSuccess: () => feedback.showRemoved(c.name) })}
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
          <option value="">— select capability —</option>
          {available.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
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
      {feedback.message && (
        <p style={{ color: "var(--good)", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>
          {feedback.message}
        </p>
      )}
    </div>
  );
}
