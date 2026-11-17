/** What an agent automates (944-agent-traceability, ADP-12x, US1): business L3 capabilities,
 * value stream stages and value chain activities. Links are edited only here (FR-004); choosing
 * a value saves it at once (ADP-w7z). Stages and activities are picked in two steps, stream or
 * chain first. */

import React, { useMemo, useState } from "react";
import {
  errorDetail,
  useAddAutomates,
  useAgentAutomates,
  useRemoveAutomates,
  type AutomatesKind,
} from "../api/agentic";
import {
  useCapabilities,
  useValueChain,
  useValueChains,
  useValueStream,
  useValueStreams,
  type BusinessCapability,
} from "../api/business";
import { Loading } from "../ui/primitives";

const SELECT: React.CSSProperties = { fontSize: 12.5, padding: "3px 6px", minWidth: 180 };
const MUTED: React.CSSProperties = { color: "var(--ink-3)" };

function capabilityPaths(caps: BusinessCapability[]): Map<string, string[]> {
  const byId = new Map(caps.map((c) => [c.id, c]));
  const out = new Map<string, string[]>();
  for (const c of caps) {
    const path: string[] = [];
    let parent = c.parent_id ? byId.get(c.parent_id) : undefined;
    while (parent) {
      path.unshift(parent.name);
      parent = parent.parent_id ? byId.get(parent.parent_id) : undefined;
    }
    out.set(c.id, path);
  }
  return out;
}

function Row({ prefix, name, suffix, onRemove, disabled }: {
  prefix: string;
  name: string;
  suffix?: string;
  onRemove: () => void;
  disabled: boolean;
}) {
  return (
    <li style={{ display: "flex", alignItems: "center", gap: 8, padding: "2px 0" }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        {prefix && <span style={MUTED}>{prefix} </span>}
        <span>{name}</span>
        {suffix && <span style={MUTED}> {suffix}</span>}
      </span>
      <button
        type="button"
        className="ui-btn ui-btn-sm"
        aria-label={`Remove ${name}`}
        onClick={onRemove}
        disabled={disabled}
      >
        Remove
      </button>
    </li>
  );
}

function Group({ title, empty, children }: { title: string; empty: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)" }}>{title}</div>
      {empty && <div style={{ ...MUTED, fontSize: 12.5 }}>None yet.</div>}
      {children}
    </div>
  );
}

export default function AgentAutomates({ agentId }: { agentId: string }) {
  const { data, isLoading } = useAgentAutomates(agentId);
  const add = useAddAutomates(agentId);
  const remove = useRemoveAutomates(agentId);
  const caps = useCapabilities();
  const streams = useValueStreams();
  const chains = useValueChains();
  const [streamId, setStreamId] = useState("");
  const [chainId, setChainId] = useState("");
  const stream = useValueStream(streamId || null);
  const chain = useValueChain(chainId || null);
  const [pending, setPending] = useState<{ kind: AutomatesKind; id: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const paths = useMemo(() => capabilityPaths(caps.data?.items ?? []), [caps.data]);

  if (isLoading || !data) return <Loading />;

  const linkedCaps = new Set(data.capabilities.map((c) => c.id));
  const linkedStages = new Set(data.stages.map((s) => s.id));
  const linkedActivities = new Set(data.activities.map((a) => a.id));
  const label = (c: BusinessCapability) => [...(paths.get(c.id) ?? []), c.name].join(" › ");
  const l3Options = (caps.data?.items ?? [])
    .filter((c) => c.level === 3 && !linkedCaps.has(c.id))
    .sort((a, b) => label(a).localeCompare(label(b)));
  const stageOptions = (stream.data?.stages ?? []).filter((s) => !linkedStages.has(s.id));
  const activityOptions = [
    ...(chain.data?.primary_activities ?? []),
    ...(chain.data?.support_activities ?? []),
  ].filter((a) => !linkedActivities.has(a.id));

  function handleAdd(kind: AutomatesKind, targetId: string) {
    if (!targetId) return;
    setError(null);
    setPending({ kind, id: targetId });
    add.mutate(
      { kind, targetId },
      {
        onSuccess: () => setPending(null),
        onError: (err: unknown) => {
          setPending(null);
          setError(errorDetail(err));
        },
      },
    );
  }

  const chosen = (kind: AutomatesKind) => (pending?.kind === kind ? pending.id : "");
  const removeLink = (kind: AutomatesKind, targetId: string) => remove.mutate({ kind, targetId });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
      <Group title="Business capabilities (L3)" empty={data.capabilities.length === 0}>
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {data.capabilities.map((c) => (
            <Row
              key={c.id}
              prefix={c.path.length ? `${c.path.join(" › ")} ›` : ""}
              name={c.name}
              onRemove={() => removeLink("capability", c.id)}
              disabled={remove.isPending}
            />
          ))}
        </ul>
        <select
          aria-label="Link a business capability"
          value={chosen("capability")}
          onChange={(e) => handleAdd("capability", e.target.value)}
          disabled={add.isPending}
          style={SELECT}
        >
          <option value="">Link an L3 capability…</option>
          {l3Options.map((c) => (
            <option key={c.id} value={c.id}>{label(c)}</option>
          ))}
        </select>
      </Group>

      <Group title="Value stream stages" empty={data.stages.length === 0}>
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {data.stages.map((s) => (
            <Row
              key={s.id}
              prefix={`${s.value_stream_name} ›`}
              name={s.name}
              onRemove={() => removeLink("stage", s.id)}
              disabled={remove.isPending}
            />
          ))}
        </ul>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <select aria-label="Value stream" value={streamId} onChange={(e) => setStreamId(e.target.value)} style={SELECT}>
            <option value="">Value stream…</option>
            {(streams.data?.items ?? []).map((v) => (
              <option key={v.id} value={v.id}>{v.name}</option>
            ))}
          </select>
          {streamId && (
            <select
              aria-label="Link a value stream stage"
              value={chosen("stage")}
              onChange={(e) => handleAdd("stage", e.target.value)}
              disabled={add.isPending}
              style={SELECT}
            >
              <option value="">Link a stage…</option>
              {stageOptions.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          )}
        </div>
      </Group>

      <Group title="Value chain activities" empty={data.activities.length === 0}>
        <ul style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
          {data.activities.map((a) => (
            <Row
              key={a.id}
              prefix={`${a.value_chain_name} ›`}
              name={a.name}
              suffix={`(${a.category})`}
              onRemove={() => removeLink("activity", a.id)}
              disabled={remove.isPending}
            />
          ))}
        </ul>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <select aria-label="Value chain" value={chainId} onChange={(e) => setChainId(e.target.value)} style={SELECT}>
            <option value="">Value chain…</option>
            {(chains.data?.items ?? []).map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {chainId && (
            <select
              aria-label="Link a value chain activity"
              value={chosen("activity")}
              onChange={(e) => handleAdd("activity", e.target.value)}
              disabled={add.isPending}
              style={SELECT}
            >
              <option value="">Link an activity…</option>
              {activityOptions.map((a) => (
                <option key={a.id} value={a.id}>{a.name} ({a.category})</option>
              ))}
            </select>
          )}
        </div>
      </Group>

      {error && <div style={{ color: "var(--crit)", fontSize: 12.5 }}>{error}</div>}
    </div>
  );
}
