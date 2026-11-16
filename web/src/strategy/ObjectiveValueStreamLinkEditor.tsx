/** ObjectiveValueStreamLinkEditor — same shape as
 * ObjectiveCapabilityLinkEditor.tsx (both near-verbatim mirrors of
 * web/src/business/DesignLinkEditor.tsx per research.md Decision 4),
 * substituting ValueStream for BusinessCapability. */

import React, { useState } from "react";
import { useValueStreams } from "../api/business";
import {
  useLinkObjectiveValueStream,
  useUnlinkObjectiveValueStream,
  type StrategicObjective,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveValueStreamLinkEditor({ objective }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const allValueStreams = useValueStreams();
  const link = useLinkObjectiveValueStream(objective.id);
  const unlink = useUnlinkObjectiveValueStream(objective.id);

  const linkedIds = new Set(objective.value_stream_ids);
  const linked = (allValueStreams.data?.items ?? []).filter((v) => linkedIds.has(v.id));
  const available = (allValueStreams.data?.items ?? []).filter((v) => !linkedIds.has(v.id));

  function handleAdd(chosenId: string) {
    if (!chosenId) return;
    setSelectedId(chosenId);
    setLinkError(null);
    const name = available.find((v) => v.id === chosenId)?.name ?? chosenId;
    link.mutate(chosenId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(name);
      },
      onError: (err: Error & { status?: number }) => {
        setSelectedId("");
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link value stream");
        }
      },
    });
  }

  if (allValueStreams.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading value streams…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No value streams linked yet.
          </p>
        )}
        {linked.map((v) => (
          <div
            key={v.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{v.name}</span>
            <button
              onClick={() => unlink.mutate(v.id, { onSuccess: () => feedback.showRemoved(v.name) })}
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
          onChange={(e) => handleAdd(e.target.value)}
          disabled={link.isPending}
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
          <option value="">Link a value stream…</option>
          {available.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
        </select>
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
