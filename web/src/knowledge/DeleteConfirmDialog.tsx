import React from "react";

interface DeleteConfirmDialogProps {
  itemTitle: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}

export default function DeleteConfirmDialog({
  itemTitle,
  onConfirm,
  onCancel,
  isPending,
}: DeleteConfirmDialogProps): React.ReactElement {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: "#fff", borderRadius: 8, padding: 24, maxWidth: 440, width: "90%", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 700 }}>Delete Knowledge Item</h3>
        <p style={{ margin: "0 0 20px", fontSize: 14, color: "#374151" }}>
          Are you sure you want to delete <strong>{itemTitle}</strong>? The item will be deactivated and will no longer appear in the knowledge base or influence recommendations.
        </p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button
            onClick={onCancel}
            disabled={isPending}
            style={{ padding: "8px 18px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isPending}
            style={{ padding: "8px 18px", background: isPending ? "#D1D5DB" : "#991B1B", color: "#fff", border: "none", borderRadius: 4, cursor: isPending ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
          >
            {isPending ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
