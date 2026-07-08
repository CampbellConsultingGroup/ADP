import React, { useState, useEffect, useRef } from "react";
import { usePortfolioSearch } from "../api/portfolio";

const LIFECYCLE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  draft:          { bg: "#F3F4F6", text: "#374151", label: "Draft" },
  proposed:       { bg: "#DBEAFE", text: "#1E40AF", label: "Proposed" },
  current:        { bg: "#D1FAE5", text: "#065F46", label: "Current" },
  deprecated:     { bg: "#FEF3C7", text: "#92400E", label: "Deprecated" },
  decommissioned: { bg: "#FEE2E2", text: "#991B1B", label: "Decommissioned" },
};

interface DependencySearchProps {
  onSelectDesign: (id: string) => void;
}

export default function DependencySearch({
  onSelectDesign,
}: DependencySearchProps): React.ReactElement {
  const [inputValue, setInputValue] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebouncedQ(inputValue), 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [inputValue]);

  const { data, isLoading } = usePortfolioSearch(debouncedQ, debouncedQ.length >= 2);

  const results = data?.designs ?? [];

  return (
    <div>
      {/* Search input */}
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Search elements and technologies…"
          style={{
            flex: 1,
            padding: "8px 12px",
            borderRadius: 8,
            border: "1px solid #D1D5DB",
            fontSize: 14,
          }}
          aria-label="Search portfolio elements"
        />
        {inputValue && (
          <button
            onClick={() => {
              setInputValue("");
              setDebouncedQ("");
            }}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "1px solid #D1D5DB",
              backgroundColor: "#fff",
              cursor: "pointer",
              fontSize: 13,
              color: "#374151",
            }}
          >
            Clear
          </button>
        )}
      </div>

      {/* Hint */}
      {inputValue.length > 0 && inputValue.length < 2 && (
        <p style={{ color: "#6B7280", fontSize: 13 }}>Type at least 2 characters to search.</p>
      )}

      {/* Loading */}
      {isLoading && debouncedQ.length >= 2 && (
        <p style={{ color: "#6B7280", fontSize: 13 }}>Searching…</p>
      )}

      {/* Results */}
      {!isLoading && debouncedQ.length >= 2 && results.length === 0 && (
        <p style={{ color: "#6B7280", fontSize: 13 }}>No matches found.</p>
      )}

      {results.map((r) => {
        const lc = LIFECYCLE_COLORS[r.lifecycle_status] ?? LIFECYCLE_COLORS.draft;
        return (
          <div
            key={r.id}
            style={{
              padding: "10px 12px",
              borderRadius: 8,
              border: "1px solid #E5E7EB",
              marginBottom: 8,
              backgroundColor: "#fff",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: 12,
                  backgroundColor: lc.bg,
                  color: lc.text,
                  fontSize: 12,
                  fontWeight: 600,
                }}
              >
                {lc.label}
              </span>
              <span style={{ fontSize: 14, fontWeight: 500, flex: 1, color: "#111827" }}>
                {r.title}
              </span>
              <button
                onClick={() => onSelectDesign(r.id)}
                style={{
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid #D1D5DB",
                  backgroundColor: "#fff",
                  fontSize: 12,
                  cursor: "pointer",
                  color: "#374151",
                }}
              >
                Open
              </button>
            </div>
            {r.matched_elements.map((m, i) => (
              <p key={i} style={{ margin: "2px 0 0 0", fontSize: 12, color: "#6B7280" }}>
                {m}
              </p>
            ))}
          </div>
        );
      })}
    </div>
  );
}
