import { useState } from "react";
import {
  useCreateProgress,
  useUpdateProgress,
  type ObjectiveProgressEntry,
} from "../api/strategy";

interface ObjectiveProgressFormProps {
  objectiveId: string;
  /** Existing entries -- used to tell whether the chosen date is a new
   * record or a correction to one that already exists (FR-002a). */
  existingEntries: ObjectiveProgressEntry[];
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function ObjectiveProgressForm({
  objectiveId,
  existingEntries,
}: ObjectiveProgressFormProps) {
  const createMutation = useCreateProgress(objectiveId);
  const updateMutation = useUpdateProgress(objectiveId);

  const [asOfDate, setAsOfDate] = useState(todayIso());
  const [actualValue, setActualValue] = useState("");
  const [note, setNote] = useState("");

  const existing = existingEntries.find((e) => e.as_of_date === asOfDate);
  const isCorrection = !!existing;
  const pending = createMutation.isPending || updateMutation.isPending;
  const activeError = isCorrection ? updateMutation.error : createMutation.error;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!actualValue.trim()) return;
    const value = Number(actualValue);
    const trimmedNote = note.trim() || null;

    if (isCorrection) {
      updateMutation.mutate(
        { asOfDate, body: { actual_value: value, note: trimmedNote } },
        { onSuccess: () => setNote("") },
      );
    } else {
      createMutation.mutate(
        { as_of_date: asOfDate, actual_value: value, note: trimmedNote },
        {
          onSuccess: () => {
            setActualValue("");
            setNote("");
          },
        },
      );
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <label style={{ fontSize: 13, flex: 1 }}>
          Date
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 2 }}
          />
        </label>
        <label style={{ fontSize: 13, flex: 1 }}>
          Actual value
          <input
            type="number"
            value={actualValue}
            onChange={(e) => setActualValue(e.target.value)}
            placeholder={isCorrection ? String(existing.actual_value) : undefined}
            style={{ display: "block", width: "100%", marginTop: 2 }}
          />
        </label>
      </div>
      <label style={{ fontSize: 13 }}>
        Note (optional)
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          style={{ display: "block", width: "100%", marginTop: 2 }}
        />
      </label>
      {isCorrection && (
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>
          An entry for {asOfDate} already exists ({existing.actual_value}) — saving will correct
          it in place, not add a second entry.
        </div>
      )}
      <button type="submit" disabled={pending || !actualValue.trim()}>
        {pending ? "Saving…" : isCorrection ? "Save Correction" : "Record Progress"}
      </button>
      {activeError && (
        <div className="ui-alert crit" style={{ fontSize: 12 }}>
          {activeError.message}
        </div>
      )}
    </form>
  );
}
