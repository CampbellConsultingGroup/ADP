/** ControlMappingsEditor — create/update/remove a Control's mappings to the Capability,
 *  Application, Design, Pattern, or estate-wide obligation it governs (COMPLY-02).
 *
 *  One shared implementation reused everywhere a mapping is edited, mirroring
 *  useLinkFeedback's own extract-once-reuse-five-times precedent (ADP-c44) rather than a
 *  one-off per target type. Wired into ControlTree.tsx's per-control "Mappings" affordance. */

import { useState } from "react";
import type { ComplianceStatus, ControlMapping, MappingTargetType } from "../api/compliance";
import {
  useControlMappingInitiatives,
  useControlMappings,
  useDeleteMapping,
  useUpsertMapping,
} from "../api/compliance";

interface ControlMappingsEditorProps {
  controlId: string;
}

// Exported for reuse by web/src/strategy/InitiativeControlMappingEditor.tsx
// (925-strategy-compliance-linkage) -- same five target types / five statuses, one source of
// truth for their display labels/colors rather than a second copy drifting out of sync.
export const TARGET_TYPE_LABEL: Record<MappingTargetType, string> = {
  capability: "Capability",
  application: "Application",
  design: "Design",
  pattern: "Pattern",
  organization: "Estate-wide (organization)",
};

const STATUS_OPTIONS: ComplianceStatus[] = [
  "not_assessed", "compliant", "partial", "non_compliant", "not_applicable",
];

export const STATUS_LABEL: Record<ComplianceStatus, string> = {
  compliant: "Compliant",
  partial: "Partial",
  non_compliant: "Non-compliant",
  not_assessed: "Not assessed",
  not_applicable: "Not applicable",
};

export const STATUS_COLOR: Record<ComplianceStatus, string> = {
  compliant: "var(--good, #2e7d32)",
  partial: "var(--warn, #b26a00)",
  non_compliant: "var(--crit)",
  not_assessed: "var(--ink-3)",
  not_applicable: "var(--ink-3)",
};

export default function ControlMappingsEditor({ controlId }: ControlMappingsEditorProps) {
  const { data, isLoading } = useControlMappings(controlId);
  const [adding, setAdding] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const del = useDeleteMapping(controlId);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (isLoading) {
    return <p style={{ fontSize: 12, color: "var(--ink-3)" }}>Loading mappings…</p>;
  }

  const items = data?.items ?? [];

  function mappingKey(m: ControlMapping): string {
    return `${m.target_type}:${m.target_id ?? ""}`;
  }

  function handleDelete(m: ControlMapping) {
    if (!window.confirm(`Remove this ${TARGET_TYPE_LABEL[m.target_type]} mapping?`)) return;
    setDeleteError(null);
    del.mutate(
      { targetType: m.target_type, targetId: m.target_id },
      { onError: (err) => setDeleteError(err.message) },
    );
  }

  return (
    <div style={{ marginTop: 8 }}>
      {items.length === 0 && (
        <p style={{ fontSize: 12, color: "var(--ink-3)", margin: "0 0 8px" }}>
          No mappings yet.
        </p>
      )}
      {items.map((m) => {
        const key = mappingKey(m);
        if (editingKey === key) {
          return (
            <div
              key={key}
              style={{ border: "1px solid var(--border)", borderRadius: 6, padding: 10, marginBottom: 6 }}
            >
              <MappingForm
                controlId={controlId}
                targetType={m.target_type}
                targetId={m.target_id}
                initial={m}
                onDone={() => setEditingKey(null)}
              />
            </div>
          );
        }
        return (
          <div
            key={key}
            style={{
              display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8,
              padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 6,
              background: "var(--surface)", marginBottom: 6,
            }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--ink)" }}>
                {TARGET_TYPE_LABEL[m.target_type]}
                {m.target_id ? `: ${m.target_id}` : ""}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: STATUS_COLOR[m.compliance_status] }}>
                  {STATUS_LABEL[m.compliance_status]}
                </span>
                {m.evidence_ref && (
                  <span style={{ fontSize: 11, color: "var(--ink-3)" }}>evidence: {m.evidence_ref}</span>
                )}
                {m.assessed_by && (
                  <span style={{ fontSize: 11, color: "var(--ink-3)" }}>
                    by {m.assessed_by}{m.assessed_at ? ` (${m.assessed_at})` : ""}
                  </span>
                )}
              </div>
              <LinkedInitiatives controlId={controlId} targetType={m.target_type} targetId={m.target_id} />
            </div>
            <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
              <button onClick={() => setEditingKey(key)} style={{ fontSize: 11 }}>
                Edit
              </button>
              <button onClick={() => handleDelete(m)} disabled={del.isPending} style={{ fontSize: 11 }}>
                Remove
              </button>
            </div>
          </div>
        );
      })}
      {deleteError && (
        <div style={{ color: "var(--crit)", fontSize: 11, marginBottom: 6 }}>{deleteError}</div>
      )}

      {adding ? (
        <div style={{ border: "1px solid var(--border)", borderRadius: 6, padding: 10 }}>
          <MappingForm controlId={controlId} onDone={() => setAdding(false)} />
        </div>
      ) : (
        <button onClick={() => setAdding(true)} style={{ fontSize: 12 }}>
          + Add mapping
        </button>
      )}
    </div>
  );
}

