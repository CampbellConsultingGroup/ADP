// ADP-SPEC-054: the C4Canvas.tsx replacement, built on the diagram tool's reused Canvas.tsx/
// DslPanel.tsx (ADP-SPEC-052) instead of ReactFlow. Edits commit immediately per action via
// reconcile.ts (research.md Decision 5) -- never a whole-design save. Reached via a new, separate
// nav entry (research.md Decision 8); the existing "Canvas" item and C4Canvas.tsx are untouched.

import { useCallback, useEffect, useRef, useState } from "react";
import { Canvas } from "../diagrams/editor/Canvas";
import { DslPanel } from "../diagrams/editor/DslPanel";
import { useDslSync } from "../diagrams/editor/useDslSync";
import type { DiagramModel } from "../diagrams/core/model/diagram-model";
import {
  useCreateElement,
  useCreateRelationship,
  useDeleteElement,
  useDeleteRelationship,
  useDesign,
  useLayout,
  useSaveLayout,
  useUpdateElement,
} from "../api/designs";
import InspectionPanel from "../inspection/InspectionPanel";
import type { C4Level } from "../types";
import { Button, StatusBadge } from "../ui/primitives";
import { elementsToC4Model } from "./c4Adapter";
import { applyIdReplacements, reconcile } from "./reconcile";

const LEVELS: { label: string; value: C4Level }[] = [
  { label: "Context", value: "context" },
  { label: "Container", value: "container" },
  { label: "Component", value: "component" },
];

const LAYOUT_SAVE_DEBOUNCE_MS = 800;

export interface C4DesignViewProps {
  designId: string;
}

