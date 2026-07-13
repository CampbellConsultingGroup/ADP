import { useState } from "react";
import {
  useDomains,
  useCreateDomain,
  useDeleteDomain,
  type BusinessDomain,
} from "../api/business";
import { Button, StatusBadge } from "../ui";
import { CLASSIFICATION_TONE, CLASSIFICATION_LABEL } from "./classification";
import DomainForm from "./DomainForm";

interface DomainListProps {
  onSelect: (domainId: string) => void;
}

export default function DomainList({ onSelect }: DomainListProps) {
  const { data, isLoading, error } = useDomains();
  const createMutation = useCreateDomain();
  const deleteMutation = useDeleteDomain();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading domains…</div>;
  if (error) return <div className="ui-alert crit">Failed to load domains</div>;

  const items = data?.items ?? [];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15, color: "var(--ink)" }}>Business Domains</h3>
        <Button size="sm" variant={showForm ? "default" : "primary"} icon={showForm ? undefined : "plus"} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "New Domain"}
        </Button>
      </div>

      {showForm && (
        <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12, background: "var(--surface)" }}>
          <DomainForm
            onSubmit={(d) =>
              createMutation.mutate(d as Partial<BusinessDomain>, {
                onSuccess: () => setShowForm(false),
              })
            }
            onCancel={() => setShowForm(false)}
            isLoading={createMutation.isPending}
          />
          {createMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>{createMutation.error.message}</div>
          )}
        </div>
      )}

      {items.length === 0 && !showForm && (
        <div style={{ color: "var(--ink-3)", fontSize: 13 }}>No domains yet. Create one above.</div>
      )}

      {items.map((d) => (
        <div
          key={d.id}
          onClick={() => onSelect(d.id)}
          style={{
            border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8,
            cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--surface)",
          }}
        >
          <div>
            <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)" }}>{d.name}</div>
            <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>
              {d.capability_count} L1 capabilities
              {d.org_unit ? ` · ${d.org_unit}` : ""}
              {d.risk_flags.length > 0 ? ` · ${d.risk_flags.join(", ")}` : ""}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <StatusBadge tone={CLASSIFICATION_TONE[d.classification] ?? "neutral"}>
              {CLASSIFICATION_LABEL[d.classification] ?? d.classification}
            </StatusBadge>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Delete domain "${d.name}"?`)) deleteMutation.mutate(d.id);
              }}
              style={{ fontSize: 13, color: "var(--crit)", background: "none", border: "none", cursor: "pointer" }}
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
