import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { WRITE_EVENT, type WriteEventDetail } from "../api/client";

/**
 * One confirmation for every saved change (ADP-blp.48): a brief "Saved" or "Removed" at the bottom
 * of the screen, raised by the API client whenever a write succeeds. It covers the controls that
 * save as soon as a value is chosen, which previously gave no sign that anything had happened.
 * Announced politely to screen readers; several writes in quick succession show one message.
 */
const VISIBLE_MS = 2200;

export function Toaster(): React.ReactElement | null {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onWrite(event: Event) {
      const { kind } = (event as CustomEvent<WriteEventDetail>).detail;
      setMessage(kind === "removed" ? "Removed" : "Saved");
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setMessage(null), VISIBLE_MS);
    }
    window.addEventListener(WRITE_EVENT, onWrite);
    return () => {
      window.removeEventListener(WRITE_EVENT, onWrite);
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  return createPortal(
    <div className="ui-toaster" role="status" aria-live="polite">
      {message && <div className="ui-toast">✓ {message}</div>}
    </div>,
    document.body,
  );
}

export default Toaster;