export function C4DesignView({ designId }: C4DesignViewProps) {
  const [level, setLevel] = useState<C4Level>("context");
  const [model, setModel] = useState<DiagramModel | null>(null);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(null);
  const [reconcileError, setReconcileError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data: design, isLoading, error: designError } = useDesign(designId);
  const { data: layout } = useLayout(designId, level);
  const saveLayout = useSaveLayout();

  const createElement = useCreateElement(designId);
  const updateElement = useUpdateElement(designId);
  const deleteElement = useDeleteElement(designId);
  const createRelationship = useCreateRelationship(designId);
  const deleteRelationship = useDeleteRelationship(designId);

  const modelRef = useRef<DiagramModel | null>(null);
  modelRef.current = model;
  const layoutSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // FR-013 / research.md Decision 3: (re-)derive the model from the canonical Element[]/
  // Relationship[] + the *existing*, unmodified layout endpoint whenever the design or the
  // selected level changes -- switching levels never keeps a separate per-level copy (FR-015).
  useEffect(() => {
    if (!design) return;
    setModel(elementsToC4Model(design.elements, design.relationships, level, layout?.positions ?? {}));
    // layout intentionally omitted from deps beyond its initial value for this level -- refetches
    // on level change already re-run this effect via the `level` dependency itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [design, level]);

  const saveLayoutDebounced = useCallback(
    (next: DiagramModel) => {
      if (layoutSaveTimer.current) clearTimeout(layoutSaveTimer.current);
      layoutSaveTimer.current = setTimeout(() => {
        const positions = Object.fromEntries(next.nodes.map((n) => [n.id, n.position]));
        saveLayout.mutate({ design_id: designId, level, positions });
      }, LAYOUT_SAVE_DEBOUNCE_MS);
    },
    [designId, level, saveLayout],
  );

  // research.md Decision 5: fires on every Canvas.tsx onChange (direct manipulation) AND every
  // DslPanel applyDsl (text editing) -- both funnel through useDslSync's onModelChange below, and
  // reconcile() diffs purely on model content, indifferent to which path produced it.
  const handleModelChange = useCallback(
    (next: DiagramModel) => {
      const previous = modelRef.current;
      setModel(next);
      saveLayoutDebounced(next);
      if (!previous) return;
      setReconcileError(null);
      reconcile(previous, next, {
        createElement: (body) => createElement.mutateAsync(body),
        updateElement: (elementId, body) => updateElement.mutateAsync({ elementId, body }).then(() => undefined),
        deleteElement: (elementId) => deleteElement.mutateAsync(elementId),
        createRelationship: (body) => createRelationship.mutateAsync(body),
        deleteRelationship: (relationshipId) => deleteRelationship.mutateAsync(relationshipId),
      })
        .then((replacements) => {
          if (replacements.length > 0) {
            setModel((current) => (current ? applyIdReplacements(current, replacements) : current));
          }
        })
        .catch((err: unknown) => {
          setReconcileError(err instanceof Error ? err.message : String(err));
        });
    },
    [createElement, updateElement, deleteElement, createRelationship, deleteRelationship, saveLayoutDebounced],
  );

  const { dsl, parseErrors, applyDsl } = useDslSync(model ?? { diagramTypeId: "c4-context", nodes: [], edges: [], containers: [] }, handleModelChange, "c4");

  async function handleExportRender() {
    setExporting(true);
    setExportError(null);
    try {
      const { getAuthHeader } = await import("../api/client");
      const authHeader = await getAuthHeader();
      const resp = await fetch(`/api/v1/designs/${designId}/render`, {
        method: "POST",
        headers: { ...authHeader, "Content-Type": "application/json" },
        body: JSON.stringify({ level }),
      });
      if (!resp.ok) throw new Error(`Render failed: ${resp.status}`);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  }

  async function handleExportCalm() {
    setExporting(true);
    setExportError(null);
    try {
      const { getAuthHeader } = await import("../api/client");
      const authHeader = await getAuthHeader();
      const resp = await fetch(`/api/v1/designs/${designId}/export/calm`, { headers: authHeader });
      if (!resp.ok) throw new Error(`Export failed: ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${designId}-calm.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(false);
    }
  }

  if (isLoading || !model) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>Loading design…</div>;
  }
  if (designError || !design) {
    return <div className="ui-alert crit" role="alert">Failed to load design.</div>;
  }

  return (
    <div className="ui-page">
      <div className="ui-toolbar">
        <div>
          <h1 className="ui-h1">{design.title}</h1>
          <p className="ui-subtle">C4 Design (Preview) — built and edited directly, saved immediately.</p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {LEVELS.map(({ label, value }) => (
            <Button
              key={value}
              variant={level === value ? "primary" : "default"}
              size="sm"
              onClick={() => setLevel(value)}
            >
              {label}
            </Button>
          ))}
          <Button size="sm" onClick={handleExportRender} disabled={exporting}>
            {exporting ? "Exporting…" : "Export Render"}
          </Button>
          <Button size="sm" onClick={handleExportCalm} disabled={exporting}>
            Export CALM
          </Button>
        </div>
      </div>

      {reconcileError && <div className="ui-alert crit" role="alert">{reconcileError}</div>}
      {exportError && <div className="ui-alert crit" role="alert">{exportError}</div>}
      {parseErrors.length > 0 && (
        <ul className="ui-alert crit" role="alert">
          {parseErrors.map((e, i) => (
            <li key={i}>Line {e.line}: {e.message}</li>
          ))}
        </ul>
      )}

      <div style={{ display: "flex", gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Canvas model={model} onChange={handleModelChange} dslFamily="c4" />
        </div>
        <div style={{ width: 320, display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="ui-panel">
            <h3 className="ui-panel-h">Elements</h3>
            <div className="ui-list">
              {design.elements.map((el) => (
                <div
                  key={el.id}
                  data-testid={`element-row-${el.id}`}
                  className={`ui-list-row selectable${selectedElementId === el.id ? " active" : ""}`}
                  onClick={() => setSelectedElementId(el.id)}
                >
                  <span>{el.name}</span>
                  <StatusBadge tone="neutral">{el.kind}</StatusBadge>
                </div>
              ))}
              {design.elements.length === 0 && <div className="ui-empty"><p>No elements yet.</p></div>}
            </div>
          </div>
          {selectedElementId && (
            <InspectionPanel
              elementId={selectedElementId}
              design={design}
              onClose={() => setSelectedElementId(null)}
            />
          )}
          <DslPanel dsl={dsl} parseErrors={parseErrors} onApply={applyDsl} />
        </div>
      </div>
    </div>
  );
}

export default C4DesignView;
