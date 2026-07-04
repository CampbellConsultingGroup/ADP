import React, { useState } from "react";
import { useDesignList, useCreateDesign } from "../api/designs";
import { NavBar, type AppView } from "../shell";

interface DesignsPageProps {
  onSelectDesign: (id: string) => void;
  onNavigate: (view: AppView) => void;
}

export default function DesignsPage({ onSelectDesign, onNavigate }: DesignsPageProps): React.ReactElement {
  const [showForm, setShowForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [titleError, setTitleError] = useState("");

  const { data, isLoading, error } = useDesignList();
  const createDesign = useCreateDesign();

  const designs = data?.designs ?? [];

  const handleCreate = () => {
    if (!newTitle.trim()) {
      setTitleError("Title is required");
      return;
    }
    setTitleError("");
    createDesign.mutate(
      { title: newTitle.trim() },
      {
        onSuccess: (design) => {
          setShowForm(false);
          setNewTitle("");
          onSelectDesign(design.id);
        },
      },
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", fontFamily: "Arial, sans-serif" }}>
      <NavBar currentView="designs" onNavigate={onNavigate} designId={null} />

      <div style={{ flex: 1, overflowY: "auto", padding: 24, maxWidth: 800, width: "100%", margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: "#111827", margin: "0 0 4px" }}>Designs</h1>
            <p style={{ fontSize: 13, color: "#6B7280", margin: 0 }}>
              {data ? `${data.total} design${data.total !== 1 ? "s" : ""}` : "Loading..."}
            </p>
          </div>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              style={{ padding: "9px 20px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 14, fontWeight: 600 }}
            >
              + New Design
            </button>
          )}
        </div>

        {/* Create form */}
        {showForm && (
          <div style={{ marginBottom: 20, padding: 20, background: "#F8FAFC", border: "1px solid #E5E7EB", borderRadius: 8 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700 }}>New Design</h3>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => { setNewTitle(e.target.value); setTitleError(""); }}
              placeholder="Design title (e.g. Payment Platform v2)"
              autoFocus
              style={{ width: "100%", padding: "8px 12px", fontSize: 14, borderRadius: 5, border: `1px solid ${titleError ? "#DC2626" : "#D1D5DB"}`, boxSizing: "border-box", marginBottom: 4 }}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
            {titleError && <div style={{ fontSize: 12, color: "#DC2626", marginBottom: 8 }}>{titleError}</div>}
            {createDesign.isError && (
              <div style={{ fontSize: 13, color: "#B91C1C", padding: "6px 10px", background: "#FEE2E2", borderRadius: 4, marginBottom: 8 }}>
                {createDesign.error?.message ?? "Failed to create design"}
              </div>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button
                onClick={() => { setShowForm(false); setNewTitle(""); setTitleError(""); }}
                style={{ padding: "7px 16px", background: "#fff", color: "#374151", border: "1px solid #D1D5DB", borderRadius: 4, cursor: "pointer", fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={createDesign.isPending}
                style={{ padding: "7px 20px", background: createDesign.isPending ? "#D1D5DB" : "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: createDesign.isPending ? "not-allowed" : "pointer", fontSize: 14, fontWeight: 600 }}
              >
                {createDesign.isPending ? "Creating..." : "Create Design"}
              </button>
            </div>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div style={{ padding: 32, textAlign: "center", color: "#6B7280" }}>Loading designs...</div>
        )}

        {/* Error */}
        {error && (
          <div style={{ padding: 14, background: "#FEE2E2", border: "1px solid #FECACA", borderRadius: 6, fontSize: 13, color: "#B91C1C" }}>
            Failed to load designs: {error.message}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && designs.length === 0 && (
          <div style={{ padding: 60, textAlign: "center", border: "2px dashed #E5E7EB", borderRadius: 10 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📐</div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "#111827", marginBottom: 8 }}>No designs yet</h2>
            <p style={{ fontSize: 14, color: "#6B7280", marginBottom: 20 }}>
              Create your first architecture design to get started.
            </p>
            <button
              onClick={() => setShowForm(true)}
              style={{ padding: "10px 24px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 5, cursor: "pointer", fontSize: 15, fontWeight: 600 }}
            >
              Create your first design
            </button>
          </div>
        )}

        {/* Design list */}
        {!isLoading && designs.length > 0 && (
          <div style={{ border: "1px solid #E5E7EB", borderRadius: 8, overflow: "hidden" }}>
            {designs.map((d, i) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "14px 16px",
                  borderBottom: i < designs.length - 1 ? "1px solid #F3F4F6" : "none",
                  background: "#fff",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "#111827", marginBottom: 3 }}>{d.title}</div>
                  <div style={{ fontSize: 12, color: "#9CA3AF" }}>
                    {d.id} · {d.element_count} element{d.element_count !== 1 ? "s" : ""} · {d.requirement_count} requirement{d.requirement_count !== 1 ? "s" : ""} · {new Date(d.created_at).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={() => onSelectDesign(d.id)}
                  style={{ padding: "7px 18px", background: "#1168BD", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 600, flexShrink: 0 }}
                >
                  Open
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
