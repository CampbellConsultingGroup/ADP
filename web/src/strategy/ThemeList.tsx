import { useState } from "react";
import { useThemes, useCreateTheme } from "../api/strategy";
import { Button } from "../ui";

export default function ThemeList() {
  const { data, isLoading, error } = useThemes();
  const createMutation = useCreateTheme();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

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

  return (
    <div>
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

      {items.length === 0 && !showForm && (
        <div style={{ color: "var(--ink-3)", fontSize: 13 }}>No themes yet. Create one above.</div>
      )}

      {items.map((t) => (
        <div
          key={t.id}
          style={{
            border: "1px solid var(--border)", borderRadius: 8, padding: "10px 12px", marginBottom: 8,
            background: "var(--surface)",
          }}
        >
          <div style={{ fontWeight: 500, fontSize: 14, color: "var(--ink)" }}>{t.name}</div>
        </div>
      ))}
    </div>
  );
}