/** Shared form for both "add a new mapping" (targetType/targetId undefined, editable) and
 *  "edit an existing mapping" (targetType/targetId fixed, not editable -- only
 *  status/evidence/assessed fields change, per spec.md US2). */
function MappingForm({
  controlId,
  targetType: fixedTargetType,
  targetId: fixedTargetId,
  initial,
  onDone,
}: {
  controlId: string;
  targetType?: MappingTargetType;
  targetId?: string | null;
  initial?: ControlMapping;
  onDone: () => void;
}) {
  const isEdit = fixedTargetType !== undefined;
  const [targetType, setTargetType] = useState<MappingTargetType>(fixedTargetType ?? "capability");
  const [targetId, setTargetId] = useState(fixedTargetId ?? "");
  const [status, setStatus] = useState<ComplianceStatus>(initial?.compliance_status ?? "not_assessed");
  const [evidenceRef, setEvidenceRef] = useState(initial?.evidence_ref ?? "");
  const [assessedAt, setAssessedAt] = useState(initial?.assessed_at ?? "");
  const [assessedBy, setAssessedBy] = useState(initial?.assessed_by ?? "");
  const [error, setError] = useState<string | null>(null);

  const upsert = useUpsertMapping(controlId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (targetType !== "organization" && !targetId.trim()) {
      setError(`A ${TARGET_TYPE_LABEL[targetType]} id is required`);
      return;
    }
    setError(null);
    upsert.mutate(
      {
        targetType,
        targetId: targetType === "organization" ? undefined : targetId.trim(),
        data: {
          compliance_status: status,
          evidence_ref: evidenceRef.trim() || null,
          assessed_at: assessedAt.trim() || null,
          assessed_by: assessedBy.trim() || null,
        },
      },
      {
        onSuccess: () => onDone(),
        onError: (err) => setError(err.message),
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {error && <div style={{ color: "var(--crit)", fontSize: 12 }}>{error}</div>}
      {!isEdit && (
        <>
          <label style={{ fontSize: 11, color: "var(--ink-3)" }}>
            Target type
            <select
              value={targetType}
              onChange={(e) => setTargetType(e.target.value as MappingTargetType)}
              style={{ fontSize: 13, display: "block", width: "100%", marginTop: 2 }}
            >
              {(Object.keys(TARGET_TYPE_LABEL) as MappingTargetType[]).map((t) => (
                <option key={t} value={t}>
                  {TARGET_TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
          {targetType !== "organization" && (
            <input
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder={`${TARGET_TYPE_LABEL[targetType]} id`}
              style={{ fontSize: 13 }}
            />
          )}
        </>
      )}
      <label style={{ fontSize: 11, color: "var(--ink-3)" }}>
        Compliance status
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as ComplianceStatus)}
          style={{ fontSize: 13, display: "block", width: "100%", marginTop: 2 }}
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>
      </label>
      <input
        value={evidenceRef}
        onChange={(e) => setEvidenceRef(e.target.value)}
        placeholder="Evidence reference (optional)"
        style={{ fontSize: 13 }}
      />
      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={assessedAt}
          onChange={(e) => setAssessedAt(e.target.value)}
          placeholder="Assessed at (YYYY-MM-DD)"
          style={{ fontSize: 12, flex: 1 }}
        />
        <input
          value={assessedBy}
          onChange={(e) => setAssessedBy(e.target.value)}
          placeholder="Assessed by"
          style={{ fontSize: 12, flex: 1 }}
        />
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="submit" disabled={upsert.isPending} style={{ fontSize: 12 }}>
          {upsert.isPending ? "Saving…" : isEdit ? "Save" : "Add"}
        </button>
        <button type="button" onClick={onDone} style={{ fontSize: 12 }}>
          Cancel
        </button>
      </div>
    </form>
  );
}

/** Read-only "Linked Initiatives" line for one mapping row (925-strategy-compliance-linkage,
 *  COMPLY-05 spec.md FR-007 reverse direction) -- hidden entirely when nothing is linked, or when
 *  the caller lacks READ_APPLICATION_GOVERNANCE for an Application-targeted mapping (403 renders
 *  as "no data" the same way an empty result would, no error surfaced for a expected-denial). */
function LinkedInitiatives({
  controlId,
  targetType,
  targetId,
}: {
  controlId: string;
  targetType: MappingTargetType;
  targetId: string | null;
}) {
  const { data } = useControlMappingInitiatives(controlId, targetType, targetId);
  const items = data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
      Remediation: {items.map((i) => i.name).join(", ")}
    </div>
  );
}
