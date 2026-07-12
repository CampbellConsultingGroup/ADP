import React, { useState, useEffect, useRef } from "react";
import { usePortfolioSearch } from "../api/portfolio";
import { Button, StatusBadge } from "../ui";
import { LIFECYCLE_TONE, LIFECYCLE_LABEL } from "./lifecycle";

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
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <input
          type="text"
          className="ui-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Search elements and technologies…"
          aria-label="Search portfolio elements"
        />
        {inputValue && (
          <Button onClick={() => { setInputValue(""); setDebouncedQ(""); }}>Clear</Button>
        )}
      </div>

      {inputValue.length > 0 && inputValue.length < 2 && (
        <p style={{ color: "var(--ink-3)", fontSize: 13 }}>Type at least 2 characters to search.</p>
      )}
      {isLoading && debouncedQ.length >= 2 && <p style={{ color: "var(--ink-3)", fontSize: 13 }}>Searching…</p>}
      {!isLoading && debouncedQ.length >= 2 && results.length === 0 && (
        <p style={{ color: "var(--ink-3)", fontSize: 13 }}>No matches found.</p>
      )}

      {results.map((r) => (
        <div
          key={r.id}
          style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)", marginBottom: 8, background: "var(--surface)" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <StatusBadge tone={LIFECYCLE_TONE[r.lifecycle_status] ?? "neutral"}>
              {LIFECYCLE_LABEL[r.lifecycle_status] ?? r.lifecycle_status}
            </StatusBadge>
            <span style={{ fontSize: 14, fontWeight: 500, flex: 1, color: "var(--ink)" }}>{r.title}</span>
            <Button size="sm" onClick={() => onSelectDesign(r.id)}>Open</Button>
          </div>
          {r.matched_elements.map((m, i) => (
            <p key={i} style={{ margin: "2px 0 0 0", fontSize: 12, color: "var(--ink-3)" }}>{m}</p>
          ))}
        </div>
      ))}
    </div>
  );
}
