import React, { useState } from "react";
import { useObjectives, useCreateObjective, useThemes } from "../api/strategy";
import ObjectiveForm from "./ObjectiveForm";

interface ObjectiveListProps {
  onSelect: (objectiveId: string) => void;
  /** Cross-navigation: when set (arrived via a Theme's "N objectives"
   *  link), the list narrows to just that theme's objectives, with a
   *  clearable filter chip -- there is no single row to scroll-and-
   *  highlight here since a theme commonly has several objectives. */
  filterThemeId?: string | null;
  onClearThemeFilter?: () => void;
}

export default function ObjectiveList({ onSelect, filterThemeId, onClearThemeFilter }: ObjectiveListProps): React.ReactElement {
  const { data, isLoading, error } = useObjectives();
  const { data: themesData } = useThemes();
  const createMutation = useCreateObjective();
  const [creating, setCreating] = useState(false);

  if (isLoading) return <div style={{ padding: 20, color: "var(--ink-3)", fontSize: 14 }}>Loading objectives…</div>;
  if (error) return <div style={{ padding: 14, background: "var(--crit-wash)", borderRadius: 6, fontSize: 13, color: "var(--crit)" }}>Failed to load objectives: {error.message}</div>;

  const allItems = data?.items ?? [];
  const items = filterThemeId ? allItems.filter((o) => o.theme_id === filterThemeId) : allItems;
  const filterThemeName = filterThemeId
    ? themesData?.items.find((t) => t.id === filterThemeId)?.name ?? filterThemeId
    : null;

  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "0 0 16px", lineHeight: 1.5 }}>
        <strong style={{ color: "var(--ink-2)" }}>Objective:</strong> A specific, measurable commitment
        that operationalizes a theme — owned by a person, with a target metric and a fiscal horizon,
        linked to the real capabilities and value streams it&rsquo;s meant to move. Where a theme states
        direction, an objective states what will change, by how much, and by when.
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--ink-3)" }}>
          {items.length} objective{items.length !== 1 ? "s" : ""}
          {filterThemeName && <> in theme &ldquo;{filterThemeName}&rdquo;</>}
        </span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {filterThemeId && onClearThemeFilter && (
            <button
              onClick={onClearThemeFilter}
              style={{ fontSize: 12, color: "var(--ink-3)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
            >
              Clear filter
            </button>
          )}
          <button
            onClick={() => setCreating(!creating)}
            style={{ padding: "6px 14px", background: "var(--good)", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600 }}
          >
            {creating ? "Cancel" : "+ New Objective"}
          </button>
        </div>
      </div>

      {creating && (
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12, background: "var(--surface)" }}>
          <ObjectiveForm
            onSubmit={(body) =>
              createMutation.mutate(body, { onSuccess: () => setCreating(false) })
            }
            onCancel={() => setCreating(false)}
            isLoading={createMutation.isPending}
          />
          {createMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>{createMutation.error.message}</div>
          )}
        </div>
      )}

      {items.length === 0 && !creating && (
        <div style={{ padding: 40, textAlign: "center", color: "var(--ink-3)", fontSize: 14, border: "2px dashed var(--border)", borderRadius: 8 }}>
          {filterThemeId
            ? `No objectives in theme "${filterThemeName}" yet.`
            : 'No strategic objectives yet. Click "New Objective" to add the first one.'}
        </div>
      )}

      {items.map((obj) => (
        <div
          key={obj.id}
          onClick={() => onSelect(obj.id)}
          style={{
            padding: "12px 16px",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            marginBottom: 6,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 2 }}>{obj.statement}</div>
            <div style={{ fontSize: 12, color: "var(--ink-3)" }}>
              {obj.owner} · {obj.period} {obj.fiscal_year}
            </div>
          </div>
          <span style={{ fontSize: 12, color: "var(--ink-3)" }}>›</span>
        </div>
      ))}
    </div>
  );
}
