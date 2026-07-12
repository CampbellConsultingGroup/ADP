import React from "react";
import { useKnowledgeItem } from "../api/knowledge";

interface KnowledgeCitationChipProps {
  itemId: string;
}

const KIND_COLORS: Record<string, { bg: string; text: string }> = {
  principle: { bg: "var(--biz-wash)", text: "var(--biz)" },
  pattern: { bg: "var(--accent-wash)", text: "var(--accent-2)" },
  standard: { bg: "var(--good-wash)", text: "var(--good)" },
  reference_architecture: { bg: "var(--warn-wash)", text: "var(--warn)" },
  prior_solution: { bg: "var(--surface-2)", text: "var(--biz)" },
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
        background: "var(--surface-2)",
        fontSize: 11,
        color: "var(--ink-3)",
      }}>
        {itemId}
      </span>
    );
  }

  const kind = item?.kind ?? "principle";
  const colors = KIND_COLORS[kind] ?? { bg: "var(--surface-2)", text: "var(--ink-2)" };
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
