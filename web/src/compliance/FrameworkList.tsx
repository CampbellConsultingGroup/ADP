import { useState } from "react";
import { useFrameworks, useCreateFramework } from "../api/compliance";
import { Button } from "../ui";
import FrameworkForm from "./FrameworkForm";

interface FrameworkListProps {
  onSelectFramework: (frameworkId: string) => void;
}

export default function FrameworkList({ onSelectFramework }: FrameworkListProps) {
  const { data, isLoading, error } = useFrameworks();
  const createMutation = useCreateFramework();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading frameworks…</div>;
  if (error) return <div className="ui-alert crit">Failed to load frameworks</div>;

  const items = data?.items ?? [];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15, color: "var(--ink)" }}>Compliance Frameworks</h3>
        <Button
          size="sm"
          variant={showForm ? "default" : "primary"}
          icon={showForm ? undefined : "plus"}
          onClick={() => setShowForm(!showForm)}
        >
          {showForm ? "Cancel" : "Add Framework"}
        </Button>
      </div>

      {showForm && (
        <div
          style={{
            border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12,
            background: "var(--surface)",
          }}
        >
          <FrameworkForm
            onSubmit={(body) => createMutation.mutate(body, { onSuccess: () => setShowForm(false) })}
            onCancel={() => setShowForm(false)}
            isLoading={createMutation.isPending}
          />
          {createMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
              {createMutation.error.message}
            </div>
          )}
        </div>
      )}

      {items.length === 0 && !showForm && (
        <div style={{ color: "var(--ink-3)", fontSize: 13 }}>
          No frameworks tracked yet. Add one above.
        </div>
      )}

      {items.map((fw) => (
        <div
          key={fw.id}
          onClick={() => onSelectFramework(fw.id)}
          style={{
            border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8,
            cursor: "pointer", background: "var(--surface)",
          }}
        >
          <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)" }}>{fw.name}</div>
          <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>
            {fw.jurisdiction} · {fw.authority} · {fw.version}
          </div>
        </div>
      ))}
    </div>
  );
}
