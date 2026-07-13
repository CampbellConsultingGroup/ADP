import React, { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

interface ConflictNotificationProps {
  designId: string;
  onDismiss: () => void;
}

export function ConflictNotificationBanner({
  designId,
  onDismiss,
}: ConflictNotificationProps): React.ReactElement {
  const qc = useQueryClient();

  const handleReload = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["design", designId] });
    onDismiss();
  }, [qc, designId, onDismiss]);

  return (
    <div
      role="alert"
      style={{
        position: "fixed",
        top: 16,
        left: "50%",
        transform: "translateX(-50%)",
        background: "var(--crit)",
        color: "#fff",
        padding: "12px 24px",
        borderRadius: 6,
        display: "flex",
        gap: 12,
        alignItems: "center",
        zIndex: 9999,
      }}
    >
      <span>Design updated by another user. Your change was not saved.</span>
      <button onClick={handleReload} style={{ background: "var(--surface)", color: "var(--crit)", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}>
        Reload
      </button>
      <button onClick={onDismiss} style={{ background: "transparent", color: "#fff", border: "1px solid var(--surface)", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}>
        Dismiss
      </button>
    </div>
  );
}

// Singleton event bus — avoids requiring React context in mutation callbacks
type ConflictListener = (designId: string) => void;
const _listeners = new Set<ConflictListener>();

export function notifyConflict(designId: string): void {
  _listeners.forEach((fn) => fn(designId));
}

export function subscribeConflict(fn: ConflictListener): () => void {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}
