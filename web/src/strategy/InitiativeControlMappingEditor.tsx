/** InitiativeControlMappingEditor — 925-strategy-compliance-linkage (COMPLY-05): link a Strategy
 *  Initiative to a specific, already-assessed ControlMapping (the remediation loop, US1). Mirrors
 *  InitiativeObjectiveLinkEditor.tsx's shape; each linked row shows the target plus its *live*
 *  compliance_status badge (research.md D3 — always read fresh off the linked ControlMapping row,
 *  never a value stored on the link itself). Reuses TARGET_TYPE_LABEL/STATUS_LABEL/STATUS_COLOR
 *  from web/src/compliance/ControlMappingsEditor.tsx rather than a second copy. */

import React, { useState } from "react";
import {
  useLinkInitiativeControlMapping,
  useUnlinkInitiativeControlMapping,
  type ControlMappingRef,
  type StrategyInitiative,
} from "../api/strategy";
import type { MappingTargetType } from "../api/compliance";
import { STATUS_COLOR, STATUS_LABEL, TARGET_TYPE_LABEL } from "../compliance/ControlMappingsEditor";
import { useLinkFeedback } from "./useLinkFeedback";

interface Props {
  initiative: StrategyInitiative;
}

const TARGET_TYPES: MappingTargetType[] = [
  "capability", "application", "design", "pattern", "organization",
];

function refLabel(ref: ControlMappingRef): string {
  const target = ref.target_id ? `${TARGET_TYPE_LABEL[ref.target_type]}: ${ref.target_id}` : TARGET_TYPE_LABEL[ref.target_type];
  return `${ref.control_id} → ${target}`;
}

export default function InitiativeControlMappingEditor({ initiative }: Props): React.ReactElement {
  const [controlId, setControlId] = useState("");
  const [targetType, setTargetType] = useState<MappingTargetType>("application");
  const [targetId, setTargetId] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const feedback = useLinkFeedback();

  const link = useLinkInitiativeControlMapping(initiative.id);
  const unlink = useUnlinkInitiativeControlMapping(initiative.id);

  function handleAdd() {
    if (!controlId.trim()) return;
    if (targetType !== "organization" && !targetId.trim()) {
      setLinkError(`A ${TARGET_TYPE_LABEL[targetType]} id is required`);
      return;
    }
    setLinkError(null);
    const args = {
      controlId: controlId.trim(),
      targetType,
      targetId: targetType === "organization" ? undefined : targetId.trim(),
    };
    link.mutate(args, {
      onSuccess: () => {
        setControlId("");
        setTargetId("");
        feedback.showLinked(`${TARGET_TYPE_LABEL[targetType]} compliance gap`);
      },
      onError: (err: Error & { status?: number }) => {
        if (err.status === 409) {
          setLinkError("Already linked");
        } else if (err.status === 404) {
          setLinkError("No assessed mapping exists yet for that control/target");
        } else {
          setLinkError(err.message || "Failed to link");
        }
      },
    });
  }

  function handleRemove(ref: ControlMappingRef) {
    unlink.mutate(
      { controlId: ref.control_id, targetType: ref.target_type, targetId: ref.target_id },
      { onSuccess: () => feedback.showRemoved(refLabel(ref)) },
    );
  }

  return (
    <div style={{ marginTop: "0.75rem" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        {initiative.control_mappings.length === 0 && (
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "0 0 0.5rem" }}>
            No compliance gaps linked yet.
          </p>
        )}
        {initiative.control_mappings.map((ref) => (
          <div
            key={`${ref.control_id}:${ref.target_type}:${ref.target_id ?? ""}`}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              padding: "0.35rem 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span style={{ flex: 1, fontSize: "0.85rem" }}>{refLabel(ref)}</span>
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: STATUS_COLOR[ref.compliance_status] }}>
              {STATUS_LABEL[ref.compliance_status]}
            </span>
            <button
              onClick={() => handleRemove(ref)}
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
            width: "140px",
            padding: "0.3rem 0.5rem",
            fontSize: "0.85rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            background: "var(--bg)",
            color: "var(--text)",
          }}
        />
        <select
          value={targetType}
          onChange={(e) => setTargetType(e.target.value as MappingTargetType)}
          style={{
            padding: "0.3rem 0.5rem",
            fontSize: "0.85rem",
            border: "1px solid var(--border)",
            borderRadius: "4px",
            background: "var(--bg)",
            color: "var(--text)",
          }}
        >
          {TARGET_TYPES.map((t) => (
            <option key={t} value={t}>
              {TARGET_TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        {targetType !== "organization" && (
          <input
            value={targetId}
            onChange={(e) => {
              setTargetId(e.target.value);
              setLinkError(null);
            }}
            placeholder={`${TARGET_TYPE_LABEL[targetType]} id`}
            style={{
              width: "140px",
              padding: "0.3rem 0.5rem",
              fontSize: "0.85rem",
              border: "1px solid var(--border)",
              borderRadius: "4px",
              background: "var(--bg)",
              color: "var(--text)",
            }}
          />
        )}
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
