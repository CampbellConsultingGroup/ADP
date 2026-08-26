import { useState } from "react";
import { ApiError } from "../api/client";
import {
  useRubricHistory,
  useRestoreRubricVersion,
  type RubricView,
  type RubricHistoryEntry,
} from "../api/adminRubrics";

interface RubricHistoryProps {
  rubric: RubricView;
}

function formatWeights(weights: Record<string, number>, labels: Record<string, string>): string {
  return Object.entries(weights)
    .map(([dim, w]) => `${labels[dim] ?? dim}: ${Math.round(w * 100)}%`)
    .join("\n");
}

export default function RubricHistory({ rubric }: RubricHistoryProps): React.ReactElement {
  const { data, isLoading } = useRubricHistory(rubric.rubric_id);
  const [pendingRestore, setPendingRestore] = useState<RubricHistoryEntry | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const restore = useRestoreRubricVersion(rubric.rubric_id);

  const items = data?.items ?? [];

  const handleConfirmRestore = () => {
    if (!pendingRestore) return;
    setErrorMessage(null);
    restore.mutate(
      {
        historyId: pendingRestore.id,
        expectedVersion: rubric.version,
        confirmationId: `CONFIRM-${rubric.rubric_id}-restore-${pendingRestore.id}`,
      },
      {
        onSuccess: () => setPendingRestore(null),
        onError: (err) => {
          setPendingRestore(null);
          if (err instanceof ApiError && err.status === 409) {
            setErrorMessage(
              "This rubric's weights changed since the page loaded. Reload the page and try again.",
            );
          } else {
            setErrorMessage("Failed to restore. Please try again.");
          }
        },
      },
    );
  };

  if (isLoading) {
    return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading history…</div>;
  }
  if (items.length === 0) {
    return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No changes recorded yet.</div>;
  }

  return (
    <div>
      {errorMessage && (
        <div role="alert" style={{ marginBottom: 12, color: "var(--danger, #b91c1c)", fontSize: 13 }}>
          {errorMessage}
        </div>
      )}
      {items.map((entry) => (
        <div
          key={entry.id}
          style={{
            border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 8,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>
              {entry.change_type === "restore" ? "Restored" : "Edited"} by {entry.actor}
            </span>
            <span style={{ fontSize: 11, color: "var(--ink-3)" }}>
              {new Date(entry.changed_at).toLocaleString()}
            </span>
          </div>
          <pre
            style={{
              whiteSpace: "pre-wrap", fontSize: 12, background: "var(--surface-2, #f8f8f8)",
              borderRadius: 6, padding: 8, margin: "0 0 8px", maxHeight: 160, overflow: "auto",
            }}
          >
            {formatWeights(entry.new_weights, rubric.dimension_labels)}
          </pre>
          <button
            onClick={() => setPendingRestore(entry)}
            style={{ fontSize: 12, padding: "4px 10px", cursor: "pointer" }}
          >
            Restore this version
          </button>
        </div>
      ))}

      {pendingRestore && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}
        >
          <div style={{ background: "var(--surface)", borderRadius: 8, padding: 24, maxWidth: 480, width: "90%" }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 700 }}>Confirm restore</h3>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-3)" }}>
              This changes <strong>{rubric.display_name}</strong>'s live scoring for every future assessment
              computed platform-wide, starting immediately — the same as a manual edit. This action is
              attributed to you and recorded as a new history entry.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                onClick={() => setPendingRestore(null)}
                disabled={restore.isPending}
                style={{ padding: "8px 18px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmRestore}
                disabled={restore.isPending}
                style={{ padding: "8px 18px", background: "var(--ent, #2874A6)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
              >
                {restore.isPending ? "Restoring..." : "Confirm & Restore"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
