import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../ui/Icon";
import ChatPanel from "./ChatPanel";

/**
 * "Ask AI" in the top bar: the chat assistant, reachable from every screen (ADP-blp.60).
 *
 * The assistant answers questions across the whole estate, but its only entry points were a
 * "Chat" button on the business capability tree and one in the diagram editor, so most users
 * never met it. This opens the same ChatPanel in a side drawer over whatever screen is showing.
 * Escape, the Close button or the top-bar button again closes it; the conversation is kept by
 * the server, so it can be picked up again from "Past conversations".
 */
export function AskAiLauncher(): React.ReactElement {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        className={`shell-askai${open ? " active" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        title="Ask the AI assistant a question about your architecture data"
      >
        <Icon name="spark" size={16} /> Ask AI
      </button>
      {open &&
        createPortal(
          <aside className="ui-drawer" aria-label="AI assistant">
            <div className="ui-drawer-head">
              <strong>AI assistant</strong>
              <span>Answers from your capabilities, applications, value streams and strategy.</span>
            </div>
            <div className="ui-drawer-body">
              <ChatPanel basePath="/api/v1/chat" onClose={() => setOpen(false)} />
            </div>
          </aside>,
          document.body,
        )}
    </>
  );
}

export default AskAiLauncher;
