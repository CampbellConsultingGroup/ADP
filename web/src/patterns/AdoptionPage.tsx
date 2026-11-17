/** One adoption: derived status, plateau, bindings, findings, conformance / transition views,
 * pins, Save as diagram (936 US1–US3, US5). Everything shown is computed on this request. */

import { useState } from "react";
import {
  errorDetail,
  useAdoption,
  useAdoptionView,
  useConformance,
  useDeleteAdoption,
} from "../api/patterns";
import type { AdoptionViewKind, ConformanceReport } from "../api/patterns";
import type { DiagramSeed } from "../diagrams/generators";
import { StatusBadge } from "../ui";
import FindingsTable from "./FindingsTable";
import FlowchartView from "./FlowchartView";
import { SCOPE_LABELS, STATUS_LABELS, STATUS_TONES } from "./labels";
import { useCanManagePatterns } from "./permissions";
import PinsEditor from "./PinsEditor";
import { flowchartToSeed } from "./saveAsDiagram";
import { confirmAction } from "../ui/confirm";

function Plateau({ report }: { report: ConformanceReport }) {
  if (!report.plateau) return null;
  const { reached, next, blocking } = report.plateau;
  return (
    <div aria-label="Plateau" className="ui-card" style={{ padding: 10, fontSize: 13 }}>
      <strong>Migration progress:</strong> {reached ? `reached ${reached}` : "no plateau reached yet"}
      {next ? ` · next ${next}, blocked by ${blocking.join(", ")}` : " · all plateaus reached"}
    </div>
  );
}

function AdoptionView({ id, view, title, onGenerateDiagram }: {
  id: string; view: AdoptionViewKind; title: string; onGenerateDiagram?: (seed: DiagramSeed) => void;
}) {
  const { data, isLoading, error } = useAdoptionView(id, view);
  const [saveError, setSaveError] = useState<string | null>(null);
  if (isLoading) return <div style={{ fontSize: 13, color: "var(--ink-3)" }}>Rendering…</div>;
  if (error || !data) return <div className="ui-alert crit" role="alert">The view could not be loaded.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {onGenerateDiagram && (
        <button
          type="button"
          className="ui-btn ui-btn-sm"
          style={{ alignSelf: "flex-start" }}
          onClick={() => {
            const seed = flowchartToSeed(data.flowchart, title);
            if (seed) onGenerateDiagram(seed);
            else setSaveError("This view could not be converted to a diagram.");
          }}
        >
          Save as diagram
        </button>
      )}
      {saveError && <div className="ui-alert crit" role="alert">{saveError}</div>}
      <FlowchartView flowchart={data.flowchart} title={title} truncated={data.truncated} />
    </div>
  );
}

export default function AdoptionPage({ adoptionId, onBack, onGenerateDiagram }: {
  adoptionId: string; onBack: () => void; onGenerateDiagram?: (seed: DiagramSeed) => void;
}) {
  const canManage = useCanManagePatterns();
  const { data: adoption, isLoading, error } = useAdoption(adoptionId);
  const { data: report } = useConformance(adoptionId);
  const del = useDeleteAdoption(adoptionId);
  const [view, setView] = useState<AdoptionViewKind>("conformance");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (isLoading) return <div style={{ padding: 20, fontSize: 13 }}>Loading…</div>;
  if (error || !adoption) return <div style={{ padding: 20 }} role="alert">Adoption not found.</div>;

  const scope = adoption.scope_type === "business_domain" ? adoption.scope_name ?? adoption.scope_ref
    : adoption.scope_type === "application_set" ? `${adoption.member_ids.length} applications` : "whole portfolio";

  return (
    <div style={{ padding: "16px 20px", overflow: "auto", height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
      <button type="button" className="ui-btn ui-btn-sm" style={{ alignSelf: "flex-start" }} onClick={onBack}>← All adoptions</button>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0, fontSize: 17 }}>{adoption.name}</h2>
        {report && <StatusBadge tone={STATUS_TONES[report.status]}>{STATUS_LABELS[report.status]}</StatusBadge>}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--ink-2)" }}>
        {adoption.pattern_name ?? adoption.pattern_key} · {SCOPE_LABELS[adoption.scope_type]}: {scope} ·{" "}
        {adoption.pinned_version ? `pinned to ${adoption.pinned_version}` : `follows current (${adoption.resolved_version ?? "none"})`}
      </div>
      {report && <Plateau report={report} />}

      {report && (
        <div aria-label="Bindings" style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12.5 }}>
          {report.bindings.map((b) => (
            <div key={b.role_key} className="ui-card" style={{ padding: 8, minWidth: 160 }}>
              <strong>{b.label}</strong> · {b.count}
              <div style={{ color: "var(--ink-3)" }}>{b.elements.slice(0, 5).map((e) => e.name).join(", ") || "none bound"}{b.count > 5 ? "…" : ""}</div>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ margin: "6px 0 0", fontSize: 14 }}>Findings</h3>
      {report ? <FindingsTable findings={report.findings} empty="No findings: the scope conforms." /> : <div>Evaluating…</div>}

      <h3 style={{ margin: "6px 0 0", fontSize: 14 }}>Diagram</h3>
      {adoption.kind === "transition" && (
        <select aria-label="Adoption view" value={view} onChange={(e) => setView(e.target.value as AdoptionViewKind)} style={{ alignSelf: "flex-start" }}>
          <option value="conformance">Conformance</option>
          <option value="transition">Transition</option>
        </select>
      )}
      <AdoptionView
        key={view}
        id={adoption.id}
        view={view}
        title={`${adoption.name} — ${view}`}
        onGenerateDiagram={onGenerateDiagram}
      />

      {canManage && report && (
        <>
          <h3 style={{ margin: "6px 0 0", fontSize: 14 }}>Pins</h3>
          <PinsEditor adoption={adoption} roles={report.bindings} />
          <button
            type="button"
            className="ui-btn ui-btn-danger ui-btn-sm"
            style={{ alignSelf: "flex-start" }}
            onClick={async () => {
              if (!(await confirmAction(`Delete adoption "${adoption.name}"?`))) return;
              setDeleteError(null);
              try { await del.mutateAsync(); onBack(); } catch (err) { setDeleteError(errorDetail(err)); }
            }}
          >
            Delete adoption
          </button>
          {deleteError && <div className="ui-alert crit" role="alert">{deleteError}</div>}
        </>
      )}
    </div>
  );
}
