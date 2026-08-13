/** "Depends on / Blocks" panel (ADP-d8u.6, US2) — both directions of
 * strategic_objective_dependencies, an add-dependency control, a remove
 * action per entry, and the cycle-rejection message from a 400 response
 * surfaced clearly (direct, chained, and self-dependency all rejected
 * server-side by _would_create_cycle). Mirrors ObjectiveInitiativeLinkEditor's
 * structure. */

import React, { useState } from "react";
import {
  useObjectives,
  useObjectiveDependencies,
  useAddObjectiveDependency,
  useRemoveObjectiveDependency,
} from "../api/strategy";
import { ApiError } from "../api/client";

/** FastAPI's HTTPException(detail=str(exc)) sends a plain string detail --
 * mirrors PromptEditor.tsx's own established ApiError.body.detail unwrap
 * (ADP-o5c), just for a string payload instead of a nested object. */
function cycleDetailMessage(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 400) return null;
  const detail = (err.body as { detail?: string } | undefined)?.detail;
  return typeof detail === "string" ? detail : null;
}

interface Props {
  objectiveId: string;
}

export default function ObjectiveDependencyPanel({ objectiveId }: Props): React.ReactElement {
  const [selectedId, setSelectedId] = useState<string>("");
  const [addError, setAddError] = useState<string | null>(null);

  const allObjectives = useObjectives();
  const dependencies = useObjectiveDependencies(objectiveId);
  const addDependency = useAddObjectiveDependency(objectiveId);
  const removeDependency = useRemoveObjectiveDependency(objectiveId);

  const statementById = new Map((allObjectives.data?.items ?? []).map((o) => [o.id, o.statement]));
  const dependsOn = dependencies.data?.depends_on ?? [];
  const blocks = dependencies.data?.blocks ?? [];
  const excluded = new Set([objectiveId, ...dependsOn]);
  const available = (allObjectives.data?.items ?? []).filter((o) => !excluded.has(o.id));

  function handleAdd() {
    if (!selectedId) return;
    setAddError(null);
    addDependency.mutate(selectedId, {
      onSuccess: () => setSelectedId(""),
      onError: (err: Error & { status?: number }) => {
        const cycleDetail = cycleDetailMessage(err);
        if (cycleDetail) {
          // Cycle rejection (direct, chained, or self-dependency) --
          // surface the server's own explanatory detail message.
          setAddError(cycleDetail);
        } else if (err.status === 409) {
          setAddError("Already depends on this objective.");
        } else {
          setAddError(err.message || "Failed to add dependency");
        }
      },
    });
  }

  if (allObjectives.isLoading || dependencies.isLoading) {
    return <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Loading dependencies…</p>;
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.75rem" }}>
        <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--ink-3)", marginBottom: "0.35rem" }}>
          Depends on
        </div>
        {dependsOn.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            This objective doesn't depend on anything.
          </p>
        )}
        {dependsOn.map((id) => (
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
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{statementById.get(id) ?? id}</span>
            <button
              onClick={() => removeDependency.mutate(id)}
              disabled={removeDependency.isPending}
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
            setAddError(null);
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
          disabled={!selectedId || addDependency.isPending}
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
          Add dependency
        </button>
      </div>
      {addError && (
        <p style={{ color: "var(--error, var(--crit))", fontSize: "0.8rem", margin: "0.35rem 0 0" }}>
          {addError}
        </p>
      )}

      <div style={{ marginTop: "1rem" }}>
        <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--ink-3)", marginBottom: "0.35rem" }}>
          Blocks
        </div>
        {blocks.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>
            No other objective depends on this one.
          </p>
        )}
        {blocks.map((id) => (
          <div key={id} style={{ padding: "0.35rem 0", borderBottom: "1px solid var(--border)" }}>
            <span style={{ fontSize: "0.85rem" }}>{statementById.get(id) ?? id}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
