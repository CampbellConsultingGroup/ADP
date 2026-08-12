// ADP-SPEC-046: User Story 3 (browse/find a previously created diagram, delete).
// ADP-SPEC-052 (research.md Decision 2): data-fetching moved from ad hoc
// useState/useEffect to TanStack Query hooks (api.ts's useDiagrams/
// useDeleteDiagram), and markup moved from a raw <table> to ADP's .ui-list
// convention -- mirrors web/src/designs/DesignsPage.tsx's list treatment.

import { Button } from "../ui";
import { useDiagrams, useDeleteDiagram } from "./api";

export interface DiagramListPageProps {
  onOpen: (diagramId: string) => void;
}

export function DiagramListPage({ onOpen }: DiagramListPageProps) {
  const { data, isLoading, error } = useDiagrams();
  const deleteDiagram = useDeleteDiagram();

  const items = data?.items ?? [];

  if (isLoading) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--ink-3)" }}>Loading diagrams…</div>;
  }

  if (error) {
    return <div className="ui-alert crit" role="alert">{error.message}</div>;
  }

  if (items.length === 0) {
    return (
      <div className="ui-empty">
        <h2>No diagrams yet</h2>
        <p>Create your first diagram to get started.</p>
      </div>
    );
  }

  return (
    <div className="ui-list">
      {items.map((item) => (
        <div key={item.id} className="ui-list-row">
          <div style={{ flex: 1, minWidth: 0 }}>
            <button
              type="button"
              className="btn btn--tertiary"
              style={{ padding: 0, fontSize: 15, fontWeight: 600, color: "var(--ink)" }}
              onClick={() => onOpen(item.id)}
            >
              {item.title}
            </button>
            <div className="ui-meta">
              {item.diagram_type} · Updated {new Date(item.updated_at).toLocaleString()}
            </div>
          </div>
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            <Button size="sm" onClick={() => onOpen(item.id)}>Open</Button>
            <Button
              variant="danger"
              size="sm"
              aria-label={`Delete ${item.title}`}
              onClick={() => deleteDiagram.mutate(item.id)}
            >
              Delete
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
