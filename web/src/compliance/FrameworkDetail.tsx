import { useState } from "react";
import { useFramework, useUpdateFramework, useDeleteFramework } from "../api/compliance";
import type { ControlNode } from "../api/compliance";
import FrameworkForm from "./FrameworkForm";
import ControlTree from "./ControlTree";

interface FrameworkDetailProps {
  frameworkId: string;
  onBack: () => void;
}

/** Recursively counts every control in the tree (all levels) — used for the
 *  client-side delete-scope disclosure (research.md D3). */
function countAllControls(nodes: ControlNode[]): number {
  let total = nodes.length;
  for (const node of nodes) total += countAllControls(node.children);
  return total;
}

/** Defense-in-depth alongside the backend's http(s)-only validation on source_url (security
 *  review finding, 923-derived-compliance-status): only render the field as a clickable link if
 *  it actually parses to an http/https URL, so a value that predates the backend validator (or
 *  reached the database by some other path) can never render as a `javascript:`-executable
 *  href. */
function isHttpUrl(value: string): boolean {
  try {
    const scheme = new URL(value).protocol;
    return scheme === "http:" || scheme === "https:";
  } catch {
    return false;
  }
}

export default function FrameworkDetail({ frameworkId, onBack }: FrameworkDetailProps) {
  const { data: framework, isLoading, error } = useFramework(frameworkId);
  const updateMutation = useUpdateFramework(frameworkId);
  const deleteMutation = useDeleteFramework();
  const [editing, setEditing] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (isLoading) return <div style={{ padding: 16 }}>Loading…</div>;
  if (error || !framework) {
    return <div style={{ padding: 16, color: "var(--crit)" }}>Framework not found</div>;
  }

  function handleDelete() {
    const controlCount = countAllControls(framework!.controls);
    const message =
      controlCount > 0
        ? `Deleting '${framework!.name}' will also remove ${controlCount} control(s) recorded under it. Continue?`
        : `Delete framework '${framework!.name}'?`;
    if (!window.confirm(message)) return;
    setDeleteError(null);
    deleteMutation.mutate(frameworkId, {
      onSuccess: () => onBack(),
      onError: (err) => setDeleteError(err.message),
    });
  }

  return (
    <div style={{ padding: 16 }}>
      <button onClick={onBack} style={{ fontSize: 12, marginBottom: 12 }}>
        ← Back to Frameworks
      </button>

      {editing ? (
        <div style={{ marginBottom: 16 }}>
          <FrameworkForm
            initial={framework}
            onSubmit={(body) => updateMutation.mutate(body, { onSuccess: () => setEditing(false) })}
            onCancel={() => setEditing(false)}
            isLoading={updateMutation.isPending}
          />
          {updateMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
              {updateMutation.error.message}
            </div>
          )}
        </div>
      ) : (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: "0 0 4px 0", fontSize: 16 }}>{framework.name}</h3>
              <div style={{ fontSize: 12, color: "var(--ink-2)" }}>
                {framework.jurisdiction} · {framework.authority} · {framework.version}
              </div>
              {framework.effective_date && (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>
                  Effective {framework.effective_date}
                </div>
              )}
              {framework.source_url && isHttpUrl(framework.source_url) && (
                <div style={{ fontSize: 12, marginTop: 2 }}>
                  <a href={framework.source_url} target="_blank" rel="noreferrer">
                    Source
                  </a>
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setEditing(true)} style={{ fontSize: 12 }}>
                Edit
              </button>
              <button onClick={handleDelete} disabled={deleteMutation.isPending} style={{ fontSize: 12 }}>
                Delete Framework
              </button>
            </div>
          </div>
          {deleteError && (
            <div style={{ color: "var(--crit)", fontSize: 12, marginTop: 6 }}>{deleteError}</div>
          )}
        </div>
      )}

      <h4 style={{ fontSize: 14, marginBottom: 8 }}>Controls</h4>
      <ControlTree frameworkId={frameworkId} controls={framework.controls} />
    </div>
  );
}
