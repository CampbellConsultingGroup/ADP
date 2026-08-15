import React, { useEffect, useState } from "react";
import { Button } from "../ui";

/** Generic popup shared by HealthAssessmentModal.tsx and
 *  BusinessValueAssessmentModal.tsx (extracted per
 *  docs/application-business-value-assessment-spec.md §8/§9 -- both popups
 *  are the same table-of-radios/pre-fill/required-all-six/independent-save
 *  shape; only the rubric content, aggregation, and copy differ). Each
 *  thin wrapper calls its own domain-specific query/mutation hooks and
 *  passes the results in as props -- this component itself has no opinion
 *  about which assessment it's rendering. */

export interface AssessmentRubricRow {
  dimension: string;
  label: string;
  /** Exactly 5 entries, index 0 = score 1 ... index 4 = score 5. */
  options: string[];
}

export interface AssessmentEntry {
  dimension: string;
  score: number;
}

interface Props {
  title: string;
  description: string;
  /** Column headers above the 5 score options, e.g. "1 — Critical" .. "5 — Thriving". */
  scoreLabels: string[];
  rubric: AssessmentRubricRow[];
  /** Existing persisted answers, if any -- pre-fills radios on open. */
  entries: AssessmentEntry[] | undefined;
  isLoading: boolean;
  /** Called only once every dimension has a selection; produces the footer
   *  copy shown before Save (e.g. Health's "lowest of six" line, or
   *  Business Value's weighted-average + cap-math line). */
  resultText: (selections: Record<string, number>) => string;
  onSave: (selections: Record<string, number>) => void;
  saving: boolean;
  saveError: string | null;
  onClose: () => void;
}

export default function AssessmentModal({
  title,
  description,
  scoreLabels,
  rubric,
  entries,
  isLoading,
  resultText,
  onSave,
  saving,
  saveError,
  onClose,
}: Props): React.ReactElement {
  const [selections, setSelections] = useState<Record<string, number>>({});
  const [prefilled, setPrefilled] = useState(false);

  // Pre-fill from the last-saved assessment, once, when it arrives -- not
  // on every refetch, so a save in progress doesn't clobber the user's
  // still-unsaved edits.
  useEffect(() => {
    if (entries && !prefilled) {
      const initial: Record<string, number> = {};
      for (const entry of entries) initial[entry.dimension] = entry.score;
      setSelections(initial);
      setPrefilled(true);
    }
  }, [entries, prefilled]);

  const allAnswered = rubric.every((row) => selections[row.dimension] !== undefined);

  function handleSave() {
    if (!allAnswered) return;
    onSave(selections);
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "var(--surface)", borderRadius: 8, padding: 24,
          maxWidth: 1000, width: "94%", maxHeight: "90vh", overflowY: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        <h3 style={{ margin: "0 0 4px", fontSize: 17, fontWeight: 700 }}>{title}</h3>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-2)" }}>{description}</p>

        {isLoading ? (
          <div style={{ padding: 20, fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ ...cellStyle, textAlign: "left", minWidth: 160 }}>Dimension</th>
                  {scoreLabels.map((label) => (
                    <th key={label} style={{ ...cellStyle, minWidth: 150 }}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rubric.map((row) => (
                  <tr key={row.dimension}>
                    <td style={{ ...cellStyle, fontWeight: 600, textAlign: "left" }}>{row.label}</td>
                    {row.options.map((optionDescription, idx) => {
                      const score = idx + 1;
                      return (
                        <td key={score} style={cellStyle}>
                          <label style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: "pointer" }}>
                            <input
                              type="radio"
                              name={`assessment-${row.dimension}`}
                              checked={selections[row.dimension] === score}
                              onChange={() =>
                                setSelections((prev) => ({ ...prev, [row.dimension]: score }))
                              }
                            />
                            <span style={{ color: "var(--ink-3)" }}>{optionDescription}</span>
                          </label>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
          <div style={{ fontSize: 13, color: "var(--ink-2)" }}>
            {allAnswered
              ? resultText(selections)
              : "Select an option for every dimension to continue."}
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <Button onClick={onClose} disabled={saving}>Cancel</Button>
            <Button variant="primary" onClick={handleSave} disabled={!allAnswered || saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
        {saveError && (
          <div style={{ marginTop: 10, fontSize: 12, color: "var(--crit)" }}>{saveError}</div>
        )}
      </div>
    </div>
  );
}

const cellStyle: React.CSSProperties = {
  border: "1px solid var(--border)",
  padding: "8px 10px",
  textAlign: "center",
  verticalAlign: "top",
};
