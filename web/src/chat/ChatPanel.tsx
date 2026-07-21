import React, { useState } from "react";
import {
  useConversation,
  useConversations,
  useCreateConversation,
  useSendMessage,
} from "../api/chat";
import type { ChatMessage } from "../api/chat";

/** Generic conversation panel (ADP-SPEC-041): message list, input box,
 * incremental streamed-text rendering, and a list of past conversations to
 * resume (US3). Parameterized by basePath only -- no adapter-specific
 * wiring lives here, mirroring SuggestionCard/AgentReviewButton's split.
 */

interface Props {
  basePath: string;
  /** Explicit dismiss for the whole panel, distinct from any toggle the
   * consuming screen uses to show/hide it -- mirrors InspectionPanel's
   * onClose convention. Optional so ChatPanel can still be embedded without
   * a close affordance if a screen manages visibility some other way. */
  onClose?: () => void;
}

export default function ChatPanel({ basePath, onClose }: Props): React.ReactElement {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [input, setInput] = useState("");

  const create = useCreateConversation(basePath);
  const { data: conversation } = useConversation(basePath, conversationId);
  const { data: pastConversations } = useConversations(basePath, showHistory);
  const { sendMessage, isStreaming, streamedText, error } = useSendMessage(basePath);

  async function handleSend() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");

    let targetId = conversationId;
    if (!targetId) {
      const conv = await create.mutateAsync();
      targetId = conv.id;
      setConversationId(conv.id);
    }
    await sendMessage(targetId, text);
  }

  const messages: ChatMessage[] = conversation?.messages ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <button
          onClick={() => setShowHistory(!showHistory)}
          style={{ ...linkBtn, color: showHistory ? "var(--accent-2)" : "var(--ink-3)" }}
        >
          Past conversations
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {conversationId && (
            <button
              onClick={() => { setConversationId(null); setInput(""); }}
              style={linkBtn}
            >
              New conversation
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              title="Close"
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "var(--ink-3)", padding: 0, lineHeight: 1 }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {showHistory && (
        <div style={{ marginBottom: 8, padding: "6px 10px", background: "var(--surface-2)", borderRadius: 4 }}>
          {(pastConversations ?? []).length === 0 && (
            <div style={{ fontSize: 12, color: "var(--ink-3)" }}>No past conversations.</div>
          )}
          {(pastConversations ?? []).map((c) => (
            <button
              key={c.id}
              onClick={() => { setConversationId(c.id); setShowHistory(false); }}
              style={{ ...linkBtn, display: "block", width: "100%", textAlign: "left", padding: "4px 0" }}
            >
              {c.title}
            </button>
          ))}
        </div>
      )}

      <div style={{ maxHeight: 320, overflowY: "auto", marginBottom: 8 }}>
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {isStreaming && streamedText && (
          <div style={bubbleStyle("assistant")}>{streamedText}</div>
        )}
      </div>

      {error && (
        <div className="ui-alert crit" style={{ marginBottom: 8 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void handleSend(); }}
          placeholder="Ask a question…"
          disabled={isStreaming}
          style={{ flex: 1, padding: "6px 10px", fontSize: 13, border: "1px solid var(--border)", borderRadius: 4 }}
        />
        <button
          onClick={() => void handleSend()}
          disabled={isStreaming || !input.trim()}
          style={{
            padding: "6px 14px", fontSize: 13, borderRadius: 4, border: "none", color: "#fff",
            background: isStreaming || !input.trim() ? "var(--border)" : "var(--accent)",
            cursor: isStreaming || !input.trim() ? "not-allowed" : "pointer",
          }}
        >
          {isStreaming ? "Thinking…" : "Send"}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }): React.ReactElement {
  return (
    <div style={bubbleStyle(message.role)}>
      <div>{message.content}</div>
      {message.citations.length > 0 && (
        <div style={{ fontSize: 10, color: "var(--ink-3)", marginTop: 4 }}>
          {message.citations.map((c) => (
            <span key={`${c.entity_type}:${c.entity_id}`} style={{ marginRight: 6 }}>
              {c.entity_type}:{c.entity_id}{!c.verified && " (unverified)"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function bubbleStyle(role: string): React.CSSProperties {
  return {
    padding: "6px 10px",
    marginBottom: 6,
    borderRadius: 6,
    fontSize: 13,
    maxWidth: "85%",
    marginLeft: role === "user" ? "auto" : 0,
    background: role === "user" ? "var(--accent-wash)" : "var(--surface-2)",
    color: "var(--ink)",
  };
}

const linkBtn: React.CSSProperties = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  fontSize: 12,
  padding: 0,
};
