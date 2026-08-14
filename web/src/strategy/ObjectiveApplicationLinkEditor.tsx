/** ObjectiveApplicationLinkEditor — near-verbatim mirror of
 * ObjectiveCapabilityLinkEditor.tsx's structure (ADP-d8u.2), adapted to link
 * a StrategicObjective to real applications instead of capabilities. Uses
 * useApplicationsForLinking (a plain, non-Suspense query) rather than
 * web/src/api/application.ts's own useApplications, which is
 * useSuspenseQuery-based and requires a <Suspense> boundary this part of the
 * tree doesn't have. */

import React, { useState } from "react";
import {
  useApplicationsForLinking,
  useLinkObjectiveApplication,
  useUnlinkObjectiveApplication,
  type StrategicObjective,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveApplicationLinkEditor({ objective }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const allApplications = useApplicationsForLinking();
  const link = useLinkObjectiveApplication(objective.id);
  const unlink = useUnlinkObjectiveApplication(objective.id);

  const linkedIds = new Set(objective.application_ids);
  const linked = (allApplications.data?.items ?? []).filter((a) => linkedIds.has(a.id));
  const available = (allApplications.data?.items ?? []).filter((a) => !linkedIds.has(a.id));

  function handleAdd() {
    if (!selectedId) return;
    setLinkError(null);
    const name = available.find((a) => a.id === selectedId)?.name ?? selectedId;
    link.mutate(selectedId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(name);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link application");
        }
      },
    });
  }

  if (allApplications.isLoading) {
    return (
      <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading applications…</p>
    );
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No applications linked yet.
          </p>
        )}
        {linked.map((a) => (
          <div
            key={a.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{a.name}</span>
            <button
              onClick={() => unlink.mutate(a.id, { onSuccess: () => feedback.showRemoved(a.name) })}
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
          <option value="">— select application —</option>
          {available.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
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
