/** ObjectiveControlLinkEditor — 925-strategy-compliance-linkage (COMPLY-05): link a Strategic
 *  Objective to a Control, recording that the objective is regulatory-driven (US2, "why does this
 *  objective exist"). A bare link (no status), so unlike ObjectiveDesignLinkEditor.tsx this has no
 *  flat "list all Controls" hook to populate a dropdown from -- Controls are nested per Framework,
 *  not a standalone registry list. A plain control-id text input plays the same role. */

import React, { useState } from "react";
import {
  useLinkObjectiveControl,
  useUnlinkObjectiveControl,
  type StrategicObjective,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveControlLinkEditor({ objective }: Props): React.ReactElement {
  const [controlId, setControlId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const link = useLinkObjectiveControl(objective.id);
  const unlink = useUnlinkObjectiveControl(objective.id);

  function handleAdd() {
    if (!controlId.trim()) return;
    setLinkError(null);
    const id = controlId.trim();
    link.mutate(id, {
      onSuccess: () => {
        setControlId("");
        feedback.showLinked(id);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else if (err.status === 404) {
          setLinkError("No such control");
        } else {
          setLinkError(err.message || "Failed to link control");
        }
      },
    });
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {objective.control_ids.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No controls linked yet.
          </p>
        )}
        {objective.control_ids.map((id) => (
          <div
            key={id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{id}</span>
            <button
              onClick={() => unlink.mutate(id, { onSuccess: () => feedback.showRemoved(id) })}
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
        <input
          value={controlId}
          onChange={(e) => {
            setControlId(e.target.value);
            setLinkError(null);
          }}
          placeholder="Control id"
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
        />
        <button
          onClick={handleAdd}
          disabled={!controlId.trim() || link.isPending}
          style={{
            padding: "0.3rem 0.75rem",
            fontSize: "0.85rem",
            borderRadius: "4px",
            border: "none",
            background: "var(--accent)",
            color: "#fff",
            cursor: controlId.trim() ? "pointer" : "not-allowed",
            opacity: controlId.trim() ? 1 : 0.5,
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
