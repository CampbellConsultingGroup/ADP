import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ModalOverlay } from "./ModalOverlay";

/**
 * One confirmation dialog for the whole app (ADP-blp.47).
 *
 * Nineteen places asked "are you sure?" with the browser's own `confirm()` box: unstyled, outside
 * the theme, and worded differently each time, while the diagram editor had a dialog of its own.
 * `confirmAction()` returns a promise for the answer, so a handler only changes from
 *
 *   if (!confirm(message)) return;          to          if (!(await confirmAction(message))) return;
 *
 * The dialog is drawn by <ConfirmHost />, mounted once in the app shell. Where no host is mounted
 * (a component rendered on its own, as in tests) it falls back to the browser's `confirm()`.
 */
export interface ConfirmOptions {
  /** The confirm button's text. Default: taken from the message ("Delete", "Remove"), else "Continue". */
  confirmLabel?: string;
  /** Style the confirm button as destructive. Default: true for Delete / Remove / Discard. */
  danger?: boolean;
}

interface Request {
  message: string;
  options: ConfirmOptions;
  resolve: (answer: boolean) => void;
}

let present: ((request: Request) => void) | null = null;

export function confirmAction(message: string, options: ConfirmOptions = {}): Promise<boolean> {
  if (present === null) return Promise.resolve(window.confirm(message));
  return new Promise<boolean>((resolve) => present!({ message, options, resolve }));
}

function defaultLabel(message: string): string {
  const first = message.trim().split(/\s+/)[0]?.toLowerCase() ?? "";
  if (first === "delete") return "Delete";
  if (first === "remove") return "Remove";
  if (first === "discard") return "Discard";
  return "Continue";
}

export function ConfirmHost(): React.ReactElement | null {
  const [request, setRequest] = useState<Request | null>(null);

  useEffect(() => {
    present = (next) => setRequest(next);
    return () => {
      present = null;
    };
  }, []);

  if (request === null) return null;

  const label = request.options.confirmLabel ?? defaultLabel(request.message);
  const danger = request.options.danger ?? label !== "Continue";
  const answer = (value: boolean) => {
    request.resolve(value);
    setRequest(null);
  };

  return createPortal(
    <ModalOverlay label="Confirm" onClose={() => answer(false)}>
      <div className="ui-confirm">
        <p>{request.message}</p>
        <div className="ui-confirm-actions">
          <button type="button" className="ui-btn" onClick={() => answer(false)}>
            Cancel
          </button>
          <button
            type="button"
            className={`ui-btn ${danger ? "ui-btn-danger" : "ui-btn-primary"}`}
            // The safe choice is the default: Enter on a just-opened dialog must not delete.
            onClick={() => answer(true)}
          >
            {label}
          </button>
        </div>
      </div>
    </ModalOverlay>,
    document.body,
  );
}
