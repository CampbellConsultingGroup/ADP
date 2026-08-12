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
import ChatButton from "../chat/ChatButton";
import ChatPanel from "../chat/ChatPanel";
import { extractProposedDsl } from "./editor/extractProposedDsl";
import { Button, StatusBadge } from "../ui/primitives";
import {
  createDiagram,
  getDiagram,
  updateDiagram,
  type Diagram,
  type DiagramType,
} from "./api";

/** ADP-SPEC-052 FR-003: a persistent save-state indication, distinct from the Save button's own
 *  momentary label swap. Derived from the pre-existing `saving`/`error` state plus one new
 *  "has this diagram been successfully saved at least once" flag (data-model.md), rather than
 *  introducing a second source of truth. */
type SaveState = "idle" | "saving" | "saved" | "error";

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
  // ADP-SPEC-052 FR-003: reopening an existing diagram already counts as "saved" -- its content
  // came from a successful prior save, even though this fresh page load hasn't triggered one.
  const [hasSavedOnce, setHasSavedOnce] = useState(Boolean(diagramId));
  const saveState: SaveState = saving ? "saving" : error ? "error" : hasSavedOnce ? "saved" : "idle";
  // ADP-SPEC-052 FR-012 (research.md Decision 5): a state-backed ref (not useRef) so Canvas's
  // `toolbarContainer` portal target is available the render after the palette DOM node mounts,
  // rather than staying null forever. Canvas already supports portalling its toolbar into an
  // external container -- no vendored-file change needed (see CanvasProps.toolbarContainer).
  const [paletteEl, setPaletteEl] = useState<HTMLDivElement | null>(null);
  // Closed by default -- only visually meaningful below the shell's 900px breakpoint, where the
  // palette becomes a toggleable drawer rather than a permanent grid column.
  const [paletteCollapsed, setPaletteCollapsed] = useState(true);
  // ADP-914.8: embedded AI assistant, mirrors CapabilityTree.tsx's showChat
  // toggle pattern exactly.
  const [showChat, setShowChat] = useState(false);
  // FR-011 / Clarifications: manual editing is locked while a chat request
  // is in flight, mirroring this file's own existing disabled={saving}
  // convention on the Save button (research.md Decision 4).
  const [chatBusy, setChatBusy] = useState(false);

  const { dsl, parseErrors, applyDsl } = useDslSync(model, setModel, diagramType);

  function getDiagramContext(): string {
    return `Diagram title: ${title}\nDiagram type: ${diagramType}\n\nCurrent DSL:\n${dsl}`;
  }

  // ADP-914.8 User Story 2: a proposed edit is applied to the live,
  // reviewable model via the same applyDsl() reopening an existing diagram
  // already uses -- nothing here is ever auto-saved (FR-006/FR-007).
  function handleAssistantReply(text: string) {
    const proposed = extractProposedDsl(text, diagramType);
    if (proposed !== null) applyDsl(proposed);
  }

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
      setHasSavedOnce(true);
      onSaved?.(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>Loading diagram…</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <input
          className="ui-input"
          style={{ maxWidth: 320 }}
          aria-label="Diagram title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        {!diagramId && (
          <select
            className="ui-select"
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
        <Button variant="primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
        {/* ADP-SPEC-052 FR-003: persistent, distinct from the Save button's own transient label. */}
        {saveState !== "idle" && (
          <span data-testid="save-state-indicator">
            <StatusBadge tone={saveState === "saved" ? "good" : saveState === "error" ? "crit" : "info"}>
              {saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : "Error saving"}
            </StatusBadge>
          </span>
        )}
        <ChatButton active={showChat} onToggle={() => setShowChat(!showChat)} label="Chat" />
      </div>
      {showChat && (
        <ChatPanel
          basePath="/api/v1/chat"
          onClose={() => setShowChat(false)}
          getDiagramContext={getDiagramContext}
          onAssistantReply={handleAssistantReply}
          onStreamingChange={setChatBusy}
        />
      )}
      {error && <div className="ui-alert crit" role="alert">{error}</div>}
      {parseErrors.length > 0 && (
        <ul className="ui-alert crit" role="alert">
          {parseErrors.map((e, i) => (
            <li key={i}>
              Line {e.line}: {e.message}
            </li>
          ))}
        </ul>
      )}
      {/* FR-011: locks Canvas (a large vendored+adapted component, research.md's
          own reasoning for not modifying its internals) via a non-invasive
          wrapper rather than threading a new prop through it.
          ADP-SPEC-052 FR-012: palette rail / canvas / DSL panel simultaneously visible, using
          Canvas's existing toolbarContainer portal target rather than any vendored JSX change. */}
      <div
        className="diagram-workspace"
        style={chatBusy ? { pointerEvents: "none", opacity: 0.6 } : undefined}
      >
        <div className="diagram-workspace__palette" data-collapsed={paletteCollapsed}>
          <button
            type="button"
            className="btn btn--secondary diagram-workspace__palette-toggle"
            data-testid="palette-toggle"
            aria-expanded={!paletteCollapsed}
            onClick={() => setPaletteCollapsed((v) => !v)}
          >
            Shapes
          </button>
          <div className="diagram-workspace__palette-content" ref={setPaletteEl} />
        </div>
        <div className="diagram-workspace__canvas">
          <Canvas model={model} onChange={setModel} dslFamily={diagramType} toolbarContainer={paletteEl} />
        </div>
        <div className="diagram-workspace__dsl">
          <div className="diagram-workspace__dsl-header">
            <span className="ui-label" style={{ margin: 0 }}>Mermaid DSL</span>
            {/* FR-014: canvas edits reflect here automatically -- distinct from the Apply-required
                direction communicated by the hint below the panel. */}
            <StatusBadge tone="info">Synced from canvas</StatusBadge>
          </div>
          <DslPanel dsl={dsl} parseErrors={parseErrors} onApply={applyDsl} disabled={chatBusy} />
          <p className="diagram-workspace__dsl-hint">Editing here? Click Apply to send changes to the canvas.</p>
        </div>
      </div>
      {savedId && <ExportAction diagramId={savedId} model={model} />}
    </div>
  );
}
