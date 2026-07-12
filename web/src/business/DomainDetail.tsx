import { useState } from "react";
import {
  useDomain,
  useUpdateDomain,
  useCapabilities,
  useAssignCapabilityDomain,
  type BusinessDomain,
} from "../api/business";
import DomainForm from "./DomainForm";

interface DomainDetailProps {
  domainId: string;
  onBack: () => void;
}

export default function DomainDetail({ domainId, onBack }: DomainDetailProps) {
  const { data: domain, isLoading, error } = useDomain(domainId);
  const { data: allCaps } = useCapabilities();
  const updateMutation = useUpdateDomain(domainId);
  const [editing, setEditing] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

  if (isLoading) return <div style={{ padding: 16 }}>Loading…</div>;
  if (error || !domain) return <div style={{ padding: 16, color: "var(--crit)" }}>Domain not found</div>;

  const assignedIds = new Set(domain.capabilities.map((c) => c.capability_id));
  const l1Caps = (allCaps?.items ?? []).filter((c) => c.level === 1);
  const unassigned = l1Caps.filter((c) => !assignedIds.has(c.id));

  return (
    <div style={{ padding: 16 }}>
      <button onClick={onBack} style={{ fontSize: 12, marginBottom: 12 }}>
        ← Back to Domains
      </button>

      {editing ? (
        <div style={{ marginBottom: 16 }}>
          <DomainForm
            initial={domain}
            onSubmit={(d) =>
              updateMutation.mutate(d as Partial<BusinessDomain>, {
                onSuccess: () => setEditing(false),
              })
            }
            onCancel={() => setEditing(false)}
            isLoading={updateMutation.isPending}
          />
        </div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: "0 0 4px 0", fontSize: 16 }}>{domain.name}</h3>
              <div style={{ fontSize: 12, color: "var(--ink-2)" }}>
                {domain.classification}
                {domain.org_unit ? ` · ${domain.org_unit}` : ""}
              </div>
            </div>
            <button onClick={() => setEditing(true)} style={{ fontSize: 12 }}>
              Edit
            </button>
          </div>
          {domain.scope_statement && (
            <div style={{ fontSize: 13, marginTop: 8, color: "var(--ink-2)" }}>{domain.scope_statement}</div>
          )}
          {domain.risk_flags.length > 0 && (
            <div style={{ marginTop: 6, display: "flex", gap: 4, flexWrap: "wrap" }}>
              {domain.risk_flags.map((f) => (
                <span
                  key={f}
                  style={{
                    background: "var(--warn-wash)",
                    color: "var(--warn)",
                    padding: "1px 6px",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                >
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      <h4 style={{ fontSize: 14, marginBottom: 8 }}>
        Assigned L1 Capabilities ({domain.capabilities.length})
      </h4>

      {assignError && (
        <div style={{ color: "var(--crit)", fontSize: 12, marginBottom: 8 }}>{assignError}</div>
      )}

      {domain.capabilities.length === 0 && (
        <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 8 }}>None yet.</div>
      )}

      {domain.capabilities.map((cap) => (
        <CapabilityRow
          key={cap.capability_id}
          capId={cap.capability_id}
          name={cap.name}
          domainId={domainId}
          assigned
          onError={setAssignError}
        />
      ))}

      {unassigned.length > 0 && (
        <>
          <div style={{ fontSize: 12, color: "var(--ink-3)", margin: "10px 0 6px 0" }}>
            Unassigned L1 capabilities
          </div>
          {unassigned.map((cap) => (
            <CapabilityRow
              key={cap.id}
              capId={cap.id}
              name={cap.name}
              domainId={null}
              assigned={false}
              onError={setAssignError}
            />
          ))}
        </>
      )}
    </div>
  );
}

function CapabilityRow({
  capId,
  name,
  domainId,
  assigned,
  onError,
}: {
  capId: string;
  name: string;
  domainId: string | null;
  assigned: boolean;
  onError: (msg: string | null) => void;
}) {
  const assignMutation = useAssignCapabilityDomain(capId);

  function toggle() {
    onError(null);
    assignMutation.mutate(assigned ? null : domainId, {
      onError: (e) => onError(e.message),
    });
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "5px 8px",
        borderRadius: 4,
        background: assigned ? "var(--good-wash)" : "var(--surface-2)",
        marginBottom: 4,
      }}
    >
      <span style={{ fontSize: 13 }}>{name}</span>
      <button
        onClick={toggle}
        disabled={assignMutation.isPending}
        style={{ fontSize: 11, cursor: "pointer" }}
      >
        {assigned ? "Remove" : "Assign"}
      </button>
    </div>
  );
}
