import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { useConfirmRubricEdit, type RubricView } from "../api/adminRubrics";

interface ConflictState {
  currentActiveWeights: Record<string, number>;
  currentVersion: number;
}

interface RubricEditorProps {
  rubric: RubricView;
  onDirtyChange: (dirty: boolean) => void;
}

const SUM_TOLERANCE = 0.01; // percent, matches the backend's 1e-6 fraction tolerance loosely

/** Weights are edited as whole-number percentages (25, 25, 15, ...) for human
 * legibility -- research.md's presentation choice -- converted to/from the
 * underlying 0.0-1.0 fractions the API actually stores. */
function toPercent(weights: Record<string, number>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(weights).map(([dim, w]) => [dim, String(Math.round(w * 100))]),
  );
}

export default function RubricEditor({ rubric, onDirtyChange }: RubricEditorProps): React.ReactElement {
  const dimensionKeys = useMemo(() => Object.keys(rubric.dimension_labels), [rubric.dimension_labels]);
  const [percentValues, setPercentValues] = useState<Record<string, string>>(() =>
    toPercent(rubric.active_weights),
  );
  const [baseVersion, setBaseVersion] = useState(rubric.version);
  const [showConfirm, setShowConfirm] = useState(false);
  const [conflict, setConflict] = useState<ConflictState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const confirmEdit = useConfirmRubricEdit(rubric.rubric_id);

  useEffect(() => {
    setPercentValues(toPercent(rubric.active_weights));
    setBaseVersion(rubric.version);
    setConflict(null);
    setErrorMessage(null);
  }, [rubric.rubric_id, rubric.active_weights, rubric.version]);

  const sum = dimensionKeys.reduce((acc, dim) => acc + (Number(percentValues[dim]) || 0), 0);
  const sumValid = Math.abs(sum - 100) <= SUM_TOLERANCE;

  const originalPercents = toPercent(rubric.active_weights);
  const isDirty = dimensionKeys.some((dim) => percentValues[dim] !== originalPercents[dim]);

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const handleConfirm = () => {
    setErrorMessage(null);
    const weights = Object.fromEntries(
      dimensionKeys.map((dim) => [dim, (Number(percentValues[dim]) || 0) / 100]),
    );
    confirmEdit.mutate(
      {
        weights,
        expectedVersion: baseVersion,
        confirmationId: `CONFIRM-${rubric.rubric_id}-${new Date().toISOString()}`,
      },
      {
        onSuccess: () => {
          setShowConfirm(false);
          setConflict(null);
        },
        onError: (err) => {
          setShowConfirm(false);
          if (err instanceof ApiError && err.status === 409) {
            const detail = (
              err.body as {
                detail?: { current_active_weights?: Record<string, number>; current_version?: number };
              }
            )?.detail;
            if (detail?.current_active_weights !== undefined && detail?.current_version !== undefined) {
              setConflict({
                currentActiveWeights: detail.current_active_weights,
                currentVersion: detail.current_version,
              });
              return;
            }
          }
          setErrorMessage("Failed to save. Please try again.");
        },
      },
    );
  };

  const handleReloadLatest = () => {
    if (!conflict) return;
    setPercentValues(toPercent(conflict.currentActiveWeights));
    setBaseVersion(conflict.currentVersion);
    setConflict(null);
  };

  const field: React.CSSProperties = {
    width: 90, padding: "6px 8px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4,
  };

  return (
    <div>
      {conflict && (
        <div
          role="alert"
          style={{
            marginBottom: 12, padding: 12, borderRadius: 6,
            background: "var(--warn-wash, #fff7ed)", border: "1px solid var(--warn, #c2410c)",
          }}
        >
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
            This rubric's weights changed since you loaded them
          </div>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            Someone else saved a newer version. Your edit was NOT applied.
          </div>
          <button onClick={handleReloadLatest} style={{ fontSize: 13, padding: "4px 10px", cursor: "pointer" }}>
            Load latest version
          </button>
        </div>
      )}
      {errorMessage && (
        <div role="alert" style={{ marginBottom: 12, color: "var(--danger, #b91c1c)", fontSize: 13 }}>
          {errorMessage}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {dimensionKeys.map((dim) => (
          <label key={dim} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13 }}>
            <span>{rubric.dimension_labels[dim]}</span>
            <span>
              <input
                type="number"
                min={0}
                max={100}
                style={field}
                value={percentValues[dim] ?? ""}
                onChange={(e) => setPercentValues((prev) => ({ ...prev, [dim]: e.target.value }))}
              />
              <span style={{ marginLeft: 4 }}>%</span>
            </span>
          </label>
        ))}
      </div>

      <div
        style={{
          display: "flex", justifyContent: "space-between", marginTop: 12, paddingTop: 8,
          borderTop: "1px solid var(--border)", fontSize: 13, fontWeight: 600,
          color: sumValid ? "var(--ink)" : "var(--danger, #b91c1c)",
        }}
      >
        <span>Total</span>
        <span>{sum}%</span>
      </div>
      {!sumValid && (
        <div style={{ color: "var(--danger, #b91c1c)", fontSize: 12, marginTop: 4 }}>
          Weights must sum to 100% (currently {sum}%).
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
        <button
          onClick={() => setShowConfirm(true)}
          disabled={!isDirty || !sumValid}
          style={{
            padding: "8px 18px", borderRadius: 4, border: "none", fontSize: 14, fontWeight: 600,
            cursor: !isDirty || !sumValid ? "not-allowed" : "pointer",
            background: !isDirty || !sumValid ? "var(--border)" : "var(--ent, #2874A6)",
            color: "#fff",
          }}
        >
          Save
        </button>
      </div>

      {showConfirm && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}
        >
          <div style={{ background: "var(--surface)", borderRadius: 8, padding: 24, maxWidth: 480, width: "90%" }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 700 }}>Confirm weight change</h3>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-3)" }}>
              This changes <strong>{rubric.display_name}</strong>'s live scoring for every future assessment
              computed platform-wide, starting immediately. This action is attributed to you and recorded in
              this rubric's history.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                onClick={() => setShowConfirm(false)}
                disabled={confirmEdit.isPending}
                style={{ padding: "8px 18px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={confirmEdit.isPending}
                style={{ padding: "8px 18px", background: "var(--ent, #2874A6)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
              >
                {confirmEdit.isPending ? "Saving..." : "Confirm & Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
