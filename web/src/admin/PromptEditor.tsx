import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { useConfirmPromptEdit, type AgentPromptView } from "../api/adminPrompts";

interface ConflictState {
  currentActiveText: string;
  currentVersion: number;
}

interface PromptEditorProps {
  agent: AgentPromptView;
  onDirtyChange: (dirty: boolean) => void;
}

export default function PromptEditor({ agent, onDirtyChange }: PromptEditorProps): React.ReactElement {
  const [editedText, setEditedText] = useState(agent.active_text);
  const [baseVersion, setBaseVersion] = useState(agent.version);
  const [showConfirm, setShowConfirm] = useState(false);
  const [conflict, setConflict] = useState<ConflictState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const confirmEdit = useConfirmPromptEdit(agent.agent_id);

  // Reset local edit state whenever the selected agent (or its server state
  // after a successful save/restore) changes.
  useEffect(() => {
    setEditedText(agent.active_text);
    setBaseVersion(agent.version);
    setConflict(null);
    setErrorMessage(null);
  }, [agent.agent_id, agent.active_text, agent.version]);

  const isDirty = editedText !== agent.active_text;
  const isEmpty = editedText.trim() === "";

  useEffect(() => {
    onDirtyChange(isDirty);
  }, [isDirty, onDirtyChange]);

  // FR-011: warn before discarding unsaved edits on tab close/refresh.
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
    confirmEdit.mutate(
      {
        newText: editedText,
        expectedVersion: baseVersion,
        confirmationId: `CONFIRM-${agent.agent_id}-${new Date().toISOString()}`,
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
                detail?: { current_active_text?: string; current_version?: number };
              }
            )?.detail;
            if (detail?.current_active_text !== undefined && detail?.current_version !== undefined) {
              setConflict({
                currentActiveText: detail.current_active_text,
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
    setEditedText(conflict.currentActiveText);
    setBaseVersion(conflict.currentVersion);
    setConflict(null);
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
            This prompt changed since you loaded it
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

      <textarea
        value={editedText}
        onChange={(e) => setEditedText(e.target.value)}
        rows={16}
        style={{
          width: "100%", boxSizing: "border-box", fontFamily: "monospace", fontSize: 13,
          padding: 12, borderRadius: 8, border: "1px solid var(--border)", resize: "vertical",
        }}
      />

      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
        <button
          onClick={() => setShowConfirm(true)}
          disabled={!isDirty || isEmpty}
          style={{
            padding: "8px 18px", borderRadius: 4, border: "none", fontSize: 14, fontWeight: 600,
            cursor: !isDirty || isEmpty ? "not-allowed" : "pointer",
            background: !isDirty || isEmpty ? "var(--border)" : "var(--ent, #2874A6)",
            color: "#fff",
          }}
        >
          Save
        </button>
      </div>
      {isEmpty && isDirty && (
        <div style={{ color: "var(--danger, #b91c1c)", fontSize: 12, marginTop: 4, textAlign: "right" }}>
          Prompt cannot be empty.
        </div>
      )}

      {showConfirm && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}
        >
          <div style={{ background: "var(--surface)", borderRadius: 8, padding: 24, maxWidth: 480, width: "90%" }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 700 }}>Confirm prompt change</h3>
            <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--ink-3)" }}>
              This changes <strong>{agent.display_name}</strong>'s live AI behavior for every user of the
              platform, starting with its very next run. This action is attributed to you and recorded in
              this agent's history.
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
