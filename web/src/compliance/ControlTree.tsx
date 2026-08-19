import { useState } from "react";
import type { ControlNode } from "../api/compliance";
import {
  useControlObjectives,
  useCreateControl,
  useUpdateControl,
  useDeleteControl,
} from "../api/compliance";
import ControlMappingsEditor from "./ControlMappingsEditor";

interface ControlTreeProps {
  frameworkId: string;
  controls: ControlNode[];
}

/** Recursively counts every descendant beneath a node (not including the node itself) —
 *  used for the client-side delete-scope disclosure (research.md D3: no new backend
 *  endpoint, computed from the already-fetched tree). */
function countDescendants(node: ControlNode): number {
  let total = node.children.length;
  for (const child of node.children) total += countDescendants(child);
  return total;
}

export default function ControlTree({ frameworkId, controls }: ControlTreeProps) {
  const [addingTopLevel, setAddingTopLevel] = useState(false);

  return (
    <div>
      {controls
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((node) => (
          <ControlRow key={node.id} node={node} frameworkId={frameworkId} depth={0} />
        ))}

      {addingTopLevel ? (
        <div style={{ marginTop: 8, border: "1px solid var(--border)", borderRadius: 6, padding: 10 }}>
          <ControlForm
            frameworkId={frameworkId}
            parentId={null}
            onDone={() => setAddingTopLevel(false)}
          />
        </div>
      ) : (
        <button onClick={() => setAddingTopLevel(true)} style={{ fontSize: 12, marginTop: 8 }}>
          + Add top-level control
        </button>
      )}
    </div>
  );
}

function ControlRow({
  node,
  frameworkId,
  depth,
}: {
  node: ControlNode;
  frameworkId: string;
  depth: number;
}) {
  const [editing, setEditing] = useState(false);
  const [addingChild, setAddingChild] = useState(false);
  const [showMappings, setShowMappings] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description ?? "");

  const update = useUpdateControl(node.id, frameworkId);
  const del = useDeleteControl(frameworkId);

  function handleSaveEdit() {
    if (!title.trim()) return;
    update.mutate(
      { title: title.trim(), description: description.trim() || undefined },
      { onSuccess: () => setEditing(false) },
    );
  }

  function handleDelete() {
    const descendantCount = countDescendants(node);
    const message =
      descendantCount > 0
        ? `Deleting '${node.code}' will also remove ${descendantCount} descendant control(s). Continue?`
        : `Delete control '${node.code}'?`;
    if (!window.confirm(message)) return;
    setDeleteError(null);
    del.mutate(node.id, { onError: (err) => setDeleteError(err.message) });
  }

  return (
    <div style={{ marginLeft: depth * 20, marginTop: 6 }}>
      <div
        style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8,
          padding: "6px 8px", border: "1px solid var(--border)", borderRadius: 6,
          background: "var(--surface)",
        }}
      >
        <div style={{ flex: 1 }}>
          {editing ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={255}
                style={{ fontSize: 13 }}
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ fontSize: 12 }}
                rows={2}
              />
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={handleSaveEdit} disabled={update.isPending} style={{ fontSize: 11 }}>
                  Save
                </button>
                <button onClick={() => setEditing(false)} style={{ fontSize: 11 }}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
                {node.code} — {node.title}
              </div>
              {node.description && (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{node.description}</div>
              )}
            </>
          )}
          {deleteError && (
            <div style={{ color: "var(--crit)", fontSize: 11, marginTop: 4 }}>{deleteError}</div>
          )}
        </div>
        {!editing && (
          <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
            <button onClick={() => setShowMappings(!showMappings)} style={{ fontSize: 11 }}>
              {showMappings ? "Hide mappings" : "Mappings"}
            </button>
            <button onClick={() => setAddingChild(!addingChild)} style={{ fontSize: 11 }}>
              {addingChild ? "Cancel" : "+ Sub-control"}
            </button>
            <button onClick={() => setEditing(true)} style={{ fontSize: 11 }}>
              Edit
            </button>
            <button onClick={handleDelete} disabled={del.isPending} style={{ fontSize: 11 }}>
              Delete
            </button>
          </div>
        )}
      </div>

      <LinkedObjectives controlId={node.id} />

      {showMappings && (
        <div style={{ marginLeft: 20, marginTop: 6 }}>
          <ControlMappingsEditor controlId={node.id} />
        </div>
      )}

      {addingChild && (
        <div
          style={{
            marginLeft: 20, marginTop: 6, border: "1px solid var(--border)", borderRadius: 6, padding: 10,
          }}
        >
          <ControlForm
            frameworkId={frameworkId}
            parentId={node.id}
            onDone={() => setAddingChild(false)}
          />
        </div>
      )}

      {node.children
        .slice()
        .sort((a, b) => a.position - b.position)
        .map((child) => (
          <ControlRow key={child.id} node={child} frameworkId={frameworkId} depth={depth + 1} />
        ))}
    </div>
  );
}

function ControlForm({
  frameworkId,
  parentId,
  onDone,
}: {
  frameworkId: string;
  parentId: string | null;
  onDone: () => void;
}) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateControl(frameworkId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim() || !title.trim() || !description.trim()) {
      setError("Code, title, and description are all required");
      return;
    }
    create.mutate(
      { parent_id: parentId, code: code.trim(), title: title.trim(), description: description.trim() },
      {
        onSuccess: () => onDone(),
        onError: (err) => setError(err.message),
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {error && <div style={{ color: "var(--crit)", fontSize: 12 }}>{error}</div>}
      <input
        value={code}
        onChange={(e) => setCode(e.target.value)}
        placeholder="Code (e.g. AC-2)"
        maxLength={100}
        style={{ fontSize: 13 }}
      />
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title"
        maxLength={255}
        style={{ fontSize: 13 }}
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Description"
        rows={2}
        style={{ fontSize: 12 }}
      />
      <div style={{ display: "flex", gap: 6 }}>
        <button type="submit" disabled={create.isPending} style={{ fontSize: 12 }}>
          {create.isPending ? "Adding…" : "Add"}
        </button>
        <button type="button" onClick={onDone} style={{ fontSize: 12 }}>
          Cancel
        </button>
      </div>
    </form>
  );
}

/** Read-only "Linked Objectives" line per control row (925-strategy-compliance-linkage, COMPLY-05
 *  spec.md FR-003 reverse direction) -- hidden entirely when nothing is linked. */
function LinkedObjectives({ controlId }: { controlId: string }) {
  const { data } = useControlObjectives(controlId);
  const items = data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <div style={{ marginLeft: 20, fontSize: 11, color: "var(--ink-3)" }}>
      Regulatory driver for: {items.map((o) => o.statement).join(", ")}
    </div>
  );
}
