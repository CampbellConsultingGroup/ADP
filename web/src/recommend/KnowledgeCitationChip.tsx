import React from "react";
import { useKnowledgeItem } from "../api/knowledge";

interface KnowledgeCitationChipProps {
  itemId: string;
}

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

export default function KnowledgeCitationChip({ itemId }: KnowledgeCitationChipProps): React.ReactElement {
  const { data: item, isLoading } = useKnowledgeItem(itemId);

  if (isLoading) {
    return (
      <span style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 8px",
        borderRadius: 4,
        background: "#F3F4F6",
        fontSize: 11,
        color: "#9CA3AF",
      }}>
        {itemId}
      </span>
    );
  }

  const kind = item?.kind ?? "principle";
  const colors = KIND_COLORS[kind] ?? { bg: "#F3F4F6", text: "#374151" };
  const kindLabel = KIND_LABELS[kind] ?? kind;

  return (
    <span
      title={item?.source_ref ?? itemId}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 8px",
        borderRadius: 4,
        background: colors.bg,
        fontSize: 11,
        fontWeight: 600,
        color: colors.text,
        cursor: "default",
      }}
    >
      <span style={{ opacity: 0.7 }}>{kindLabel}</span>
      <span>{item?.title ?? itemId}</span>
    </span>
  );
}
