import { useState } from "react";
import type { Application, ApplicationIntegrationCreate } from "../api/application";
import { useIntegrations, useCreateIntegration, useDeleteIntegration } from "../api/application";
import IntegrationForm from "./IntegrationForm";

interface Props {
  apps: Application[];
  filterAppId?: string | null;
}

const TYPE_COLORS: Record<string, string> = {
  API: "#e3f2fd",
  event: "#f3e5f5",
  file: "#e8f5e9",
  database: "#fff8e1",
  messaging: "#fce4ec",
  other: "#f5f5f5",
};

export default function IntegrationList({ apps, filterAppId }: Props) {
  const { data } = useIntegrations(filterAppId ?? undefined);
  const createIntegration = useCreateIntegration();
  const deleteIntegration = useDeleteIntegration();
  const [showForm, setShowForm] = useState(false);

  const handleSave = async (body: ApplicationIntegrationCreate) => {
    await createIntegration.mutateAsync(body);
    setShowForm(false);
  };

  const handleDelete = (id: string) => {
    if (!confirm("Delete this integration?")) return;
    deleteIntegration.mutate(id);
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: "#444" }}>
          Integrations {data ? `(${data.total})` : ""}
        </h4>
        <button onClick={() => setShowForm(s => !s)} style={{ fontSize: 11, color: "#1168BD", background: "none", border: "1px solid #1168BD", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}>
          + New
        </button>
      </div>
      {showForm && (
        <IntegrationForm
          apps={apps}
          defaultSourceId={filterAppId ?? undefined}
          onSave={handleSave}
          onCancel={() => setShowForm(false)}
          saving={createIntegration.isPending}
        />
      )}
      {(!data || data.items.length === 0) && !showForm && (
        <div style={{ fontSize: 12, color: "#888" }}>No integrations.</div>
      )}
      {data?.items.map(item => (
        <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 6, marginBottom: 4, background: "#fafafa", border: "1px solid #eee" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
              {item.source_app_name} → {item.target_app_name}
            </div>
            {item.description && <div style={{ fontSize: 11, color: "#888" }}>{item.description}</div>}
          </div>
          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 10, background: TYPE_COLORS[item.integration_type] ?? "#f5f5f5", color: "#333" }}>
            {item.integration_type}
          </span>
          <button onClick={() => handleDelete(item.id)} style={{ fontSize: 11, color: "#c00", background: "none", border: "none", cursor: "pointer" }}>✕</button>
        </div>
      ))}
    </div>
  );
}
