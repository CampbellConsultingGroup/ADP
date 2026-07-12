import React, { useState } from "react";
import type { KnowledgeKind } from "../api/knowledge";
import { KNOWLEDGE_KINDS, useImportCalmPattern, useKnowledgeItem, useKnowledgeItems } from "../api/knowledge";
import type { AppView } from "../shell";
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
            <h2 style={{ fontSize: 20, fontWeight: 700, color: "#111827", margin: "0 0 4px" }}>Knowledge Base</h2>
            <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
              {data?.total ?? 0} active item{(data?.total ?? 0) !== 1 ? "s" : ""} — these ground AI recommendations
            </p>
          </div>
          {mode === "idle" && (
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={() => setMode("import-calm")}
                style={{ padding: "8px 14px", background: "#fff", color: "#065F46", border: "1px solid #6EE7B7", borderRadius: 4, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
              >
                Import CALM
              </button>
              <button
                onClick={() => setMode("create")}
                style={{ padding: "8px 18px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
              >
                + Add Item
              </button>
            </div>
          )}
        </div>

        {/* Import CALM panel */}
        {mode === "import-calm" && (
          <div style={{ background: "#F0FDF4", border: "1px solid #6EE7B7", borderRadius: 8, padding: 20, marginBottom: 16 }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 700 }}>Import CALM Pattern</h3>
            <p style={{ margin: "0 0 12px", fontSize: 13, color: "#374151" }}>
              Paste a FINOS CALM JSON pattern document. The pattern will be indexed and made available to the recommendation engine.
            </p>
            <textarea
              value={calmJson}
              onChange={(e) => setCalmJson(e.target.value)}
              placeholder='{"$id": "https://example.com/my-pattern", "nodes": [...], "relationships": [...]}'
              rows={10}
              style={{ width: "100%", padding: "8px 10px", fontSize: 12, fontFamily: "monospace", borderRadius: 6, border: "1px solid #D1D5DB", resize: "vertical", boxSizing: "border-box" }}
            />
            {importCalm.isError && (
              <div style={{ marginTop: 8, padding: 10, background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 5, fontSize: 13, color: "#B91C1C" }}>
                {importCalm.error?.message}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
              <button
                onClick={() => { setMode("idle"); setCalmJson(""); importCalm.reset(); }}
                style={{ padding: "8px 16px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleImportCalm}
                disabled={!calmJson.trim() || importCalm.isPending}
                style={{ padding: "8px 18px", background: (!calmJson.trim() || importCalm.isPending) ? "#D1D5DB" : "#065F46", color: "#fff", border: "none", borderRadius: 4, cursor: (!calmJson.trim() || importCalm.isPending) ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
              >
                {importCalm.isPending ? "Importing..." : "Import"}
              </button>
            </div>
          </div>
        )}

        {/* Success toast */}
        {importSuccess && (
          <div style={{ marginBottom: 12, padding: "10px 16px", background: "#D1FAE5", border: "1px solid #6EE7B7", borderRadius: 6, fontSize: 14, color: "#065F46", fontWeight: 600 }}>
            ✓ {importSuccess}
          </div>
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
          <span style={{ fontSize: 13, color: "#6B7280" }}>Filter by kind:</span>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as KnowledgeKind | "")}
            style={{ padding: "5px 10px", fontSize: 13, borderRadius: 5, border: "1px solid #D1D5DB", background: "#fff" }}
          >
            <option value="">All kinds</option>
            {KNOWLEDGE_KINDS.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
          {kindFilter && (
            <span style={{ fontSize: 12, color: "#6B7280" }}>
              {filtered.length} of {allItems.length} item{allItems.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Loading / error */}
        {isLoading && (
          <div style={{ padding: 20, textAlign: "center", color: "#6B7280", fontSize: 14 }}>
            Loading knowledge base...
          </div>
        )}
        {error && (
          <div style={{ padding: 14, background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 6, fontSize: 13, color: "#B91C1C" }}>
            Failed to load knowledge items: {error.message}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && filtered.length === 0 && (
          <div style={{ padding: 40, textAlign: "center", color: "#6B7280", fontSize: 14, border: "2px dashed #E5E7EB", borderRadius: 8 }}>
            {kindFilter
              ? `No ${kindFilter.replace("_", " ")} items in the knowledge base.`
              : "The knowledge base is empty. Click \"+ Add Item\" to add the first knowledge item."}
          </div>
        )}

        {/* Item list */}
        {!isLoading && filtered.length > 0 && (
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, overflow: "hidden" }}>
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
