import { Suspense, useState } from "react";
import { useApplications, useCreateApplication } from "../api/application";
import type { ApplicationCreate } from "../api/application";
import { NavBar, type AppView } from "../shell";
import ApplicationList from "./ApplicationList";
import ApplicationDetail from "./ApplicationDetail";
import ApplicationForm from "./ApplicationForm";

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
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Sidebar */}
      <div style={{ width: 260, borderRight: "1px solid #e0e0e0", overflow: "auto", flexShrink: 0 }}>
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
          <ApplicationForm
            onSave={handleCreate}
            onCancel={() => setShowCreate(false)}
            saving={createApp.isPending}
          />
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#aaa", fontSize: 14 }}>
            Select an application or click "+ Add Application"
          </div>
        )}
      </div>
    </div>
  );
}

export default function ApplicationPage({ onNavigate }: { onNavigate?: (view: AppView) => void } = {}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      {onNavigate && <NavBar currentView="applications" onNavigate={onNavigate} designId={null} />}
      <div style={{ padding: "10px 16px", borderBottom: "1px solid #e0e0e0", display: "flex", alignItems: "center", gap: 10 }}>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Application Registry</h1>
      </div>
      <div style={{ flex: 1, overflow: "hidden" }}>
        <Suspense fallback={<div style={{ padding: 24, color: "#888" }}>Loading…</div>}>
          <ApplicationPageInner />
        </Suspense>
      </div>
    </div>
  );
}
