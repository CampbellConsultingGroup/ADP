import React from "react";

/** Generic page-level chat toggle (ADP-SPEC-041), mirroring the "Review"/
 * "Review Portfolio" toggle pattern already established for Agent Review --
 * a plain on/off affordance; the actual conversation UI lives in ChatPanel,
 * rendered by the consuming page only while this toggle is on.
 */

interface Props {
  active: boolean;
  onToggle: () => void;
  label?: string;
}

export default function ChatButton({ active, onToggle, label = "Chat" }: Props): React.ReactElement {
  return (
    <button
      onClick={onToggle}
      title="Ask a question about this data"
      style={{
        padding: "6px 14px", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600,
        background: active ? "var(--accent-wash)" : "var(--surface)",
        color: active ? "var(--accent-2)" : "var(--ink-2)",
        border: "1px solid var(--border)",
      }}
    >
      {label}
    </button>
  );
}
