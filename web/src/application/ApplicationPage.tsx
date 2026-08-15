import { Suspense, useState, type CSSProperties } from "react";
import { useApplications, useCreateApplication } from "../api/application";
import type { ApplicationCreate } from "../api/application";
import ApplicationList from "./ApplicationList";
import ApplicationDetail from "./ApplicationDetail";
import ApplicationForm from "./ApplicationForm";
import RationalizationView from "./RationalizationView";
import RoadmapView from "./RoadmapView";

function ApplicationPageInner() {
  const { data } = useApplications();
  const createApp = useCreateApplication();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const apps = data?.items ?? [];
  const handleCreate = async (body: ApplicationCreate) => {
    const created = await createApp.mutateAsync(body);
    setShowCreate(false);
    setSelectedId(created.id);
  };

  const handleDeleted = () => setSelectedId(null);

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden", background: "var(--surface)" }}>
      {/* Sidebar */}
      <div style={{ width: 260, borderRight: "1px solid var(--border)", overflow: "auto", flexShrink: 0 }}>
        <ApplicationList
          apps={apps}
          selectedId={selectedId}
          onSelect={(id) => { setSelectedId(id); setShowCreate(false); }}
          onAdd={() => { setShowCreate(true); setSelectedId(null); }}
        />
      </div>

      {/* Main panel */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {showCreate && (
          // Same overflow:hidden-parent-with-no-scroll-region issue as
          // ApplicationDetail.tsx's edit form (bug report, 2026-08-15) --
          // this panel also has overflow:hidden with nothing scrollable
          // between it and ApplicationForm's own root.
          <div style={{ height: "100%", overflowY: "auto" }}>
            <ApplicationForm
              onSave={handleCreate}
              onCancel={() => setShowCreate(false)}
              saving={createApp.isPending}
            />
          </div>
        )}
        {!showCreate && selectedId && (
          <ApplicationDetail
            key={selectedId}
            appId={selectedId}
            allApps={apps}
            onDeleted={handleDeleted}
          />
        )}
        {!showCreate && !selectedId && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--ink-3)", fontSize: 14 }}>
            Select an application or click “Add” to create one
          </div>
        )}
      </div>
    </div>
  );
}

function tabStyle(active: boolean): CSSProperties {
  return {
    padding: "6px 14px",
    fontSize: 13,
    border: "1px solid var(--border)",
    borderRadius: 6,
    background: active ? "var(--accent, #2874A6)" : "var(--surface)",
    color: active ? "#fff" : "var(--ink-2)",
    cursor: "pointer",
  };
}

export default function ApplicationPage() {
  const [view, setView] = useState<"registry" | "rationalization" | "roadmap">("registry");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, padding: "10px 16px", borderBottom: "1px solid var(--border)", flexShrink: 0 }}>
        <button type="button" style={tabStyle(view === "registry")} aria-pressed={view === "registry"} onClick={() => setView("registry")}>
          Registry
        </button>
        <button type="button" style={tabStyle(view === "rationalization")} aria-pressed={view === "rationalization"} onClick={() => setView("rationalization")}>
          Rationalization
        </button>
        <button type="button" style={tabStyle(view === "roadmap")} aria-pressed={view === "roadmap"} onClick={() => setView("roadmap")}>
          Roadmap
        </button>
      </div>
      <div style={{ flex: 1, overflow: "hidden" }}>
        {view === "registry" && (
          <Suspense fallback={<div style={{ padding: 24, color: "var(--ink-3)" }}>Loading…</div>}>
            <ApplicationPageInner />
          </Suspense>
        )}
        {view === "rationalization" && <RationalizationView />}
        {view === "roadmap" && <RoadmapView />}
      </div>
    </div>
  );
}
