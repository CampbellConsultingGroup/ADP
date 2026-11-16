/** ObjectiveControlLinkEditor — 925-strategy-compliance-linkage (COMPLY-05): link a Strategic
 *  Objective to a Control, recording that the objective is regulatory-driven (US2, "why does this
 *  objective exist"). A bare link (no status).
 *
 *  ADP-w7z: works like the Capabilities screen's dropdowns -- choosing a control links it at once,
 *  with no separate Link button. Controls are nested per framework (there is no flat list), so you
 *  pick a framework first, then a control from its tree. */

import React, { useState } from "react";
import { flattenControls, useAllControls, useFramework, useFrameworks } from "../api/compliance";
import {
  useLinkObjectiveControl,
  useUnlinkObjectiveControl,
  type StrategicObjective,
} from "../api/strategy";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  objective: StrategicObjective;
}

const selectStyle: React.CSSProperties = {
  flex: 1,
  minWidth: "160px",
  padding: "0.3rem 0.5rem",
  fontSize: "0.85rem",
  border: "1px solid var(--border)",
  borderRadius: "4px",
  background: "var(--bg)",
  color: "var(--text)",
};

export default function ObjectiveControlLinkEditor({ objective }: Props): React.ReactElement {
  const [frameworkId, setFrameworkId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const frameworks = useFrameworks();
  const framework = useFramework(frameworkId || null);
  const allControls = useAllControls();
  const link = useLinkObjectiveControl(objective.id);
  const unlink = useUnlinkObjectiveControl(objective.id);

  const linkedIds = new Set(objective.control_ids);
  const available = framework.data ? flattenControls(framework.data).filter((c) => !linkedIds.has(c.id)) : [];
  const label = (id: string): string => {
    const c = allControls.byId.get(id);
    return c ? `${c.code} — ${c.title}` : id;
  };

  function handleAdd(chosenId: string) {
    if (!chosenId) return;
    setSelectedId(chosenId);
    setLinkError(null);
    const name = label(chosenId);
    link.mutate(chosenId, {
      onSuccess: () => {
        setSelectedId("");
        feedback.showLinked(name);
      },
      onError: (err: Error & { status?: number }) => {
        setSelectedId("");
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
        {objective.control_ids.map((id) => {
          const c = allControls.byId.get(id);
          return (
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
              <span style={{ flex: 1, fontSize: "0.85rem" }}>{label(id)}</span>
              {c && <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{c.framework_name}</span>}
              <button
                onClick={() => unlink.mutate(id, { onSuccess: () => feedback.showRemoved(label(id)) })}
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
          );
        })}
      </div>

      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <select
          aria-label="Framework"
          value={frameworkId}
          onChange={(e) => {
            setFrameworkId(e.target.value);
            setLinkError(null);
          }}
          style={selectStyle}
        >
          <option value="">Choose a framework…</option>
          {(frameworks.data?.items ?? []).map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
        {frameworkId && (
          <select
            aria-label="Control"
            value={selectedId}
            onChange={(e) => handleAdd(e.target.value)}
            disabled={link.isPending || framework.isLoading}
            style={selectStyle}
          >
            <option value="">{framework.isLoading ? "Loading controls…" : "Link a control…"}</option>
            {available.map((c) => (
              <option key={c.id} value={c.id}>
                {"  ".repeat(c.depth)}
                {c.code} — {c.title}
              </option>
            ))}
          </select>
        )}
      </div>
      {frameworkId && framework.data && available.length === 0 && (
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "0.35rem 0 0" }}>
          {framework.data.controls.length === 0
            ? "This framework has no controls yet."
            : "Every control in this framework is already linked."}
        </p>
      )}
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
