import React, { useState } from "react";
import type { KnowledgeItemSummary } from "../api/knowledge";
import { useDeleteKnowledgeItem } from "../api/knowledge";
import DeleteConfirmDialog from "./DeleteConfirmDialog";

const KIND_COLORS: Record<string, { bg: string; text: string }> = {
  principle: { bg: "#EDE9FE", text: "#5B21B6" },
  pattern: { bg: "#DBEAFE", text: "#1E40AF" },
  standard: { bg: "#D1FAE5", text: "#065F46" },
  reference_architecture: { bg: "#FEF3C7", text: "#92400E" },
  prior_solution: { bg: "#FCE7F3", text: "#9D174D" },
};

const KIND_LABELS: Record<string, string> = {
  principle: "Principle",
  pattern: "Pattern",
  standard: "Standard",
  reference_architecture: "Ref. Arch",
  prior_solution: "Prior Solution",
};

interface KnowledgeItemRowProps {
  item: KnowledgeItemSummary;
  onEdit: (id: string) => void;
}

export default function KnowledgeItemRow({ item, onEdit }: KnowledgeItemRowProps): React.ReactElement {
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const deleteItem = useDeleteKnowledgeItem();

  const kindStyle = KIND_COLORS[item.kind] ?? { bg: "#F3F4F6", text: "#374151" };

  return (
    <>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 14px",
        borderBottom: "1px solid #F3F4F6",
        background: "#fff",
      }}>
        <span style={{
          background: kindStyle.bg,
          color: kindStyle.text,
          fontSize: 11,
          fontWeight: 700,
          padding: "2px 8px",
          borderRadius: 4,
          flexShrink: 0,
          minWidth: 80,
          textAlign: "center",
        }}>
          {KIND_LABELS[item.kind] ?? item.kind}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#111827", marginBottom: 2 }}>
            {item.title}
          </div>
          <a
            href={item.source_ref}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: "#6B7280", textDecoration: "none", wordBreak: "break-all" }}
            onClick={(e) => e.stopPropagation()}
          >
            {item.source_ref}
          </a>
        </div>

        <span style={{ fontSize: 11, color: "#9CA3AF", flexShrink: 0 }}>{item.id}</span>

        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button
            onClick={() => onEdit(item.id)}
            style={{ padding: "4px 12px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 13 }}
          >
            Edit
          </button>
          <button
            onClick={() => setShowDeleteDialog(true)}
            style={{ padding: "4px 12px", background: "#fff", color: "#991B1B", border: "1px solid #FCA5A5", borderRadius: 4, cursor: "pointer", fontSize: 13 }}
          >
            Delete
          </button>
        </div>
      </div>

      {showDeleteDialog && (
        <DeleteConfirmDialog
          itemTitle={item.title}
          onConfirm={() => deleteItem.mutate(item.id, { onSuccess: () => setShowDeleteDialog(false) })}
          onCancel={() => setShowDeleteDialog(false)}
          isPending={deleteItem.isPending}
        />
      )}
    </>
  );
}
