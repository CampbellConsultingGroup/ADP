// ADP-q3j / ADP-a8s: one consistent frame for the Strategy screens' inline edit forms
// (theme, objective, initiative). Before this, each form ended in two unstyled browser-default
// buttons with no heading and no way back at the top, so users couldn't find Save/Cancel or a
// way out. The frame gives every edit form:
//   - a top "<- Back to ..." control and a heading naming the item being edited
//   - a sticky action bar (primary Save, Cancel) that stays visible while scrolling the form
//   - Escape to cancel, and a confirm before discarding unsaved field changes
//   - focus moved to the heading on open (callers return focus to their Edit button on close)
// Content outside the form (link editors that save immediately) goes in `after`.

import { useEffect, useId, useRef, useState } from "react";
import type React from "react";
import { Button } from "../ui";

export const DISCARD_PROMPT = "Discard your unsaved changes?";

interface EditFrameProps {
  /** e.g. "Edit initiative" */
  title: string;
  /** The item's current name/statement, shown after the title. */
  subject: string;
  /** e.g. "Back to initiatives" */
  backLabel: string;
  /** True when a field differs from the saved value; Back/Cancel/Escape then ask first. */
  dirty: boolean;
  saving: boolean;
  /** Disables Save (e.g. a required field is empty). */
  saveDisabled?: boolean;
  onSubmit: (e: React.FormEvent) => void;
  /** Leave without saving the form fields. */
  onClose: () => void;
  /** Validation or server error for the form fields. */
  error?: string | null;
  children: React.ReactNode;
  /** Rendered below the form, e.g. link editors that save immediately. */
  after?: React.ReactNode;
}

export default function EditFrame({
  title,
  subject,
  backLabel,
  dirty,
  saving,
  saveDisabled = false,
  onSubmit,
  onClose,
  error,
  children,
  after,
}: EditFrameProps): React.ReactElement {
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  function requestClose() {
    if (dirty && !confirm(DISCARD_PROMPT)) return;
    onClose();
  }

  return (
    <div
      role="presentation"
      onKeyDown={(e) => {
        if (e.key === "Escape" && !e.defaultPrevented) {
          e.preventDefault();
          requestClose();
        }
      }}
      style={{ border: "1px solid var(--accent)", borderRadius: 8, padding: 12, marginBottom: 8, background: "var(--surface)" }}
    >
      <button
        type="button"
        onClick={requestClose}
        style={{ marginBottom: 8, padding: 0, background: "none", border: "none", cursor: "pointer", color: "var(--ink-3)", fontSize: 13 }}
      >
        ← {backLabel}
      </button>
      <h3
        id={headingId}
        ref={headingRef}
        tabIndex={-1}
        style={{ margin: "0 0 12px", fontSize: 15, color: "var(--ink)", outline: "none" }}
      >
        {title}: <span style={{ fontWeight: 400 }}>{subject}</span>
      </h3>
      <form onSubmit={onSubmit} aria-labelledby={headingId}>
        {children}
        {error && (
          <div role="alert" className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
            {error}
          </div>
        )}
        <div
          style={{
            position: "sticky",
            bottom: 0,
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginTop: 12,
            padding: "8px 0",
            background: "var(--surface)",
            borderTop: "1px solid var(--border)",
          }}
        >
          <Button type="submit" variant="primary" size="sm" disabled={saving || saveDisabled}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button type="button" size="sm" onClick={requestClose}>
            Cancel
          </Button>
          {dirty && <span style={{ fontSize: 12, color: "var(--ink-3)" }}>Unsaved changes</span>}
        </div>
      </form>
      {after}
    </div>
  );
}

/** After an inline edit closes, scroll the item's row into view and return focus to its Edit
 * button (marked with `data-edit-for={id}`). Call the returned function with the item's id. */
export function useReturnFocus(): (id: string) => void {
  const [target, setTarget] = useState<string | null>(null);
  useEffect(() => {
    if (!target) return;
    const el = document.querySelector<HTMLElement>(`[data-edit-for="${target}"]`);
    el?.scrollIntoView?.({ block: "nearest" });
    el?.focus();
    setTarget(null);
  }, [target]);
  return setTarget;
}
