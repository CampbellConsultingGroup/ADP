import { useEffect, useRef } from "react";
import { confirmAction } from "./confirm";

/**
 * Unsaved edits, known to the whole app (ADP-blp.63).
 *
 * Only the Strategy edit forms asked before discarding changes. Everywhere else, edits were
 * lost without a word when the user picked another tab or another screen, because the form is
 * unmounted. A form says it has unsaved edits with `useUnsavedChanges(dirty)`; the things that
 * take the user away (the nav rail, a tab bar, closing or reloading the page) ask first.
 *
 * Not covered: following a link to another entity, and the browser's Back button. Both change
 * the address directly, and that cannot be held up without a router.
 */
export const DISCARD_PROMPT = "Discard your unsaved changes?";

const dirtyForms = new Set<symbol>();

function onBeforeUnload(event: BeforeUnloadEvent): void {
  event.preventDefault();
  event.returnValue = ""; // older browsers need a value to show their own prompt
}

function sync(): void {
  if (dirtyForms.size > 0) window.addEventListener("beforeunload", onBeforeUnload);
  else window.removeEventListener("beforeunload", onBeforeUnload);
}

/** Register this form as having unsaved edits while `dirty` is true. */
export function useUnsavedChanges(dirty: boolean): void {
  const id = useRef(Symbol("form"));
  useEffect(() => {
    const key = id.current;
    if (dirty) dirtyForms.add(key);
    else dirtyForms.delete(key);
    sync();
    return () => {
      dirtyForms.delete(key);
      sync();
    };
  }, [dirty]);
}

export function hasUnsavedChanges(): boolean {
  return dirtyForms.size > 0;
}

/**
 * Run `leave` now when nothing is unsaved (so nothing changes for the common case), or after
 * the user agrees to discard their edits.
 */
export function leaveIfSafe(leave: () => void): void {
  if (!hasUnsavedChanges()) {
    leave();
    return;
  }
  void confirmAction(DISCARD_PROMPT).then((ok) => {
    if (ok) leave();
  });
}

/** For tests. */
export function resetUnsavedChanges(): void {
  dirtyForms.clear();
  sync();
}
