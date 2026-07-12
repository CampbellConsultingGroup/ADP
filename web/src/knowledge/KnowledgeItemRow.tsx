import React, { useState } from "react";
import type { KnowledgeItemSummary } from "../api/knowledge";
import { useDeleteKnowledgeItem } from "../api/knowledge";
import { Button } from "../ui";
import DeleteConfirmDialog from "./DeleteConfirmDialog";

// Categorical wayfinding hues (theme-aware tokens), not status semantics.
const KIND_HUE: Record<string, { hue: string; wash: string }> = {
  principle: { hue: "var(--biz)", wash: "var(--biz-wash)" },
  pattern: { hue: "var(--ent)", wash: "var(--ent-wash)" },
  standard: { hue: "var(--sol)", wash: "var(--sol-wash)" },
  reference_architecture: { hue: "var(--tec)", wash: "var(--tec-wash)" },
  prior_solution: { hue: "var(--good)", wash: "var(--good-wash)" },
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

  const kind = KIND_HUE[item.kind] ?? { hue: "var(--ink-2)", wash: "var(--surface-2)" };

  return (
    <>
      <div className="ui-list-row">
        <span style={{
          background: kind.wash, color: kind.hue, fontSize: 11, fontWeight: 700,
          padding: "3px 9px", borderRadius: 6, flexShrink: 0, minWidth: 82, textAlign: "center",
          fontFamily: "var(--mono)",
        }}>
          {KIND_LABELS[item.kind] ?? item.kind}
        </span>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>{item.title}</div>
          <a
            href={item.source_ref}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: "var(--ink-3)", textDecoration: "none", wordBreak: "break-all" }}
            onClick={(e) => e.stopPropagation()}
          >
            {item.source_ref}
          </a>
        </div>

        <span style={{ fontSize: 11, color: "var(--ink-3)", flexShrink: 0, fontFamily: "var(--mono)" }}>{item.id}</span>

        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button size="sm" onClick={() => onEdit(item.id)}>Edit</Button>
          <Button size="sm" variant="danger" onClick={() => setShowDeleteDialog(true)}>Delete</Button>
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
