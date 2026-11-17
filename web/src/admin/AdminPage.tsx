import { useState } from "react";
import { useAgentPrompts } from "../api/adminPrompts";
import PromptEditor from "./PromptEditor";
import PromptHistory from "./PromptHistory";
import { clickableRow } from "../ui/clickableRow";
import { Tabs } from "../ui/Tabs";
import { confirmAction } from "../ui/confirm";

const CARD: React.CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "12px 16px",
  marginBottom: 8,
  cursor: "pointer",
  background: "var(--surface)",
};

const BADGE_DEFAULT: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 8px",
  borderRadius: 999,
  background: "var(--ink-3)",
  color: "var(--surface)",
};

const BADGE_CUSTOM: React.CSSProperties = {
  fontSize: 11,
  padding: "2px 8px",
  borderRadius: 999,
  background: "var(--ent)",
  color: "#fff",
};

export default function AdminPage(): React.ReactElement {
  const { data, isLoading, error } = useAgentPrompts();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [activeTab, setActiveTab] = useState<"edit" | "history">("edit");

  const items = data?.items ?? [];
  const selected = items.find((i) => i.agent_id === selectedId) ?? null;

  // FR-011: warn before discarding unsaved edits when switching agents
  // in-app (the browser-level beforeunload case is handled in PromptEditor).
  const trySelect = async (agentId: string) => {
    if (isDirty && agentId !== selectedId) {
      const proceed = await confirmAction(
        "You have unsaved changes to this agent's prompt. Discard them and switch agents?",
      );
      if (!proceed) return;
    }
    setSelectedId(agentId);
    setActiveTab("edit");
  };

  if (isLoading) {
    return <div style={{ padding: 24 }}>Loading agent prompts…</div>;
  }
  if (error) {
    return <div style={{ padding: 24, color: "var(--danger, #b91c1c)" }}>Failed to load agent prompts.</div>;
  }

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 320, borderRight: "1px solid var(--border)", overflow: "auto", padding: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>AI Agents</h2>
        {items.map((item) => (
          <div
            key={item.agent_id}
            style={{ ...CARD, outline: selectedId === item.agent_id ? "2px solid var(--ent)" : "none" }}
            {...clickableRow(() => trySelect(item.agent_id))}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontWeight: 500, fontSize: 13 }}>{item.display_name}</span>
              <span style={item.is_override ? BADGE_CUSTOM : BADGE_DEFAULT}>
                {item.is_override ? "Custom" : "Default"}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
        {!selected && (
          <div style={{ color: "var(--ink-3)", fontSize: 14 }}>
            Select an agent to view and edit its current system prompt.
          </div>
        )}
        {selected && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>{selected.display_name}</h1>
              <span style={selected.is_override ? BADGE_CUSTOM : BADGE_DEFAULT}>
                {selected.is_override ? "Custom (saved override)" : "Default (built-in fallback)"}
              </span>
            </div>
            <Tabs
              label="Edit or history"
              tabs={[{ id: "edit", label: "Edit" }, { id: "history", label: "History" }]}
              active={activeTab}
              onChange={setActiveTab}
              style={{ marginBottom: 16 }}
            />
            {activeTab === "edit" && (
              <PromptEditor key={selected.agent_id} agent={selected} onDirtyChange={setIsDirty} />
            )}
            {activeTab === "history" && <PromptHistory key={selected.agent_id} agent={selected} />}
          </div>
        )}
      </div>
    </div>
  );
}
