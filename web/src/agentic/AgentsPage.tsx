/** Estate-wide agent registry (933-agent-registry, US2): every agent, filterable by autonomy,
 * model provider, owner and lifecycle, with its solution count; opens an agent's detail. */

import React, { useState } from "react";
import { errorDetail, useAgents, useCreateAgent } from "../api/agentic";
import type { AgentFilters, AgentLifecycle, AgentWrite } from "../api/agentic";
import { StatusBadge } from "../ui";
import AgentDetail from "./AgentDetail";
import AgentForm from "./AgentForm";
import { AUTONOMY_LEVELS, HUMAN_APPROVAL_LABELS, LIFECYCLE_LABELS, autonomyLabel } from "./autonomy";

const cell: React.CSSProperties = { padding: "7px 10px", borderBottom: "1px solid var(--border)", fontSize: 12.5, textAlign: "left" };

export default function AgentsPage({ onOpenSolution }: { onOpenSolution?: (appId: string) => void }) {
  const [filters, setFilters] = useState<AgentFilters>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, isLoading } = useAgents(filters);
  const { data: unfiltered } = useAgents();
  const create = useCreateAgent();

  const providers = Array.from(
    new Set((unfiltered?.items ?? []).map((a) => a.model_provider).filter((p): p is string => !!p)),
  ).sort();
  const owners = Array.from(
    new Set((unfiltered?.items ?? []).map((a) => a.owner).filter((o): o is string => !!o)),
  ).sort();

  if (selectedId) {
    return <AgentDetail agentId={selectedId} onBack={() => setSelectedId(null)} onOpenSolution={onOpenSolution} />;
  }

  if (creating) {
    const handleCreate = async (body: AgentWrite) => {
      setError(null);
      try {
        const agent = await create.mutateAsync(body);
        setCreating(false);
        setSelectedId(agent.id);
      } catch (err) {
        setError(errorDetail(err));
      }
    };
    return (
      <div style={{ padding: "16px 20px", overflow: "auto", height: "100%" }}>
        <h2 style={{ marginTop: 0, fontSize: 17 }}>Register agent</h2>
        <AgentForm onSubmit={(b) => void handleCreate(b)} onCancel={() => setCreating(false)} saving={create.isPending} error={error} />
      </div>
    );
  }

  const set = (patch: Partial<AgentFilters>) => setFilters((f) => ({ ...f, ...patch }));
  const items = data?.items ?? [];

  return (
    <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12, overflow: "auto", height: "100%" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--ink-2)", flex: 1 }}>
          Every AI agent registered across all agentic solutions. Shared agents show more than one solution.
        </p>
        <button type="button" className="ui-btn ui-btn-primary ui-btn-sm" onClick={() => { setError(null); setCreating(true); }}>
          Register agent
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: 12.5 }}>
        <select
          aria-label="Minimum autonomy"
          value={filters.autonomy_min ?? ""}
          onChange={(e) => set({ autonomy_min: e.target.value === "" ? undefined : Number(e.target.value) })}
        >
          <option value="">Any autonomy</option>
          {AUTONOMY_LEVELS.map((d) => <option key={d.level} value={d.level}>L{d.level}+ ({d.name} or higher)</option>)}
        </select>
        <select aria-label="Model provider" value={filters.model_provider ?? ""} onChange={(e) => set({ model_provider: e.target.value || undefined })}>
          <option value="">Any provider</option>
          {providers.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select aria-label="Owner" value={filters.owner ?? ""} onChange={(e) => set({ owner: e.target.value || undefined })}>
          <option value="">Any owner</option>
          {owners.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <select
          aria-label="Lifecycle"
          value={filters.lifecycle_status ?? ""}
          onChange={(e) => set({ lifecycle_status: (e.target.value || undefined) as AgentLifecycle | undefined })}
        >
          <option value="">Any lifecycle</option>
          {Object.entries(LIFECYCLE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {Object.values(filters).some((v) => v !== undefined) && (
          <button type="button" className="ui-btn ui-btn-sm" onClick={() => setFilters({})}>Clear filters</button>
        )}
      </div>

      {isLoading ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>
      ) : items.length === 0 ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No agents match.</div>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              {["Agent", "Owner", "Model provider", "Autonomy", "Approval", "Lifecycle", "Solutions"].map((h) => (
                <th key={h} style={{ ...cell, color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} onClick={() => setSelectedId(a.id)} style={{ cursor: "pointer" }}>
                <td style={cell}>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setSelectedId(a.id); }}
                    style={{ background: "none", border: "none", padding: 0, color: "var(--accent)", cursor: "pointer", fontSize: 12.5, fontWeight: 600 }}
                  >
                    {a.name}
                  </button>
                </td>
                <td style={cell}>{a.owner ?? "—"}</td>
                <td style={cell}>{a.model_provider ?? "—"}</td>
                <td style={cell}>{autonomyLabel(a.autonomy_level)}</td>
                <td style={cell}>{HUMAN_APPROVAL_LABELS[a.human_approval]}</td>
                <td style={cell}>{LIFECYCLE_LABELS[a.lifecycle_status]}</td>
                <td style={cell}>
                  {a.solution_count === 0 ? <StatusBadge tone="warn">Unassigned</StatusBadge> : a.solution_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
