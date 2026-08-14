/** ObjectiveInitiativeLinkEditor — near-verbatim mirror of
 * ObjectiveCapabilityLinkEditor.tsx's structure, adapted to link a
 * StrategicObjective to StrategyInitiative records (ADP-d8u.6). Unlike the
 * capability editor, the "linked" set comes from a dedicated reverse-lookup
 * query (useObjectiveInitiatives) rather than an inline field on the
 * objective, since GET /objectives/{id} doesn't carry initiative_ids. */

import React, { useState } from "react";
import {
  useInitiatives,
  useObjectiveInitiatives,
  useLinkObjectiveToInitiative,
  useUnlinkObjectiveFromInitiative,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objectiveId: string;
}

export default function ObjectiveInitiativeLinkEditor({ objectiveId }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const allInitiatives = useInitiatives();
  const linkedInitiatives = useObjectiveInitiatives(objectiveId);
  const link = useLinkObjectiveToInitiative(objectiveId);
  const unlink = useUnlinkObjectiveFromInitiative(objectiveId);

  const linkedIds = new Set((linkedInitiatives.data?.items ?? []).map((i) => i.id));
  const linked = linkedInitiatives.data?.items ?? [];
  const available = (allInitiatives.data?.items ?? []).filter((i) => !linkedIds.has(i.id));

  function handleAdd() {
    if (!selectedId) return;
    setLinkError(null);
    const name = available.find((i) => i.id === selectedId)?.name ?? selectedId;
    link.mutate(selectedId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(name);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link initiative");
        }
      },
    });
  }

  if (allInitiatives.isLoading || linkedInitiatives.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading initiatives…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No initiatives linked yet.
          </p>
        )}
        {linked.map((i) => (
          <div
            key={i.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{i.name}</span>
            <button
              onClick={() => unlink.mutate(i.id, { onSuccess: () => feedback.showRemoved(i.name) })}
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
          <option value="">— select initiative —</option>
          {available.map((i) => (
            <option key={i.id} value={i.id}>
              {i.name}
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
