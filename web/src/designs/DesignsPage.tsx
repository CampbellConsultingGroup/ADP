import React, { useState } from "react";
import { useDesignList, useCreateDesign } from "../api/designs";
import type { AppView } from "../shell";
import { Button, Card, StatusBadge, Icon, type BadgeTone } from "../ui";
import LifecycleTransitionButton from "./LifecycleTransitionButton";

interface DesignsPageProps {
  onSelectDesign: (id: string) => void;
  onNavigate: (view: AppView) => void;
}

const LIFECYCLE: Record<string, { tone: BadgeTone; label: string }> = {
  draft: { tone: "neutral", label: "Draft" },
  proposed: { tone: "info", label: "Proposed" },
  current: { tone: "good", label: "Current" },
  deprecated: { tone: "warn", label: "Deprecated" },
  decommissioned: { tone: "crit", label: "Decommissioned" },
};

export default function DesignsPage({ onSelectDesign }: DesignsPageProps): React.ReactElement {
  const [showForm, setShowForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [titleError, setTitleError] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading, error } = useDesignList(1, statusFilter || undefined);
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
    <div className="ui-page" style={{ maxWidth: 940 }}>
      <div className="ui-toolbar">
        <div>
          <h1 className="ui-h1">Designs</h1>
          <p className="ui-subtle">
            {data ? `${data.total} design${data.total !== 1 ? "s" : ""}` : "Loading…"}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select className="ui-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="proposed">Proposed</option>
            <option value="current">Current</option>
            <option value="deprecated">Deprecated</option>
            <option value="decommissioned">Decommissioned</option>
          </select>
          {!showForm && (
            <Button variant="primary" icon="plus" onClick={() => setShowForm(true)}>New Design</Button>
          )}
        </div>
      </div>

      {showForm && (
        <Card style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 16, fontWeight: 700 }}>New Design</h3>
          <input
            type="text"
            className={`ui-input${titleError ? " invalid" : ""}`}
            value={newTitle}
            onChange={(e) => { setNewTitle(e.target.value); setTitleError(""); }}
            placeholder="Design title (e.g. Payment Platform v2)"
            autoFocus
            onKeyDown={(e) => e.key === "Enter" && handleCreate()}
          />
          {titleError && <div style={{ fontSize: 12, color: "var(--crit)", marginTop: 4 }}>{titleError}</div>}
          {createDesign.isError && (
            <div className="ui-alert crit" style={{ marginTop: 8 }}>
              {createDesign.error?.message ?? "Failed to create design"}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <Button onClick={() => { setShowForm(false); setNewTitle(""); setTitleError(""); }}>Cancel</Button>
            <Button variant="primary" onClick={handleCreate} disabled={createDesign.isPending}>
              {createDesign.isPending ? "Creating…" : "Create Design"}
            </Button>
          </div>
        </Card>
      )}

      {isLoading && <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>Loading designs…</div>}

      {error && <div className="ui-alert crit">Failed to load designs: {error.message}</div>}

      {!isLoading && !error && designs.length === 0 && (
        <div className="ui-empty">
          <div className="em-ic"><Icon name="sol" size={40} style={{ margin: "0 auto" }} /></div>
          <h2>No designs yet</h2>
          <p>Create your first architecture design to get started.</p>
          <Button variant="primary" icon="plus" onClick={() => setShowForm(true)}>Create your first design</Button>
        </div>
      )}

      {!isLoading && designs.length > 0 && (
        <div className="ui-list">
          {designs.map((d) => {
            const lc = LIFECYCLE[d.lifecycle_status] ?? LIFECYCLE.draft;
            return (
              <div key={d.id} className="ui-list-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>{d.title}</span>
                    <StatusBadge tone={lc.tone}>{lc.label}</StatusBadge>
                    {d.overdue_review && <StatusBadge tone="warn">Review overdue</StatusBadge>}
                  </div>
                  <div className="ui-meta">
                    {d.id} · {d.element_count} element{d.element_count !== 1 ? "s" : ""} · {d.requirement_count} requirement{d.requirement_count !== 1 ? "s" : ""} · {new Date(d.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0, alignItems: "center" }}>
                  <LifecycleTransitionButton designId={d.id} currentStatus={d.lifecycle_status} />
                  <Button variant="primary" size="sm" onClick={() => onSelectDesign(d.id)}>Open</Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
