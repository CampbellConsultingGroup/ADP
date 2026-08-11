// ADP-SPEC-046: User Story 3 (browse/find a previously created diagram, delete).

import { useEffect, useState } from "react";
import { listDiagrams, deleteDiagram, type DiagramSummary } from "./api";

export interface DiagramListPageProps {
  onOpen: (diagramId: string) => void;
}

export function DiagramListPage({ onOpen }: DiagramListPageProps) {
  const [items, setItems] = useState<DiagramSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    setLoading(true);
    listDiagrams()
      .then((resp) => setItems(resp.items))
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  async function handleDelete(id: string) {
    try {
      await deleteDiagram(id);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  if (loading) return <div>Loading…</div>;
  if (error) return <p role="alert">{error}</p>;

  if (items.length === 0) {
    return <p>No diagrams yet.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Last updated</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id}>
            <td>
              <button type="button" onClick={() => onOpen(item.id)}>
                {item.title}
              </button>
            </td>
            <td>{item.diagram_type}</td>
            <td>{new Date(item.updated_at).toLocaleString()}</td>
            <td>
              <button
                type="button"
                aria-label={`Delete ${item.title}`}
                onClick={() => handleDelete(item.id)}
              >
                Delete
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
