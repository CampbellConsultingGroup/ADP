import { Suspense, useState } from "react";
import { useApplications, useCreateApplication } from "../api/application";
import type { ApplicationCreate } from "../api/application";
import ApplicationList from "./ApplicationList";
import ApplicationDetail from "./ApplicationDetail";
import ApplicationForm from "./ApplicationForm";
import RationalizationView from "./RationalizationView";
import RoadmapView from "./RoadmapView";
import AppCapabilitiesView from "./AppCapabilitiesView";
import { Tabs } from "../ui/Tabs";

function ApplicationPageInner({ initialAppId }: { initialAppId: string | null }) {
  const { data } = useApplications();
  const createApp = useCreateApplication();
  const [selectedId, setSelectedId] = useState<string | null>(initialAppId);
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

type ApplicationView = "registry" | "capabilities" | "rationalization" | "roadmap";
const APPLICATION_TABS: { id: ApplicationView; label: string }[] = [
  { id: "registry", label: "Registry" },
  { id: "capabilities", label: "Capabilities" },
  { id: "rationalization", label: "Rationalization" },
  { id: "roadmap", label: "Roadmap" },
];

// 933-agent-registry: initialAppId lets another screen (an agent's solution list) open a
// specific application in the registry. 937: initialAppCapId opens the Capabilities tab on one
// application capability.
export default function ApplicationPage({
  initialAppId = null,
  initialAppCapId = null,
}: { initialAppId?: string | null; initialAppCapId?: string | null } = {}) {
  const [view, setView] = useState<ApplicationView>(
    initialAppCapId ? "capabilities" : "registry",
  );
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Tabs
        label="Applications"
        tabs={APPLICATION_TABS}
        active={view}
        onChange={setView}
        style={{ padding: "0 16px", marginBottom: 0, flexShrink: 0 }}
      />
      <div style={{ flex: 1, overflow: "hidden" }}>
        {view === "registry" && (
          <Suspense fallback={<div style={{ padding: 24, color: "var(--ink-3)" }}>Loading…</div>}>
            <ApplicationPageInner initialAppId={initialAppId} />
          </Suspense>
        )}
        {view === "capabilities" && <AppCapabilitiesView initialId={initialAppCapId} />}
        {view === "rationalization" && <RationalizationView />}
        {view === "roadmap" && <RoadmapView />}
      </div>
    </div>
  );
}
