// 941-capability-org-mappings US3: Business -> Organization -> Findings. Four lists derived by the
// server on every read (never stored): L1/L2 with no accountable owner, shared-service candidates
// (L3s performed by two or more independent branches of the org tree), unmapped L3s, and owned L3s
// that nobody performs. Each entry opens the capability on the Capabilities tab.

import type React from "react";
import type { FindingCapability, SharedServiceCandidate } from "../api/organization";
import { useCapabilityOrgFindings } from "../api/organization";

const muted: React.CSSProperties = { fontSize: 12, color: "var(--ink-3)" };
const link: React.CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  color: "var(--accent)",
  cursor: "pointer",
  fontSize: 13,
  textAlign: "left",
};

function pathOf(c: FindingCapability): string {
  return c.path.map((p) => p.name).join(" › ");
}

function CapLink({ cap, onOpen }: { cap: FindingCapability; onOpen?: (id: string) => void }): React.ReactElement {
  return (
    <span>
      <button type="button" style={link} onClick={() => onOpen?.(cap.id)} title="Open on the Capabilities tab">
        {cap.name}
      </button>
      {cap.path.length > 0 && <span style={{ ...muted, marginLeft: 6 }}>{pathOf(cap)}</span>}
    </span>
  );
}

function Section({
  title,
  hint,
  count,
  total,
  children,
}: {
  title: string;
  hint: string;
  count: number;
  total?: number;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <section aria-label={title} style={{ marginBottom: 18 }}>
      <h4 style={{ margin: "0 0 2px", fontSize: 13 }}>
        {title} <span style={muted}>({count}{total !== undefined ? ` of ${total}` : ""})</span>
      </h4>
      <p style={{ ...muted, margin: "0 0 6px" }}>{hint}</p>
      {children}
    </section>
  );
}

function CapList({ items, empty, onOpen }: { items: FindingCapability[]; empty: string; onOpen?: (id: string) => void }): React.ReactElement {
  if (items.length === 0) return <div style={muted}>{empty}</div>;
  return (
    <ul style={{ margin: 0, paddingLeft: 18 }}>
      {items.map((c) => (
        <li key={c.id} style={{ padding: "2px 0" }}>
          <CapLink cap={c} onOpen={onOpen} />
        </li>
      ))}
    </ul>
  );
}

function SharedList({ items, onOpen }: { items: SharedServiceCandidate[]; onOpen?: (id: string) => void }): React.ReactElement {
  if (items.length === 0) return <div style={muted}>No capability is performed by more than one part of the organization.</div>;
  return (
    <ul style={{ margin: 0, paddingLeft: 18 }}>
      {items.map((c) => (
        <li key={c.capability.id} style={{ padding: "3px 0" }}>
          <CapLink cap={c.capability} onOpen={onOpen} />
          <span style={{ ...muted, marginLeft: 6 }}>{c.branches} independent performers</span>
          <ul style={{ margin: "2px 0 0", paddingLeft: 18 }}>
            {c.performers.map((p) => (
              <li key={p.org_unit.id} style={{ fontSize: 12 }}>
                {p.org_unit.name}
                {p.geographies.length > 0 && <span style={muted}> — {p.geographies.map((g) => g.name).join(", ")}</span>}
                {p.folded_into && <span style={muted}> (part of {p.folded_into.name})</span>}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}

export default function OrgFindings({ onOpenCapability }: { onOpenCapability?: (id: string) => void }): React.ReactElement {
  const { data, isLoading, error } = useCapabilityOrgFindings();
  if (isLoading) return <div style={muted}>Loading…</div>;
  if (error || !data) return <div role="alert" style={{ ...muted, color: "var(--crit)" }}>Failed to load findings.</div>;
  const { counts } = data;
  return (
    <div>
      <p style={{ ...muted, marginTop: 0 }}>
        Worked out from the current owner and performer mappings every time this page loads. Fix a mapping on the
        Capabilities tab and the finding goes away.
      </p>
      <Section
        title="No accountable owner"
        hint="L1 and L2 capabilities with no owner of their own and none above them."
        count={counts.no_owner}
        total={counts.l1_l2_total}
      >
        <CapList items={data.no_owner} empty="Every L1 and L2 capability has an owner." onOpen={onOpenCapability} />
      </Section>
      <Section
        title="Shared-service candidates"
        hint="L3 capabilities performed by two or more separate parts of the org tree. A unit and its own sub-units count once."
        count={counts.shared_service}
      >
        <SharedList items={data.shared_service} onOpen={onOpenCapability} />
      </Section>
      <Section
        title="Unmapped"
        hint="L3 capabilities with no performer and no accountable owner."
        count={counts.unmapped}
        total={counts.l3_total}
      >
        <CapList items={data.unmapped} empty="Every L3 capability has a performer or an owner." onOpen={onOpenCapability} />
      </Section>
      <Section
        title="Owned, no performer"
        hint="L3 capabilities with an accountable owner but no one recorded as doing the work."
        count={counts.owned_no_performer}
        total={counts.l3_total}
      >
        <CapList items={data.owned_no_performer} empty="Every owned L3 capability has a performer." onOpen={onOpenCapability} />
      </Section>
    </div>
  );
}
