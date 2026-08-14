import { useState } from "react";
import {
  useThemes,
  useCreateTheme,
  useUpdateTheme,
  useDeleteTheme,
  type StrategicTheme,
} from "../api/strategy";
import { Button } from "../ui";

function ThemeEditForm({ theme, onDone }: { theme: StrategicTheme; onDone: () => void }) {
  const updateMutation = useUpdateTheme(theme.id);
  const [description, setDescription] = useState(theme.description ?? "");
  const [owner, setOwner] = useState(theme.owner ?? "");
  const [priority, setPriority] = useState(theme.priority != null ? String(theme.priority) : "");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateMutation.mutate(
      {
        description: description.trim() || null,
        owner: owner.trim() || null,
        priority: priority.trim() ? Number(priority) : null,
      },
      { onSuccess: onDone },
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 8, background: "var(--surface)" }}
    >
      <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
      </label>
      <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        Owner
        <input value={owner} onChange={(e) => setOwner(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
      </label>
      <label style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
        Priority (1–5)
        <input type="number" min={1} max={5} value={priority} onChange={(e) => setPriority(e.target.value)} style={{ display: "block", width: "100%", marginTop: 2 }} />
      </label>
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" disabled={updateMutation.isPending}>
          {updateMutation.isPending ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onDone}>Cancel</button>
      </div>
      {updateMutation.isError && (
        <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
          {updateMutation.error.message}
        </div>
      )}
    </form>
  );
}

export default function ThemeList() {
  const { data, isLoading, error } = useThemes();
  const createMutation = useCreateTheme();
  const deleteMutation = useDeleteTheme();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (isLoading) return <div style={{ padding: 16, color: "var(--ink-3)" }}>Loading themes…</div>;
  if (error) return <div className="ui-alert crit">Failed to load themes</div>;

  const items = data?.items ?? [];

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setFormError("Name is required");
      return;
    }
    setFormError(null);
    createMutation.mutate(
      { name: name.trim() },
      {
        onSuccess: () => {
          setShowForm(false);
          setName("");
        },
      },
    );
  }

  function handleDelete(theme: StrategicTheme) {
    if (!confirm(`Delete theme "${theme.name}"?`)) return;
    setDeleteError(null);
    deleteMutation.mutate(theme.id, {
      onError: (err: Error & { status?: number }) => {
        // FR-014: deleting a theme still referenced by an objective is
        // blocked (409) rather than silently orphaning it -- surface why.
        setDeleteError(
          err.status === 409
            ? `"${theme.name}" is still assigned to at least one objective — reassign or delete those first.`
            : err.message,
        );
      },
    });
  }

  return (
    <div>
      <p style={{ fontSize: 13, color: "var(--ink-3)", margin: "0 0 16px", lineHeight: 1.5 }}>
        <strong style={{ color: "var(--ink-2)" }}>Theme:</strong> A broad, ongoing area of strategic focus
        (e.g. &ldquo;Operational Resilience&rdquo;) that groups related objectives under a shared intent.
        Themes are qualitative and long-lived — they don&rsquo;t carry metrics or fiscal horizons themselves.
        Objectives are created under a theme to make it measurable and actionable.
      </p>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15, color: "var(--ink)" }}>Strategic Themes</h3>
        <Button size="sm" variant={showForm ? "default" : "primary"} icon={showForm ? undefined : "plus"} onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "New Theme"}
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12, background: "var(--surface)" }}
        >
          {formError && <div style={{ color: "var(--crit)", fontSize: 13, marginBottom: 6 }}>{formError}</div>}
          <label style={{ fontSize: 13 }}>
            Name *
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ display: "block", width: "100%", marginTop: 2 }}
              placeholder="Usage-based pricing"
            />
          </label>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Saving…" : "Save"}
            </button>
            <button type="button" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
          {createMutation.isError && (
            <div className="ui-alert crit" style={{ marginTop: 6, fontSize: 12 }}>
              {createMutation.error.message}
            </div>
          )}
        </form>
      )}

      {deleteError && (
        <div className="ui-alert crit" style={{ marginBottom: 12, fontSize: 12 }}>{deleteError}</div>
      )}

      {items.length === 0 && !showForm && (
        <div style={{ color: "var(--ink-3)", fontSize: 13 }}>No themes yet. Create one above.</div>
      )}

      {items.map((t) =>
        editingId === t.id ? (
          <ThemeEditForm key={t.id} theme={t} onDone={() => setEditingId(null)} />
        ) : (
          <div
            key={t.id}
            style={{
              display: "flex", justifyContent: "space-between", alignItems: "flex-start",
              border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8,
              background: "var(--surface)",
            }}
          >
            <div>
              <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)" }}>
                {t.name}
                {t.priority != null && (
                  <span style={{ fontWeight: 400, fontSize: 12, color: "var(--ink-3)", marginLeft: 8 }}>
                    Priority {t.priority}
                  </span>
                )}
              </div>
              {t.description && (
                <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 2 }}>{t.description}</div>
              )}
              {t.owner && (
                <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>Owner: {t.owner}</div>
              )}
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <Button size="sm" onClick={() => setEditingId(t.id)}>Edit</Button>
              <Button size="sm" variant="danger" onClick={() => handleDelete(t)}>Delete</Button>
            </div>
          </div>
        ),
      )}
    </div>
  );
}
