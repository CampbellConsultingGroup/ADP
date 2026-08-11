// ADP-SPEC-046: User Story 1 (create/author/save) + reopen for editing.
//
// `diagramTypeId` is stamped identically to the ADP DiagramType / dslFamily
// registry key for all 5 supported types -- confirmed by reading
// core/dsl/architecture.ts (and the other 4 families) that none of them
// branch on diagramTypeId during parse/serialize, so there's no need to
// special-case a different internal label the way the upstream test suite's
// own convention does ('cloud-infrastructure' for the architecture family).

import { useEffect, useState } from "react";
import { Canvas } from "./editor/Canvas";
import { DslPanel } from "./editor/DslPanel";
import { ExportAction } from "./editor/ExportAction";
import { useDslSync } from "./editor/useDslSync";
import { createEmptyDiagramModel, type DiagramModel } from "./core/index";
import { useAuth } from "../auth/AuthProvider";
import { getRecommendedDiagramType } from "./persona";
import {
  createDiagram,
  getDiagram,
  updateDiagram,
  type Diagram,
  type DiagramType,
} from "./api";

export interface DiagramEditorPageProps {
  /** Existing diagram id to load, or undefined to author a brand-new one. */
  diagramId?: string;
  /** Required when diagramId is undefined -- the type chosen for a new diagram. */
  newDiagramType?: DiagramType;
  /**
   * ADP-914.7: pre-filled title + model for a diagram generated from ADP's own
   * business data (a value stream's stages, a capability's subtree). Only
   * consulted when `diagramId` is undefined (a genuinely new diagram) and
   * takes priority over `newDiagramType`/the persona-aware default below --
   * a seed already carries real content, so there is nothing to steer.
   */
  seed?: { title: string; model: DiagramModel };
  onSaved?: (diagram: Diagram) => void;
}

const DIAGRAM_TYPES: DiagramType[] = ["flowchart", "sequence", "erd", "uml", "architecture"];

export function DiagramEditorPage({
  diagramId,
  newDiagramType,
  seed,
  onSaved,
}: DiagramEditorPageProps) {
  const [title, setTitle] = useState(seed?.title ?? "Untitled diagram");
  // Tracks the persisted id -- starts as the `diagramId` prop (editing an
  // existing diagram) and gets set once a brand-new diagram is first saved,
  // so ExportAction (which needs a real id to export against) becomes
  // available without requiring a page navigation.
  const [savedId, setSavedId] = useState<string | undefined>(diagramId);
  // ADP-914.6: an explicit `newDiagramType` prop always wins (FR-004); absent
  // that, a new diagram defaults to the signed-in architect's mapped type
  // (FR-002/FR-003), falling back to today's pre-feature "flowchart" default
  // when the role is unrecognized (FR-006). Computed once and reused for both
  // `diagramType` and the initial `model` below so they never start out of
  // sync with each other. ADP-914.7: a `seed` (generated content) takes
  // priority over both -- see the prop doc above.
  const { user } = useAuth();
  const recommended = getRecommendedDiagramType(user?.role);
  const initialType = (seed?.model.diagramTypeId as DiagramType | undefined) ?? newDiagramType ?? recommended ?? "flowchart";
  const [diagramType, setDiagramType] = useState<DiagramType>(initialType);
  const [model, setModel] = useState<DiagramModel>(() => seed?.model ?? createEmptyDiagramModel(initialType));
  const [loading, setLoading] = useState(Boolean(diagramId));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { dsl, parseErrors, applyDsl } = useDslSync(model, setModel, diagramType);

  useEffect(() => {
    if (!diagramId) return;
    let cancelled = false;
    setLoading(true);
    getDiagram(diagramId)
      .then((diagram) => {
        if (cancelled) return;
        setTitle(diagram.title);
        setDiagramType(diagram.diagram_type);
        if (diagram.dsl_source) {
          applyDsl(diagram.dsl_source);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // applyDsl intentionally omitted -- it's derived fresh each render from
    // `model`/`diagramType` and re-running this effect on every model change
    // (which applyDsl itself causes) would create a load loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagramId]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const saved = savedId
        ? await updateDiagram(savedId, { title, dsl_source: dsl })
        : await createDiagram({ title, diagram_type: diagramType, dsl_source: dsl });
      setSavedId(saved.id);
      onSaved?.(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div>Loading…</div>;

  return (
    <div>
      <div>
        <input
          aria-label="Diagram title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        {!diagramId && (
          <select
            aria-label="Diagram type"
            value={diagramType}
            onChange={(e) => {
              const next = e.target.value as DiagramType;
              setDiagramType(next);
              setModel(createEmptyDiagramModel(next));
            }}
          >
            {DIAGRAM_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
                {t === recommended ? " (Recommended for your role)" : ""}
              </option>
            ))}
          </select>
        )}
        <button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {parseErrors.length > 0 && (
        <ul role="alert">
          {parseErrors.map((e, i) => (
            <li key={i}>
              Line {e.line}: {e.message}
            </li>
          ))}
        </ul>
      )}
      <Canvas model={model} onChange={setModel} dslFamily={diagramType} />
      <DslPanel dsl={dsl} parseErrors={parseErrors} onApply={applyDsl} />
      {savedId && <ExportAction diagramId={savedId} model={model} />}
    </div>
  );
}
