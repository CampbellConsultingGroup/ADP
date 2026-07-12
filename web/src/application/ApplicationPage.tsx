import { Suspense, useState } from "react";
import { useApplications, useCreateApplication } from "../api/application";
import type { ApplicationCreate } from "../api/application";
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--ink-3)", fontSize: 14 }}>
            Select an application or click “Add” to create one
          </div>
        )}
      </div>
    </div>
  );
}

export default function ApplicationPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Suspense fallback={<div style={{ padding: 24, color: "var(--ink-3)" }}>Loading…</div>}>
        <ApplicationPageInner />
      </Suspense>
    </div>
  );
}
