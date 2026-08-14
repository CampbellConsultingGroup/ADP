/** InitiativeObjectiveLinkEditor — the initiative-side mirror of
 * ObjectiveInitiativeLinkEditor.tsx, wiring the useLinkInitiativeObjective/
 * useUnlinkInitiativeObjective hooks (built alongside the objective-side pair
 * but never called from any UI until now). Simpler than its mirror: unlike
 * GET /objectives/{id}, GET /initiatives/{id} already returns objective_ids
 * inline, so no separate reverse-lookup query is needed here -- the "linked"
 * set comes straight off the `initiative` prop. (ADP-pgx) */

import React, { useState } from "react";
import {
  useObjectives,
  useLinkInitiativeObjective,
  useUnlinkInitiativeObjective,
  type StrategyInitiative,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";
import NavLinkButton from "./NavLinkButton";

interface Props {
  initiative: StrategyInitiative;
  /** Cross-navigation: jump to a linked objective's own detail view. When
   *  omitted, names render as plain text. */
  onNavigateToObjective?: (objectiveId: string) => void;
}

export default function InitiativeObjectiveLinkEditor({ initiative, onNavigateToObjective }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const allObjectives = useObjectives();
  const link = useLinkInitiativeObjective(initiative.id);
  const unlink = useUnlinkInitiativeObjective(initiative.id);

  const linkedIds = new Set(initiative.objective_ids);
  const all = allObjectives.data?.items ?? [];
  const linked = all.filter((o) => linkedIds.has(o.id));
  const available = all.filter((o) => !linkedIds.has(o.id));

  function handleAdd() {
    if (!selectedId) return;
    setLinkError(null);
    const statement = available.find((o) => o.id === selectedId)?.statement ?? selectedId;
    link.mutate(selectedId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(statement);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else {
          setLinkError(err.message || "Failed to link objective");
        }
      },
    });
  }

  if (allObjectives.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading objectives…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {linked.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No objectives linked yet.
          </p>
        )}
        {linked.map((o) => (
          <div
            key={o.id}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>
              {onNavigateToObjective ? (
                <NavLinkButton onClick={() => onNavigateToObjective(o.id)} title="Jump to this objective">
                  {o.statement}
                </NavLinkButton>
              ) : (
                o.statement
              )}
            </span>
            <button
              onClick={() => unlink.mutate(o.id, { onSuccess: () => feedback.showRemoved(o.statement) })}
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
          <option value="">— select objective —</option>
          {available.map((o) => (
            <option key={o.id} value={o.id}>
              {o.statement}
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
