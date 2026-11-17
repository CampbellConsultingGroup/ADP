import React, { useEffect, useRef } from "react";

/**
 * The backdrop for a modal dialog, with the behaviour a dialog needs (ADP-blp.40): it is announced
 * as a dialog, Escape closes it, focus moves into it when it opens and returns to where it was
 * when it closes, and Tab stays inside it.
 *
 * Eight dialogs each drew their own `position: fixed` backdrop as a plain div, so a screen reader
 * was not told a dialog had opened and the keyboard could neither close it nor stay within it.
 * Put the dialog's panel inside as children.
 */
interface ModalOverlayProps {
  /** Accessible name, normally the dialog's title. */
  label: string;
  /** Called on Escape. Omit to make Escape do nothing (for example while a save is running). */
  onClose?: () => void;
  style?: React.CSSProperties;
  children: React.ReactNode;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function ModalOverlay({ label, onClose, style, children }: ModalOverlayProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const node = ref.current;
    // Leave focus alone if a control inside already took it (autoFocus).
    if (node && !node.contains(document.activeElement)) node.focus();
    return () => previous?.focus?.();
  }, []);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && onClose) {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !ref.current) return;
    const items = Array.from(ref.current.querySelectorAll<HTMLElement>(FOCUSABLE));
    if (items.length === 0) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === ref.current)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    // The dialog itself handles Escape and keeps Tab inside it: that is what makes it modal.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-label={label}
      tabIndex={-1}
      onKeyDown={onKeyDown}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        outline: "none",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export default ModalOverlay;
