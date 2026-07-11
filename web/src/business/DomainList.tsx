import { useState } from "react";
import {
  useDomains,
  useCreateDomain,
  useDeleteDomain,
  type BusinessDomain,
} from "../api/business";
import DomainForm from "./DomainForm";

const CLASSIFICATION_BADGE: Record<string, { bg: string; text: string }> = {
  strategic: { bg: "#c8e6c9", text: "#1b5e20" },
  differentiating: { bg: "#ffe0b2", text: "#bf360c" },
  commodity: { bg: "#e0e0e0", text: "#424242" },
};

interface DomainListProps {
  onSelect: (domainId: string) => void;
}

export default function DomainList({ onSelect }: DomainListProps) {
  const { data, isLoading, error } = useDomains();
  const createMutation = useCreateDomain();
  const deleteMutation = useDeleteDomain();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <div style={{ padding: 16 }}>Loading domains…</div>;
  if (error) return <div style={{ padding: 16, color: "red" }}>Failed to load domains</div>;

  const items = data?.items ?? [];

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>Business Domains</h3>
        <button onClick={() => setShowForm(!showForm)} style={{ fontSize: 12 }}>
          {showForm ? "Cancel" : "+ New Domain"}
        </button>
      </div>

      {showForm && (
        <div style={{ border: "1px solid #ddd", borderRadius: 6, padding: 12, marginBottom: 12 }}>
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
            <div style={{ color: "red", fontSize: 12, marginTop: 6 }}>
              {createMutation.error.message}
            </div>
          )}
        </div>
      )}

      {items.length === 0 && !showForm && (
        <div style={{ color: "#888", fontSize: 13 }}>No domains yet. Create one above.</div>
      )}

      {items.map((d) => {
        const badge = CLASSIFICATION_BADGE[d.classification] ?? { bg: "#eee", text: "#333" };
        return (
          <div
            key={d.id}
            onClick={() => onSelect(d.id)}
            style={{
              border: "1px solid #ddd",
              borderRadius: 6,
              padding: "8px 12px",
              marginBottom: 8,
              cursor: "pointer",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ fontWeight: 500, fontSize: 14 }}>{d.name}</div>
              <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
                {d.capability_count} L1 capabilities
                {d.org_unit ? ` · ${d.org_unit}` : ""}
                {d.risk_flags.length > 0 ? ` · ${d.risk_flags.join(", ")}` : ""}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span
                style={{
                  background: badge.bg,
                  color: badge.text,
                  padding: "2px 7px",
                  borderRadius: 10,
                  fontSize: 11,
                  fontWeight: 500,
                }}
              >
                {d.classification}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`Delete domain "${d.name}"?`)) {
                    deleteMutation.mutate(d.id);
                  }
                }}
                style={{ fontSize: 11, color: "#c62828", background: "none", border: "none", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
