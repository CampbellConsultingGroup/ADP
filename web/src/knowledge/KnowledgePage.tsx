import React, { useState } from "react";
import type { KnowledgeKind } from "../api/knowledge";
import { KNOWLEDGE_KINDS, useImportCalmPattern, useKnowledgeItem, useKnowledgeItems } from "../api/knowledge";
import type { AppView } from "../shell";
import { Button } from "../ui";
import KnowledgeItemForm from "./KnowledgeItemForm";
import KnowledgeItemRow from "./KnowledgeItemRow";

interface KnowledgePageProps {
  onNavigate: (view: AppView) => void;
  designId?: string | null;
}

export default function KnowledgePage(_props: KnowledgePageProps): React.ReactElement {
  const [kindFilter, setKindFilter] = useState<KnowledgeKind | "">("");
  const [mode, setMode] = useState<"idle" | "create" | "edit" | "import-calm">("idle");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [calmJson, setCalmJson] = useState("");
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  const importCalm = useImportCalmPattern();

  const { data, isLoading, error } = useKnowledgeItems();
  const { data: editingItem } = useKnowledgeItem(editingId);

  const allItems = data?.items ?? [];
  const filtered = kindFilter ? allItems.filter((i) => i.kind === kindFilter) : allItems;

  const handleEdit = (id: string) => {
    setEditingId(id);
    setMode("edit");
  };

  const handleDone = () => {
    setMode("idle");
    setEditingId(null);
  };

  const handleImportCalm = () => {
    if (!calmJson.trim()) return;
    importCalm.mutate(calmJson, {
      onSuccess: (result) => {
        const n = result.items_created + result.items_updated;
        setImportSuccess(`${n} item${n !== 1 ? "s" : ""} imported`);
        setCalmJson("");
        setMode("idle");
        setTimeout(() => setImportSuccess(null), 4000);
      },
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>Knowledge Base</h2>
            <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
              {data?.total ?? 0} active item{(data?.total ?? 0) !== 1 ? "s" : ""} — these ground AI recommendations
            </p>
          </div>
          {mode === "idle" && (
            <div style={{ display: "flex", gap: 8 }}>
              <Button icon="doc" onClick={() => setMode("import-calm")}>Import CALM</Button>
              <Button variant="primary" icon="plus" onClick={() => setMode("create")}>Add Item</Button>
            </div>
          )}
        </div>

        {/* Import CALM panel */}
        {mode === "import-calm" && (
          <div style={{ background: "var(--good-wash)", border: "1px solid color-mix(in srgb, var(--good) 35%, var(--border))", borderRadius: 8, padding: 20, marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>Import CALM Pattern</h3>
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--ink-2)" }}>
              Paste a FINOS CALM JSON pattern document. The pattern will be indexed and made available to the recommendation engine.
            </p>
            <textarea
              className="ui-textarea"
              value={calmJson}
              onChange={(e) => setCalmJson(e.target.value)}
              placeholder='{"$id": "https://example.com/my-pattern", "nodes": [...], "relationships": [...]}'
              rows={10}
              style={{ fontFamily: "var(--mono)", fontSize: 12 }}
            />
            {importCalm.isError && (
              <div className="ui-alert crit" style={{ marginTop: 8 }}>{importCalm.error?.message}</div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
              <Button onClick={() => { setMode("idle"); setCalmJson(""); importCalm.reset(); }}>Cancel</Button>
              <Button variant="primary" onClick={handleImportCalm} disabled={!calmJson.trim() || importCalm.isPending}>
                {importCalm.isPending ? "Importing…" : "Import"}
              </Button>
            </div>
          </div>
        )}

        {/* Success toast */}
        {importSuccess && (
          <div className="ui-alert good" style={{ marginBottom: 12, fontWeight: 600 }}>✓ {importSuccess}</div>
        )}

        {/* Create/Edit form */}
        {(mode === "create" || (mode === "edit" && editingItem)) && (
          <KnowledgeItemForm
            existing={mode === "edit" ? editingItem : undefined}
            onDone={handleDone}
            onCancel={handleDone}
          />
        )}

        {/* Kind filter */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: "var(--ink-3)" }}>Filter by kind:</span>
          <select
            className="ui-select"
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as KnowledgeKind | "")}
          >
            <option value="">All kinds</option>
            {KNOWLEDGE_KINDS.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
          {kindFilter && (
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>
              {filtered.length} of {allItems.length} item{allItems.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Loading / error */}
        {isLoading && (
          <div style={{ padding: 20, textAlign: "center", color: "var(--ink-3)", fontSize: 14 }}>
            Loading knowledge base...
          </div>
        )}
        {error && (
          <div className="ui-alert crit">Failed to load knowledge items: {error.message}</div>
        )}

        {/* Empty state */}
        {!isLoading && !error && filtered.length === 0 && (
          <div className="ui-empty">
            <p style={{ margin: 0 }}>
              {kindFilter
                ? `No ${kindFilter.replace("_", " ")} items in the knowledge base.`
                : "The knowledge base is empty. Click “Add Item” to add the first knowledge item."}
            </p>
          </div>
        )}

        {/* Item list */}
        {!isLoading && filtered.length > 0 && (
          <div className="ui-list">
            {filtered.map((item) => (
              <KnowledgeItemRow
                key={item.id}
                item={item}
                onEdit={handleEdit}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
