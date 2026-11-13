/** The Agents tab of an agentic application (933-agent-registry, US1): the solution's agents in
 * order with their roles; add an existing agent, register a new one, change role, reorder, remove. */

import React, { useState } from "react";
import {
  errorDetail,
  useAddSolutionAgent,
  useAgents,
  useCreateAgent,
  useRemoveSolutionAgent,
  useReorderSolutionAgents,
  useSolutionAgents,
  useUpdateSolutionAgentRole,
} from "../api/agentic";
import type { AgentWrite, SolutionRole } from "../api/agentic";
import AgentForm from "./AgentForm";
import { HUMAN_APPROVAL_LABELS, ROLE_LABELS, autonomyLabel } from "./autonomy";

const ROLES = Object.keys(ROLE_LABELS) as SolutionRole[];

const cell: React.CSSProperties = { padding: "6px 8px", borderBottom: "1px solid var(--border)", fontSize: 12.5 };
const smallBtn: React.CSSProperties = { fontSize: 11, padding: "1px 7px", cursor: "pointer" };

export default function SolutionAgentsPanel({ appId }: { appId: string }) {
  const { data, isLoading } = useSolutionAgents(appId);
  const { data: allAgents } = useAgents();
  const addAgent = useAddSolutionAgent(appId);
  const createAgent = useCreateAgent();
  const updateRole = useUpdateSolutionAgentRole(appId);
  const reorder = useReorderSolutionAgents(appId);
  const remove = useRemoveSolutionAgent(appId);

  const [pickId, setPickId] = useState("");
  const [pickRole, setPickRole] = useState<SolutionRole>("worker");
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const members = data?.items ?? [];
  const memberIds = new Set(members.map((m) => m.agent.id));
  const candidates = (allAgents?.items ?? []).filter((a) => !memberIds.has(a.id));

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorDetail(err));
    }
  };

  const move = (index: number, delta: number) => {
    const ids = members.map((m) => m.agent.id);
    const target = index + delta;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    void run(() => reorder.mutateAsync(ids));
  };

  const handleRegister = (body: AgentWrite) =>
    run(async () => {
      const created = await createAgent.mutateAsync(body);
      await addAgent.mutateAsync({ agent_id: created.id, role: pickRole });
      setRegistering(false);
    });

  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Loading…</div>;

  if (registering) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Register a new agent (joins as {ROLE_LABELS[pickRole]})</div>
        <AgentForm
          onSubmit={(body) => void handleRegister(body)}
          onCancel={() => setRegistering(false)}
          saving={createAgent.isPending || addAgent.isPending}
          error={error}
        />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-3)" }}>
        The AI agents that make up this agentic solution, in order. Agents live in the shared
        registry (Agents screen) and can belong to several solutions.
      </p>
      {error && <div role="alert" style={{ color: "var(--crit)", fontSize: 13 }}>{error}</div>}

      {members.length === 0 ? (
        <div style={{ fontSize: 13, color: "var(--ink-3)" }}>No agents yet.</div>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              {["#", "Agent", "Role", "Autonomy", "Approval", "Model", ""].map((h) => (
                <th key={h} style={{ ...cell, textAlign: "left", color: "var(--ink-3)", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {members.map((m, i) => (
              <tr key={m.agent.id}>
                <td style={cell}>{i + 1}</td>
                <td style={cell}>{m.agent.name}</td>
                <td style={cell}>
                  <select
                    aria-label={`Role for ${m.agent.name}`}
                    value={m.role}
                    onChange={(e) =>
                      void run(() =>
                        updateRole.mutateAsync({ agentId: m.agent.id, role: e.target.value as SolutionRole }),
                      )
                    }
                  >
                    {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                  </select>
                </td>
                <td style={cell}>{autonomyLabel(m.agent.autonomy_level)}</td>
                <td style={cell}>{HUMAN_APPROVAL_LABELS[m.agent.human_approval]}</td>
                <td style={cell}>{[m.agent.model_provider, m.agent.model_id].filter(Boolean).join(" · ") || "—"}</td>
                <td style={{ ...cell, whiteSpace: "nowrap" }}>
                  <button type="button" style={smallBtn} aria-label={`Move ${m.agent.name} up`} disabled={i === 0} onClick={() => move(i, -1)}>↑</button>{" "}
                  <button type="button" style={smallBtn} aria-label={`Move ${m.agent.name} down`} disabled={i === members.length - 1} onClick={() => move(i, 1)}>↓</button>{" "}
                  <button
                    type="button"
                    style={smallBtn}
                    aria-label={`Remove ${m.agent.name}`}
                    onClick={() => void run(() => remove.mutateAsync(m.agent.id))}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select aria-label="Agent to add" value={pickId} onChange={(e) => setPickId(e.target.value)}>
          <option value="">Add an existing agent…</option>
          {candidates.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select aria-label="Role for new member" value={pickRole} onChange={(e) => setPickRole(e.target.value as SolutionRole)}>
          {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
        </select>
        <button
          type="button"
          className="ui-btn ui-btn-sm"
          disabled={!pickId || addAgent.isPending}
          onClick={() =>
            void run(async () => {
              await addAgent.mutateAsync({ agent_id: pickId, role: pickRole });
              setPickId("");
            })
          }
        >
          Add
        </button>
        <span style={{ color: "var(--ink-3)", fontSize: 12 }}>or</span>
        <button type="button" className="ui-btn ui-btn-sm" onClick={() => { setError(null); setRegistering(true); }}>
          Register new agent
        </button>
      </div>
    </div>
  );
}
